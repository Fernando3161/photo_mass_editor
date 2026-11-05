"""Build the production UI only when tracked frontend inputs change."""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
STAMP = FRONTEND / "dist" / ".source.sha256"


def fingerprint() -> str:
    digest = hashlib.sha256()
    files = sorted((FRONTEND / "src").rglob("*"))
    files += [FRONTEND / name for name in ("index.html", "package.json", "package-lock.json",
                                           "vite.config.ts", "tsconfig.app.json", "tsconfig.json")]
    for path in files:
        if path.is_file():
            digest.update(path.relative_to(FRONTEND).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def main() -> None:
    if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve():
        raise SystemExit("Use the repository .venv interpreter")
    for name in ("package.json", "package-lock.json", "index.html"):
        if not (FRONTEND / name).is_file():
            raise SystemExit(f"Missing frontend input: {name}")
    current = fingerprint()
    if STAMP.is_file() and (FRONTEND / "dist" / "index.html").is_file() and STAMP.read_text().strip() == current:
        print("Frontend bundle is current")
        return
    npm = shutil.which("npm.cmd" if sys.platform == "win32" else "npm")
    if npm is None:
        raise SystemExit("Node.js/npm is required to build the frontend")
    STAMP.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([npm, "run", "build"], cwd=FRONTEND, check=True)
    if not (STAMP.parent / "index.html").is_file():
        raise SystemExit("Frontend build did not produce index.html")
    STAMP.write_text(current + "\n", encoding="ascii")
    print("Frontend bundle built and stamped")


if __name__ == "__main__":
    main()
