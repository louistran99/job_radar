from __future__ import annotations

from pathlib import Path

from src.report import stdout_summary, write_report
from src.snapshot import Diff


def test_write_report_creates_file_when_missing(tmp_path: Path) -> None:
    path = tmp_path / "report.md"
    write_report(path, "# Job monitor — first\n")
    assert path.read_text(encoding="utf-8") == "# Job monitor — first\n"


def test_write_report_prepends_by_default(tmp_path: Path) -> None:
    path = tmp_path / "report.md"
    write_report(path, "# Job monitor — first\n")
    write_report(path, "# Job monitor — second\n")
    text = path.read_text(encoding="utf-8")
    assert text.count("# Job monitor") == 2
    assert text == "# Job monitor — second\n\n# Job monitor — first\n"


def test_write_report_replace_overwrites(tmp_path: Path) -> None:
    path = tmp_path / "report.md"
    write_report(path, "# Job monitor — first\n")
    write_report(path, "# Job monitor — second\n", replace=True)
    assert path.read_text(encoding="utf-8") == "# Job monitor — second\n"


def test_stdout_summary_wrote_vs_prepended(tmp_path: Path) -> None:
    path = tmp_path / "report.md"
    diff = Diff(new=[], removed=[], still_open=[], baseline=False)
    assert "Wrote" in stdout_summary(diff, path)
    assert "Prepended" in stdout_summary(diff, path, prepended=True)
