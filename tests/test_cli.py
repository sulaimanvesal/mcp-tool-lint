import json
from pathlib import Path

from mcp_tool_lint.cli import main

ROOT = Path(__file__).resolve().parents[1]


def test_cli_good_file_exits_zero(capsys):
    code = main([str(ROOT / "examples" / "good_tools.json")])
    assert code == 0
    assert "no findings" in capsys.readouterr().out


def test_cli_bad_file_exits_one(capsys):
    code = main([str(ROOT / "examples" / "bad_tools.json")])
    assert code == 1
    assert "NAME_DUPLICATE" in capsys.readouterr().out


def test_cli_json_report(capsys):
    code = main(["--json", str(ROOT / "examples" / "bad_tools.json")])
    assert code == 1
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is False and data["files"][0]["error_count"] >= 4


def test_cli_missing_file_exits_two(capsys):
    assert main(["/nonexistent/tools.json"]) == 2


def test_cli_strict_turns_warnings_into_failure(tmp_path, capsys):
    doc = {"tools": [{"name": "readFile", "description": "short",
                      "inputSchema": {"type": "object", "properties": {},
                                      "additionalProperties": False}}]}
    p = tmp_path / "t.json"
    p.write_text(json.dumps(doc))
    assert main([str(p)]) == 0          # warnings only
    capsys.readouterr()
    assert main(["--strict", str(p)]) == 1
