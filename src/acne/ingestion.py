"""
ingestion.py — Stage 1: Ingestion & Provenance-Anchored Chunking
Transforms unstructured feeds (emails, transcripts, notes, PDFs) into
overlapping chunks with Document nodes and EXTRACTED_FROM provenance edges.
"""

from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional
import hashlib
import re
from urllib.parse import urlparse
from .models import DocumentArtifact, TextChunk, TLPGNode, TLPGEdge, _now_iso

# ------------------------------------------------------------------
# Chunking helpers
# ------------------------------------------------------------------

def _approx_token_count(text: str) -> int:
    # rough: 1 token ≈ 4 chars, but use words for stability when offline
    return max(1, len(text.split()))

def chunk_text(
    text: str,
    document_id: str,
    chunk_tokens: int = 650,
    overlap_tokens: int = 100,
    min_tokens: int = 150,
) -> List[TextChunk]:
    """
    Split into overlapping context chunks, 500-1000 tokens default.
    Keeps character offsets for provenance traceability.
    """
    words = text.split()
    total_words = len(words)  # ~ tokens for our purposes
    chunks: List[TextChunk] = []
    idx = 0
    char_cursor = 0
    chunk_index = 0

    while idx < total_words:
        end = min(idx + chunk_tokens, total_words)
        chunk_words = words[idx:end]
        chunk_text_str = " ".join(chunk_words)

        if _approx_token_count(chunk_text_str) < min_tokens and chunks:
            # too tiny tail — append to previous instead of new chunk
            chunks[-1].text += " " + chunk_text_str
            chunks[-1].token_count = _approx_token_count(chunks[-1].text)
            char_cursor += len(chunk_text_str) + 1
            break

        # find char offsets via search (approx but stable for provenance)
        start_char = text.find(chunk_words[0], char_cursor) if chunk_words else char_cursor
        if start_char == -1:
            start_char = char_cursor
        end_char = start_char + len(chunk_text_str)

        chk = TextChunk(
            document_id=document_id,
            text=chunk_text_str,
            token_count=_approx_token_count(chunk_text_str),
            chunk_index=chunk_index,
            start_char=start_char,
            end_char=end_char,
            overlap_with_prev=overlap_tokens if chunk_index > 0 else 0,
        )
        chunks.append(chk)
        char_cursor = end_char
        chunk_index += 1

        if end >= total_words:
            break
        idx = end - overlap_tokens  # overlap
        if idx < 0:
            idx = 0

    return chunks

# ------------------------------------------------------------------
# Document artifact creation
# ------------------------------------------------------------------

def make_document_artifact(
    source_path: str | Path,
    title: str = "",
    author: str = None,
    publication_timestamp: str = None,
    uri: str = None,
    extra_meta: Dict[str, Any] = None,
) -> tuple[DocumentArtifact, str]:
    """
    Create a Document/Citation node for a source file or blob.
    Returns (artifact, raw_text).
    """
    raw_input = str(source_path)
    # Only treat as path if short and no newlines and exists
    is_path_candidate = "\n" not in raw_input and len(raw_input) < 600 and not raw_input.strip().startswith("From:")
    p = Path(raw_input) if is_path_candidate else None
    raw_text = ""
    checksum = ""
    byte_size = 0
    mime_type = "text/plain"
    computed_uri = uri

    if p and p.exists() and p.is_file():
        # read file
        try:
            raw_text = p.read_text(encoding="utf-8", errors="ignore")
        except:
            raw_text = p.read_bytes().decode("utf-8", errors="ignore")[:200000]
        byte_size = len(raw_text.encode("utf-8", errors="ignore"))
        checksum = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:16]
        if not computed_uri:
            computed_uri = f"file://{p.resolve()}"
        if p.suffix.lower() == ".pdf":
            mime_type = "application/pdf"
        elif p.suffix.lower() in (".md", ".markdown"):
            mime_type = "text/markdown"
        title = title or p.name
    elif isinstance(source_path, str) and len(source_path) > 20:
        # raw text blob passed directly
        raw_text = source_path
        byte_size = len(raw_text.encode("utf-8"))
        checksum = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:16]
        computed_uri = computed_uri or f"inline://{checksum}"
        title = title or f"Inline {checksum[:8]}"
    else:
        raw_text = str(source_path)
        checksum = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:16]
        computed_uri = computed_uri or f"inline://{checksum}"

    doc = DocumentArtifact(
        uri=computed_uri,
        title=title or "Untitled",
        author=author,
        publication_timestamp=publication_timestamp,
        checksum=checksum,
        mime_type=mime_type,
        byte_size=byte_size,
        metadata=extra_meta or {},
    )
    return doc, raw_text

# ------------------------------------------------------------------
# Main ingestion entry
# ------------------------------------------------------------------

def ingest_feed(
    source: str | Path,
    tlpg_store,
    title: str = "",
    author: str = None,
    uri: str = None,
    meta: Dict[str, Any] = None,
    chunk_tokens: int = 650,
    overlap: int = 120,
) -> Dict[str, Any]:
    """
    Stage 1 driver: artifact + chunking + EXTRACTED_FROM edges.
    Returns dict with document, chunks, provenance edges.
    """
    doc, raw_text = make_document_artifact(source, title=title, author=author, uri=uri, extra_meta=meta)
    tlpg_store.save_document(doc)

    chunks = chunk_text(raw_text, document_id=doc.id, chunk_tokens=chunk_tokens, overlap_tokens=overlap)
    tlpg_store.save_chunks(chunks)

    # Create provenance edges: Chunk -(EXTRACTED_FROM)-> Document
    prov_edges: List[TLPGEdge] = []
    for chk in chunks:
        edge = TLPGEdge(
            source_id=chk.id,
            target_id=doc.id,
            edge_type="EXTRACTED_FROM",
            confidence=1.0,
            properties={"chunk_index": chk.chunk_index, "start_char": chk.start_char, "end_char": chk.end_char},
            source="ingest",
            provenance_chunk_id=chk.id,
        )
        prov_edges.append(edge)
    tlpg_store.add_edges(prov_edges)

    return {
        "document": doc,
        "raw_text_len": len(raw_text),
        "chunks": chunks,
        "chunk_count": len(chunks),
        "provenance_edges": prov_edges,
    }

# ------------------------------------------------------------------
# Email / note specific conveniences
# ------------------------------------------------------------------

def extract_emails_and_headers(text: str) -> Dict[str, str]:
    """Pull From/To/Date-ish lines for provenance without cloud."""
    headers = {}
    for line in text.splitlines()[:15]:
        if ":" in line and len(line) < 200:
            key, val = line.split(":", 1)
            k = key.strip().lower()
            if k in ("from", "to", "cc", "date", "subject", "author"):
                headers[k] = val.strip()
    return headers
