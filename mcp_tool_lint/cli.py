"""Command-line interface: mcp-tool-lint <file.json> [--json] [--strict]."""
from __future__ import annotations

import argparse
import json
import sys

from .linter import load_document, lint_tools


def build_parser():
    p = argparse.ArgumentParser(
        prog="mcp-tool-lint",
        description="Lint MCP tool definitions for naming, description, and schema problems.")
    p.add_argument("files", nargs="+", help="JSON file(s) with tool definitions")
    p.add_argument("--json", action="store_true", help="emit a JSON report")
    p.add_argument("--strict", action="store_true",
                   help="treat warnings as errors (exit 1) and require snake_case names")
    p.add_argument("--min-description", type=int, default=20,
                   help="minimum description length before a warning (default 20)")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    combined = {"files": [], "ok": True}
    exit_code = 0
    for path in args.files:
        try:
            tools = load_document(path)
        except (OSError, ValueError) as exc:
            print(f"{path}: failed to load: {exc}", file=sys.stderr)
            exit_code = 2
            combined["ok"] = False
            combined["files"].append({"file": path, "error": str(exc)})
            continue
        report = lint_tools(tools, min_description=args.min_description,
                            strict_names=args.strict)
        bad = bool(report.errors) or (args.strict and bool(report.warnings))
        if bad:
            exit_code = 1
            combined["ok"] = False
        if args.json:
            combined["files"].append({"file": path, **report.to_dict()})
        else:
            print(f"== {path}")
            print(report.render_text())
    if args.json:
        print(json.dumps(combined, indent=2))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
