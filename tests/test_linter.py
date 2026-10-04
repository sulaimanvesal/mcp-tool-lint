import json
from pathlib import Path

from mcp_tool_lint import lint_tools, lint_document, load_document

ROOT = Path(__file__).resolve().parents[1]

GOOD = {
    "name": "read_file",
    "description": "Read a UTF-8 text file from the workspace and return its contents.",
    "inputSchema": {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Relative path."}},
        "required": ["path"],
        "additionalProperties": False,
    },
    "annotations": {"readOnlyHint": True},
}


def rules(report):
    return {f.rule for f in report.findings}


def test_good_tool_is_clean():
    report = lint_tools([GOOD])
    assert report.ok and report.errors == [] and report.warnings == []


def test_missing_name_is_error():
    report = lint_tools([{"description": "x" * 30, "inputSchema": {"type": "object"}}])
    assert "NAME_MISSING" in rules(report) and not report.ok


def test_bad_name_format():
    bad = dict(GOOD, name="Bad Name!")
    assert "NAME_FORMAT" in rules(lint_tools([bad]))


def test_duplicate_names():
    assert "NAME_DUPLICATE" in rules(lint_tools([GOOD, GOOD]))


def test_short_description_warns():
    assert "DESCRIPTION_TOO_SHORT" in rules(lint_tools([dict(GOOD, description="reads")]))


def test_missing_description_errors():
    tool = {k: v for k, v in GOOD.items() if k != "description"}
    assert "DESCRIPTION_MISSING" in rules(lint_tools([tool]))


def test_missing_schema_errors():
    tool = {k: v for k, v in GOOD.items() if k != "inputSchema"}
    assert "SCHEMA_MISSING" in rules(lint_tools([tool]))


def test_schema_type_must_be_object():
    tool = dict(GOOD, inputSchema={"type": "array"})
    assert "SCHEMA_TYPE" in rules(lint_tools([tool]))


def test_required_must_be_defined():
    schema = {"type": "object", "properties": {}, "required": ["nope"], "additionalProperties": False}
    assert "REQUIRED_UNDEFINED" in rules(lint_tools([dict(GOOD, inputSchema=schema)]))


def test_property_without_type_or_description_warns():
    schema = {"type": "object", "properties": {"x": {}}, "additionalProperties": False}
    r = rules(lint_tools([dict(GOOD, inputSchema=schema)]))
    assert "PROPERTY_NO_TYPE" in r and "PROPERTY_NO_DESCRIPTION" in r


def test_unknown_property_type_errors():
    schema = {"type": "object", "additionalProperties": False,
              "properties": {"x": {"type": "weird", "description": "d"}}}
    assert "PROPERTY_BAD_TYPE" in rules(lint_tools([dict(GOOD, inputSchema=schema)]))


def test_empty_enum_errors():
    schema = {"type": "object", "additionalProperties": False,
              "properties": {"x": {"type": "string", "description": "d", "enum": []}}}
    assert "ENUM_EMPTY" in rules(lint_tools([dict(GOOD, inputSchema=schema)]))


def test_destructive_tool_without_guard_warns():
    tool = dict(GOOD, name="delete_file",
                description="Delete a file from the workspace permanently and quickly.")
    assert "DESTRUCTIVE_NO_GUARD" in rules(lint_tools([tool]))


def test_destructive_tool_with_guard_and_annotations_is_quiet():
    tool = dict(GOOD, name="delete_file",
                description="Permanently delete a file; irreversible, call only after user confirmation.",
                annotations={"destructiveHint": True})
    r = rules(lint_tools([tool]))
    assert "DESTRUCTIVE_NO_GUARD" not in r and "ANNOTATIONS_MISSING" not in r


def test_strict_names_warns_on_camel_case():
    assert "NAME_NOT_SNAKE_CASE" in rules(lint_tools([dict(GOOD, name="readFile")], strict_names=True))
    assert "NAME_NOT_SNAKE_CASE" not in rules(lint_tools([dict(GOOD, name="readFile")]))


def test_document_shapes():
    assert lint_document([GOOD]).tool_count == 1
    assert lint_document({"tools": [GOOD]}).tool_count == 1
    assert lint_document({"result": {"tools": [GOOD, GOOD]}}).tool_count == 2
    assert lint_document(GOOD).tool_count == 1


def test_bundled_examples():
    good = lint_document(json.loads((ROOT / "examples" / "good_tools.json").read_text()))
    bad = lint_document(json.loads((ROOT / "examples" / "bad_tools.json").read_text()))
    assert good.ok and good.warnings == []
    assert not bad.ok and len(bad.errors) >= 4


def test_load_document_from_disk(tmp_path):
    p = tmp_path / "tools.json"
    p.write_text(json.dumps({"tools": [GOOD]}))
    assert load_document(p)[0]["name"] == "read_file"
