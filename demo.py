"""Zero-key demo: lint the bundled good and bad example tool sets."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mcp_tool_lint import lint_document  # noqa: E402

HERE = Path(__file__).parent

for name in ("good_tools.json", "bad_tools.json"):
    doc = json.loads((HERE / "examples" / name).read_text(encoding="utf-8"))
    report = lint_document(doc)
    print(f"== examples/{name}: {report.tool_count} tool(s), ok={report.ok}")
    print(report.render_text())
    print()
print("Demo done: the good set passes clean; the bad set shows errors to fix before shipping.")
