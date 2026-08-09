"""SSE/HTTP-servable MCP server for acne, built on the official MCP SDK.

The stdio JSON-RPC server in mcp_server.py stays dependency-free; this wrapper
exists so HTTP MCP clients (for example scout-cli's meta-MCP namespaces, which
consume SSE/streamable-HTTP downstreams) can use acne as a downstream people-
memory server. Requires the optional extra:  pip install acne[mcp]

Each tool is registered with its REAL input schema: a typed Python signature
is synthesized from TOOLS_DEF's inputSchema so the SDK validates arguments
natively and callers pass ordinary fields ({"query": ...}), not a wrapped
JSON string. A first integration attempt used a uniform args-string
convention; the MCP SDK silently dropped the real fields callers naturally
sent, and a contact was persisted empty — schema fidelity is load-bearing,
not cosmetic. Dispatch reuses mcp_server's handle_tools_call, so the two
transports cannot drift.
"""

from __future__ import annotations

import json
import keyword

from .mcp_server import TOOLS_DEF, handle_tools_call

_JSON_TO_PY = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "object": "dict",
    "array": "list",
}

_OMIT = object()


def _require_sdk():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as e:
        raise RuntimeError(
            "The MCP SDK is not installed. Run: pip install acne[mcp]"
        ) from e
    return FastMCP


def _make_tool(tdef: dict):
    """Synthesize a function whose signature mirrors the tool's inputSchema."""
    name = tdef["name"]
    schema = tdef.get("inputSchema", {}) or {}
    props = schema.get("properties", {}) or {}
    required = set(schema.get("required", []))
    if not all(p.isidentifier() and not keyword.iskeyword(p) for p in props):
        raise ValueError(f"tool {name!r} has a non-identifier parameter name")

    params, collectors = [], []
    # Required parameters first, then optional (schema default or omit-sentinel).
    for p in [p for p in props if p in required] + [p for p in props if p not in required]:
        py_type = _JSON_TO_PY.get(props[p].get("type", "string"), "str")
        if p in required:
            params.append(f"{p}: {py_type}")
            collectors.append(f"    _args[{p!r}] = {p}")
        elif "default" in props[p]:
            params.append(f"{p}: {py_type} = {props[p]['default']!r}")
            collectors.append(f"    _args[{p!r}] = {p}")
        else:
            params.append(f"{p}: {py_type} | None = None")
            collectors.append(f"    if {p} is not None: _args[{p!r}] = {p}")

    src = (
        f"def {name}({', '.join(params)}) -> str:\n"
        f"    _args = {{}}\n"
        + "\n".join(collectors) + ("\n" if collectors else "")
        + f"    try:\n"
        f"        _r = _dispatch({{'name': {name!r}, 'arguments': _args}})\n"
        f"    except Exception as e:\n"
        f"        return _json.dumps({{'ok': False, 'error': str(e)}})\n"
        f"    return _json.dumps({{'ok': True, 'result': _r}}, default=str)\n"
    )
    scope = {"_dispatch": handle_tools_call, "_json": json}
    exec(src, scope)  # noqa: S102 — source is built only from our own TOOLS_DEF
    return scope[name]


def build_server(port: int = 8899):
    FastMCP = _require_sdk()
    server = FastMCP("acne", port=port)
    for tdef in TOOLS_DEF:
        server.tool(name=tdef["name"], description=tdef["description"])(_make_tool(tdef))
    return server


def run_server(transport: str = "sse", port: int = 8899) -> None:
    build_server(port=port).run(transport="sse" if transport == "sse" else "stdio")
