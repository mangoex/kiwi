"""Install frozen external dependencies, then the local packages without resolving again."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from compile_python_locks import input_digest

ROOT = Path(__file__).resolve().parents[1]


def verify_lock_inputs(root: Path, target: str) -> None:
    digest = input_digest(target.startswith("dev"), target != "api-runtime-linux", root)
    expected = f"# Input SHA256: {digest}"
    lines = (
        (root / "requirements" / f"{target}-py312.lock").read_text(encoding="utf-8").splitlines()
    )
    if expected not in lines[:5]:
        raise RuntimeError("Python manifest and frozen lock inputs differ; regenerate explicitly")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dev", action="store_true")
    args = parser.parse_args()
    if sys.version_info[:2] != (3, 12) or sys.platform not in {"linux", "win32"}:
        raise RuntimeError("Recorded installation targets are Python 3.12 Linux and Windows")
    target = (
        "dev-windows"
        if args.dev and sys.platform == "win32"
        else "dev-linux"
        if args.dev
        else "gateway-runtime-windows"
        if sys.platform == "win32"
        else "api-runtime-linux"
    )
    verify_lock_inputs(ROOT, target)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--require-hashes",
            "--only-binary=:all:",
            "-r",
            str(ROOT / "requirements" / f"{target}-py312.lock"),
        ],
        check=True,
    )
    packages = [ROOT / "apps/api"]
    if args.dev or sys.platform == "win32":
        packages.append(ROOT / "apps/edge-gateway")
    for package in packages:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--no-build-isolation",
                "-e",
                str(package),
            ],
            check=True,
        )
    subprocess.run([sys.executable, "-m", "pip", "check"], check=True)


if __name__ == "__main__":
    main()
