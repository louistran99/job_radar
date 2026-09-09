from __future__ import annotations

from pathlib import Path

import pytest

import main
import src.bootstrap as bootstrap


def _venv_python(repo_root: Path) -> Path:
    python = bootstrap.venv_python(repo_root / ".venv")
    python.parent.mkdir(parents=True)
    python.write_text("", encoding="utf-8")
    return python


def test_importing_main_does_not_create_venv(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib
    import subprocess

    def fail(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("subprocess.run must not run on import")

    monkeypatch.setattr(subprocess, "run", fail)
    importlib.reload(main)


def test_bootstrap_skips_venv_on_ci(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(bootstrap, "create_venv", lambda _p: (_ for _ in ()).throw(AssertionError("venv")))
    monkeypatch.setattr(bootstrap, "deps_importable", lambda: True)
    bootstrap.bootstrap(repo_root=tmp_path, environ={"CI": "true"})
    out = capsys.readouterr().out
    assert "1 of 5 (Create virtual environment — skipped on CI)" in out
    assert "2 of 5 (Install dependencies — already satisfied)" in out


def test_bootstrap_creates_venv_and_reexecs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    created: list[Path] = []
    execd: list[tuple[str, list[str]]] = []

    def fake_create(path: Path) -> None:
        created.append(path)
        _venv_python(tmp_path)

    def fake_execv(program: str, args: list[str]) -> None:
        execd.append((program, list(args)))

    monkeypatch.setattr(bootstrap, "create_venv", fake_create)
    monkeypatch.setattr(bootstrap, "deps_importable", lambda: True)
    monkeypatch.setattr(bootstrap, "install_requirements", lambda: (_ for _ in ()).throw(AssertionError("pip")))
    bootstrap.bootstrap(
        repo_root=tmp_path,
        environ={},
        argv=["main.py", "--verbose"],
        executable="/usr/bin/python3",
        execv=fake_execv,
    )
    assert created == [tmp_path / ".venv"]
    venv_py = str(bootstrap.venv_python(tmp_path / ".venv"))
    assert execd == [(venv_py, [venv_py, "main.py", "--verbose"])]
    out = capsys.readouterr().out
    assert "1 of 5 (Create virtual environment)" in out
    assert "Install dependencies" not in out


def test_bootstrap_reuses_venv_and_skips_install(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    python = _venv_python(tmp_path)
    monkeypatch.setattr(bootstrap, "create_venv", lambda _p: (_ for _ in ()).throw(AssertionError("venv")))
    monkeypatch.setattr(bootstrap, "deps_importable", lambda: True)
    installs: list[bool] = []
    monkeypatch.setattr(bootstrap, "install_requirements", lambda: installs.append(True))
    bootstrap.bootstrap(
        repo_root=tmp_path,
        environ={},
        executable=str(python.resolve()),
        execv=lambda _p, _a: (_ for _ in ()).throw(AssertionError("execv")),
    )
    assert installs == []
    out = capsys.readouterr().out
    assert "1 of 5 (Create virtual environment — reuse .venv)" in out
    assert "2 of 5 (Install dependencies — already satisfied)" in out


def test_bootstrap_installs_when_deps_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    python = _venv_python(tmp_path)
    monkeypatch.setattr(bootstrap, "create_venv", lambda _p: (_ for _ in ()).throw(AssertionError("venv")))
    monkeypatch.setattr(bootstrap, "deps_importable", lambda: False)
    installs: list[bool] = []
    monkeypatch.setattr(bootstrap, "install_requirements", lambda: installs.append(True))
    bootstrap.bootstrap(
        repo_root=tmp_path,
        environ={},
        executable=str(python.resolve()),
        execv=lambda _p, _a: (_ for _ in ()).throw(AssertionError("execv")),
    )
    assert installs == [True]
    out = capsys.readouterr().out
    assert "2 of 5 (Install dependencies)" in out
    assert "already satisfied" not in out


def test_bootstrap_child_skips_step_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    python = _venv_python(tmp_path)
    monkeypatch.setattr(bootstrap, "create_venv", lambda _p: (_ for _ in ()).throw(AssertionError("venv")))
    monkeypatch.setattr(bootstrap, "deps_importable", lambda: True)
    bootstrap.bootstrap(
        repo_root=tmp_path,
        environ={bootstrap.BOOTSTRAP_CHILD_ENV: "1"},
        executable=str(python.resolve()),
        execv=lambda _p, _a: (_ for _ in ()).throw(AssertionError("execv")),
    )
    out = capsys.readouterr().out
    assert "1 of 5" not in out
    assert "2 of 5 (Install dependencies — already satisfied)" in out
