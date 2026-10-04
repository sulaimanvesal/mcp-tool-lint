"""Core lint engine for MCP tool definitions.

A *tool* here is the dict shape returned by an MCP ``tools/list`` call::

    {"name": "read_file", "description": "...", "inputSchema": {...}}

Input documents may be a bare list of tools, ``{"tools": [...]}``, a full
JSON-RPC envelope ``{"result": {"tools": [...]}}``, or a single tool dict.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SNAKE_RE = re.compile(r"^[a-z][a-z0-9_]*$")
DESTRUCTIVE_WORDS = ("delete", "remove", "drop", "destroy", "purge", "wipe",
                     "exec", "shell", "run_command", "write", "overwrite", "send")
GUARD_WORDS = ("confirm", "approval", "dry-run", "dry run", "irreversible",
               "destructive", "caution", "warning", "will permanently")
VALID_TYPES = {"string", "number", "integer", "boolean", "array", "object", "null"}

ERROR, WARNING, INFO = "error", "warning", "info"


@dataclass
class Finding:
    rule: str
    severity: str
    tool: str
    message: str

    def to_dict(self):
        return {"rule": self.rule, "severity": self.severity,
                "tool": self.tool, "message": self.message}


@dataclass
class Report:
    findings: list = field(default_factory=list)
    tool_count: int = 0

    def add(self, rule, severity, tool, message):
        self.findings.append(Finding(rule, severity, tool, message))

    @property
    def errors(self):
        return [f for f in self.findings if f.severity == ERROR]

    @property
    def warnings(self):
        return [f for f in self.findings if f.severity == WARNING]

    @property
    def ok(self):
        return not self.errors

    def to_dict(self):
        return {"tool_count": self.tool_count, "ok": self.ok,
                "error_count": len(self.errors), "warning_count": len(self.warnings),
                "findings": [f.to_dict() for f in self.findings]}

    def render_text(self):
        if not self.findings:
            return f"OK: {self.tool_count} tool(s), no findings."
        lines = []
        for f in self.findings:
            lines.append(f"[{f.severity.upper():7}] {f.tool} :: {f.rule}: {f.message}")
        lines.append(f"-- {len(self.errors)} error(s), {len(self.warnings)} warning(s) "
                     f"across {self.tool_count} tool(s)")
        return "\n".join(lines)


def load_document(path):
    """Load a JSON document from *path* and return its list of tool dicts."""
    text = Path(path).read_text(encoding="utf-8")
    return extract_tools(json.loads(text))


def extract_tools(document):
    if isinstance(document, list):
        return document
    if isinstance(document, dict):
        if isinstance(document.get("tools"), list):
            return document["tools"]
        result = document.get("result")
        if isinstance(result, dict) and isinstance(result.get("tools"), list):
            return result["tools"]
        if "name" in document:  # a single tool definition
            return [document]
    raise ValueError("could not find a list of tools in the document "
                     "(expected a list, {'tools': [...]}, a JSON-RPC result, or one tool)")


def lint_document(document, *, min_description=20, strict_names=False):
    return lint_tools(extract_tools(document),
                      min_description=min_description, strict_names=strict_names)


def lint_tools(tools, *, min_description=20, strict_names=False):
    report = Report(tool_count=len(tools))
    seen = {}
    for i, tool in enumerate(tools):
        if not isinstance(tool, dict):
            report.add("TOOL_NOT_OBJECT", ERROR, f"<index {i}>", "tool entry is not an object")
            continue
        _lint_one(tool, report, seen, min_description, strict_names)
    return report


def _lint_one(tool, report, seen, min_description, strict_names):
    name = tool.get("name")
    label = name if isinstance(name, str) and name else "<unnamed>"
    if not isinstance(name, str) or not name:
        report.add("NAME_MISSING", ERROR, label, "tool has no string 'name'")
        return
    if not NAME_RE.match(name):
        report.add("NAME_FORMAT", ERROR, name,
                   "name must be 1-64 chars of letters, digits, '_' or '-' (MCP spec)")
    if strict_names and not SNAKE_RE.match(name):
        report.add("NAME_NOT_SNAKE_CASE", WARNING, name,
                   "name is not snake_case; consistent snake_case names are easier for models to call")
    if name in seen:
        report.add("NAME_DUPLICATE", ERROR, name, f"duplicate tool name (first seen at index {seen[name]})")
    seen.setdefault(name, len(seen))

    desc = tool.get("description")
    if not isinstance(desc, str) or not desc.strip():
        report.add("DESCRIPTION_MISSING", ERROR, name,
                   "tool has no description; the model chooses tools from descriptions")
    else:
        if len(desc.strip()) < min_description:
            report.add("DESCRIPTION_TOO_SHORT", WARNING, name,
                       f"description is {len(desc.strip())} chars (< {min_description}); "
                       "say what it does, when to use it, and what it returns")
        low = desc.lower()
        if any(w in name.lower() for w in DESTRUCTIVE_WORDS) and not any(g in low for g in GUARD_WORDS):
            report.add("DESTRUCTIVE_NO_GUARD", WARNING, name,
                       "name suggests a mutating/destructive action but the description "
                       "mentions no confirmation, dry-run, or irreversibility warning")

    schema = tool.get("inputSchema")
    if not isinstance(schema, dict):
        report.add("SCHEMA_MISSING", ERROR, name, "tool has no object 'inputSchema'")
        return
    if schema.get("type") != "object":
        report.add("SCHEMA_TYPE", ERROR, name, "inputSchema.type must be 'object'")
    props = schema.get("properties")
    if props is None:
        props = {}
        if schema.get("type") == "object":
            report.add("SCHEMA_NO_PROPERTIES", INFO, name,
                       "inputSchema has no 'properties'; fine only if the tool truly takes no arguments")
    if not isinstance(props, dict):
        report.add("SCHEMA_PROPERTIES_TYPE", ERROR, name, "inputSchema.properties must be an object")
        return
    required = schema.get("required") or []
    if not isinstance(required, list):
        report.add("REQUIRED_TYPE", ERROR, name, "inputSchema.required must be an array of names")
        required = []
    for req in required:
        if req not in props:
            report.add("REQUIRED_UNDEFINED", ERROR, name,
                       f"required parameter '{req}' is not defined in properties")
    for pname, pschema in props.items():
        if not isinstance(pschema, dict):
            report.add("PROPERTY_NOT_SCHEMA", ERROR, name, f"parameter '{pname}' is not a schema object")
            continue
        ptype = pschema.get("type")
        if ptype is None:
            report.add("PROPERTY_NO_TYPE", WARNING, name, f"parameter '{pname}' has no 'type'")
        elif isinstance(ptype, str) and ptype not in VALID_TYPES:
            report.add("PROPERTY_BAD_TYPE", ERROR, name, f"parameter '{pname}' has unknown type '{ptype}'")
        if not str(pschema.get("description", "")).strip():
            report.add("PROPERTY_NO_DESCRIPTION", WARNING, name,
                       f"parameter '{pname}' has no description; models guess argument values without one")
        if "enum" in pschema and (not isinstance(pschema["enum"], list) or not pschema["enum"]):
            report.add("ENUM_EMPTY", ERROR, name, f"parameter '{pname}' has an empty/invalid 'enum'")
    if "additionalProperties" not in schema:
        report.add("ADDITIONAL_PROPERTIES_UNSET", INFO, name,
                   "inputSchema does not set additionalProperties; set it to false to reject stray arguments")
    annotations = tool.get("annotations")
    if any(w in name.lower() for w in DESTRUCTIVE_WORDS) and not isinstance(annotations, dict):
        report.add("ANNOTATIONS_MISSING", INFO, name,
                   "mutating tool has no 'annotations' (e.g. destructiveHint / readOnlyHint) for client UIs")
