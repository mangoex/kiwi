"""Compile target-specific Python 3.12 hashes from canonical project manifests.

Run with uv 0.12.24 installed in an isolated tooling environment. Local packages
are installed separately with --no-deps; they are never resolved from PyPI.
"""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    ("api-runtime-linux", "linux", False, False),
    ("dev-linux", "linux", True, True),
    ("gateway-runtime-windows", "windows", False, True),
    ("dev-windows", "windows", True, True),
)


def dependencies(dev: bool, gateway: bool, root: Path = ROOT) -> list[str]:
    paths = [root / "apps/api/pyproject.toml"]
    if gateway:
        paths.append(root / "apps/edge-gateway/pyproject.toml")
    result: list[str] = []
    for path in paths:
        project = tomllib.loads(path.read_text(encoding="utf-8"))["project"]
        result.extend(d for d in project["dependencies"] if not d.startswith("restaurant-os-api"))
        if dev:
            result.extend(project.get("optional-dependencies", {}).get("dev", []))
    # The editable-build backend is itself frozen, avoiding isolated build resolution.
    result.append("setuptools>=68")
    return sorted(set(result))


def input_digest(dev: bool, gateway: bool, root: Path = ROOT) -> str:
    return hashlib.sha256(("\n".join(dependencies(dev, gateway, root)) + "\n").encode()).hexdigest()


def main() -> None:
    version = subprocess.check_output(["uv", "--version"], text=True).strip()
    if version.split()[:2] != ["uv", "0.12.24"]:
        raise RuntimeError("Use the recorded compiler uv 0.12.24")
    destination = ROOT / "requirements"
    destination.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="restaurantos-locks-") as scratch:
        for name, platform, dev, gateway in TARGETS:
            source = Path(scratch) / "requirements.in"
            source.write_text("\n".join(dependencies(dev, gateway)) + "\n", encoding="utf-8")
            output = destination / f"{name}-py312.lock"
            subprocess.run(
                [
                    "uv",
                    "pip",
                    "compile",
                    str(source),
                    "--python-version",
                    "3.12",
                    "--python-platform",
                    platform,
                    "--generate-hashes",
                    "--no-header",
                    "--no-annotate",
                    "--output-file",
                    str(output),
                ],
                check=True,
            )
            content = output.read_text(encoding="utf-8")
            output.write_text(
                f"# RestaurantOS Python 3.12 / {name}; uv 0.12.24\n"
                f"# Input SHA256: {input_digest(dev, gateway)}\n"
                "# Sources: apps/api/pyproject.toml; gateway targets also use edge-gateway.\n"
                "# Regenerate: python scripts/compile_python_locks.py\n" + content,
                encoding="utf-8",
            )


if __name__ == "__main__":
    main()
