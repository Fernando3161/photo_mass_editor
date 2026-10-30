"""Install and verify locked dependencies inside the repository's .venv."""

from importlib.metadata import version
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
EXPECTED = (ROOT / ".venv").resolve()


def main() -> None:
    if sys.version_info < (3, 11):
        raise SystemExit("Python 3.11 or newer is required")
    if Path(sys.prefix).resolve() != EXPECTED:
        if not EXPECTED.exists():
            subprocess.run([sys.executable, "-m", "venv", str(EXPECTED)], check=True)
        interpreter = EXPECTED / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if not interpreter.is_file():
            raise SystemExit(f"Virtual environment needs repair: {interpreter}")
        subprocess.run([str(interpreter), str(Path(__file__).resolve())], check=True)
        return
    lock = ROOT / "requirements.lock"
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-r", str(lock)],
        check=True,
    )
    for line in lock.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        name, expected = line.split("==", 1)
        actual = version(name)
        if actual != expected:
            raise SystemExit(f"{name}: expected {expected}, found {actual}")
        print(f"{name}=={actual}")
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)
    frontend = ROOT / "frontend"
    if frontend.joinpath("package.json").is_file():
        node = shutil.which("node")
        npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
        if not node or not npm:
            raise SystemExit("Phase 02 frontend requires Node.js and npm on PATH")
        node_version = subprocess.run(
            [node, "--version"], check=True, capture_output=True, text=True
        ).stdout.strip()
        major = int(node_version.removeprefix("v").split(".", 1)[0])
        if major < 22:
            raise SystemExit(f"Node.js 22 or newer is required; found {node_version}")
        subprocess.run([npm, "ci", "--no-audit", "--no-fund"], cwd=frontend, check=True)
        subprocess.run([npm, "ls", "--all"], cwd=frontend, check=True,
                       stdout=subprocess.DEVNULL)
        print(f"Frontend dependencies verified with Node.js {node_version}")
    print(f"Environment verified: {sys.executable}")


if __name__ == "__main__":
    main()
