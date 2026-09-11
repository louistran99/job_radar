"""Create `.venv` and install deps before the CLI imports third-party packages."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = REPO_ROOT / ".venv"
REQUIREMENTS = REPO_ROOT / "requirements.txt"
TOTAL_STEPS = 5
BOOTSTRAP_CHILD_ENV = "JOB_SEARCH_BOOTSTRAP_CHILD"


def progress(step: int, description: str) -> None:
    print(f"{step} of {TOTAL_STEPS} ({description})", flush=True)


def status(description: str) -> None:
    print(description, flush=True)


def venv_python(venv_dir: Path = VENV_DIR) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"


def deps_importable() -> bool:
    return importlib.util.find_spec("requests") is not None


def create_venv(venv_dir: Path) -> None:
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)


def install_requirements(
    python: str | None = None, requirements: Path = REQUIREMENTS
) -> None:
    exe = python or sys.executable
    subprocess.run([exe, "-m", "pip", "install", "-r", str(requirements)], check=True)


def _same_python(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return False


def bootstrap(
    *,
    repo_root: Path = REPO_ROOT,
    argv: Sequence[str] | None = None,
    environ: Mapping[str, str] | None = None,
    executable: str | None = None,
    execv: Callable[[str, Sequence[str]], None] | None = None,
) -> None:
    """Create `.venv` if needed, re-exec into it, then install deps when missing."""
    env = os.environ if environ is None else environ
    venv_dir = repo_root / ".venv"
    python = venv_python(venv_dir)
    current = Path(sys.executable if executable is None else executable)
    ci = bool(env.get("CI"))
    child = env.get(BOOTSTRAP_CHILD_ENV) == "1"

    if not child:
        if ci:
            progress(1, "Create virtual environment — skipped on CI")
        elif python.exists():
            progress(1, "Create virtual environment — reuse .venv")
        else:
            progress(1, "Create virtual environment")
            create_venv(venv_dir)

    if not ci and python.exists() and not _same_python(current, python):
        args = list(sys.argv if argv is None else argv)
        argv_list = [str(python), *args]
        if execv is None:
            child_env = {**os.environ, BOOTSTRAP_CHILD_ENV: "1"}
            os.execve(str(python), argv_list, child_env)
        else:
            execv(str(python), argv_list)
        return

    if deps_importable():
        progress(2, "Install dependencies — already satisfied")
    else:
        progress(2, "Install dependencies")
        install_requirements()
