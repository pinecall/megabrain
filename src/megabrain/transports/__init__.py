"""The edges of the system: CLI, MCP, HTTP.

A transport parses its own protocol, calls a use case, and formats the result.
It holds no engine logic — that is what keeps three surfaces from drifting into
three subtly different products.
"""
