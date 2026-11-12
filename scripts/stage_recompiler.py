#!/usr/bin/env python3
"""Stage the ROM-free GB Recompiled executable and runtime into the app bundle."""
from __future__ import annotations

import hashlib
import os
import shutil
import tarfile
import urllib.request
import zipfile
from pathlib import Path

VERSION = "v0.1.0"
BASE = f"https://github.com/arcanite24/gb-recompiled/releases/download/{VERSION}"
ASSETS = {
    ("Darwin", "arm64"): "gb-recompiled-macos-arm64.tar.gz",
    ("Darwin", "aarch64"): "gb-recompiled-macos-arm64.tar.gz",
    ("Darwin", "x86_64"): "gb-recompiled-macos-x64.tar.gz",
    ("Darwin", "amd64"): "gb-recompiled-macos-x64.tar.gz",
    ("Linux", "x86_64"): "gb-recompiled-linux-x64.tar.gz",
    ("Linux", "amd64"): "gb-recompiled-linux-x64.tar.gz",
    ("Windows", "amd64"): "gb-recompiled-windows-x64.zip",
    ("Windows", "x86_64"): "gb-recompiled-windows-x64.zip",
}
ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "vendor-tools" / "gb-recompiled"
CACHE = ROOT / ".build-deps"
SHA256 = {
    "gb-recompiled-linux-x64.tar.gz": "b77fbf8913a9dd770097df81e8e0f84cf2e0d9e3a44dc1a1ee4d1846c5035535",
    "gb-recompiled-macos-arm64.tar.gz": "3881d643d0f7bf2eaa6ba83140b66c7de9b564eb70eba92f81f41d14d91758f9",
    "gb-recompiled-macos-x64.tar.gz": "916ebdfefb0952fa8abed0bf985bd63b500033cd3bce5ad565434079d0ae3e77",
    "gb-recompiled-windows-x64.zip": "81d67729a4bbefc4e7247e9fbf53f2909ee74bb77f6d1daacf3d1920ea245269",
}


def download(url: str, destination: Path) -> None:
    temporary = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(
        url, headers={"User-Agent": "PokemonPinballRecompiled-build"}
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        with temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
    temporary.replace(destination)


def main() -> int:
    import platform

    key = (platform.system(), platform.machine().lower())
    asset = ASSETS.get(key)
    if not asset:
        raise RuntimeError(f"No upstream recompiler package for {key}")

    CACHE.mkdir(parents=True, exist_ok=True)
    archive = CACHE / asset
    if not archive.is_file():
        download(BASE + "/" + asset, archive)

    expected = SHA256[asset]
    actual = hashlib.sha256(archive.read_bytes()).hexdigest()
    if actual != expected:
        archive.unlink(missing_ok=True)
        raise RuntimeError(f"SHA256 mismatch for upstream recompiler {asset}")

    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    if asset.endswith(".zip"):
        with zipfile.ZipFile(archive) as package:
            package.extractall(DEST)
    else:
        with tarfile.open(archive, "r:gz") as package:
            package.extractall(DEST, filter="data")

    expected_exe = "gbrecomp.exe" if os.name == "nt" else "gbrecomp"
    executables = list(DEST.rglob(expected_exe))
    if len(executables) != 1:
        raise RuntimeError(
            f"Expected one {expected_exe} in upstream archive; found {len(executables)}"
        )
    executable = executables[0]
    runtime_candidates = [
        executable.parent / "runtime",
        executable.parent.parent / "runtime",
        executable.parent.parent.parent / "runtime",
    ]
    if not any(
        (runtime / "include" / "gbrt.h").is_file()
        and (runtime / "src" / "gbrt.c").is_file()
        and (runtime / "vendor" / "imgui" / "imgui.cpp").is_file()
        for runtime in runtime_candidates
    ):
        raise RuntimeError("Upstream recompiler archive did not include its runtime")
    if os.name != "nt":
        executable.chmod(executable.stat().st_mode | 0o111)
    print("Bundled ROM-free recompiler:", executable)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
