"""mcp-tool-lint: lint MCP (Model Context Protocol) tool definitions.

Zero-dependency static checks for the tool schemas an MCP server exposes:
naming, descriptions, inputSchema sanity, required-field consistency,
and guard hints for destructive tools. Usable as a library and a CI CLI.
"""
from .linter import Finding, Report, lint_tools, lint_document, load_document

__all__ = ["Finding", "Report", "lint_tools", "lint_document", "load_document"]
__version__ = "0.1.0"
