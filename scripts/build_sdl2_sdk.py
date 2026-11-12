#!/usr/bin/env python3
"""Build a relocatable SDL2 development SDK for the launcher bundle.

The SDK is built on the matching GitHub Actions runner with the same bundled
Zig compiler that the desktop launcher will use for the user's local game build.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

SDL2_VERSION = "2.32.10"
SDL2_URL = (
    "https://github.com/libsdl-org/SDL/releases/download/"
    f"release-{SDL2_VERSION}/SDL2-{SDL2_VERSION}.tar.gz"
)
SDL2_SHA256 = "5f5993c530f084535c65a6879e9b26ad441169b3e25d789d83287040a9ca5165"
ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / ".build-deps"
TOOLS = ROOT / "vendor-tools"
SDK = TOOLS / "sdl2"


def run(command: list[str], *, cwd: Path | None = None) -> None:
    print("\n> " + subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=str(cwd) if cwd else None, check=True)


def executable(name: str) -> Path:
    found = shutil.which(name)
    if not found:
        raise RuntimeError(f"{name} is missing from the CI build environment")
    return Path(found).resolve()


def zig_executable() -> Path:
    spec = importlib.util.find_spec("ziglang")
    if spec is None or spec.origin is None:
        raise RuntimeError("Install the pinned ziglang Python package first")
    package = Path(spec.origin).resolve().parent
    name = "zig.exe" if os.name == "nt" else "zig"
    binary = package / name
    if not binary.is_file():
        raise RuntimeError(f"Zig compiler binary not found: {binary}")
    return binary


def download_source() -> Path:
    WORK.mkdir(parents=True, exist_ok=True)
    archive = WORK / f"SDL2-{SDL2_VERSION}.tar.gz"
    if not archive.is_file():
        temporary = archive.with_suffix(".part")
        request = urllib.request.Request(
            SDL2_URL, headers={"User-Agent": "PokemonPinballRecompiled-build"}
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            with temporary.open("wb") as output:
                shutil.copyfileobj(response, output)
        temporary.replace(archive)

    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != SDL2_SHA256:
        archive.unlink(missing_ok=True)
        raise RuntimeError(
            f"SDL2 source checksum mismatch: expected {SDL2_SHA256}, got {digest}"
        )

    extracted = WORK / f"SDL2-{SDL2_VERSION}"
    if not (extracted / "CMakeLists.txt").is_file():
        if extracted.exists():
            shutil.rmtree(extracted)
        extracted.mkdir(parents=True)
        with tarfile.open(archive, "r:gz") as package:
            package.extractall(extracted, filter="data")
        nested = extracted / f"SDL2-{SDL2_VERSION}"
        if nested.is_dir():
            return nested
    return extracted


def main() -> int:
    cmake = executable("cmake")
    ninja = executable("ninja")
    zig = zig_executable()
    source = download_source()

    if SDK.exists():
        shutil.rmtree(SDK)
    build = WORK / "sdl2-build"
    if build.exists():
        shutil.rmtree(build)

    configure = [
        str(cmake),
        "-G", "Ninja",
        "-DCMAKE_MAKE_PROGRAM=" + str(ninja),
        "-DCMAKE_BUILD_TYPE=Release",
        "-DCMAKE_INSTALL_PREFIX=" + str(SDK),
        "-DCMAKE_C_COMPILER=" + str(zig),
        "-DCMAKE_C_COMPILER_ARG1=cc",
        "-DCMAKE_CXX_COMPILER=" + str(zig),
        "-DCMAKE_CXX_COMPILER_ARG1=c++",
        "-DSDL_SHARED=ON",
        "-DSDL_STATIC=OFF",
        "-DSDL_TEST=OFF",
        "-DSDL_TESTS=OFF",
        "-DSDL_EXAMPLES=OFF",
        "-DSDL_INSTALL_TESTS=OFF",
        "-DSDL_INSTALL=ON",
        str(source),
        str(build),
    ]
    run(configure)
    run([
        str(cmake), "--build", str(build), "--parallel",
        str(max(1, min(os.cpu_count() or 4, 4))),
    ])
    run([str(cmake), "--install", str(build)])

    license_source = source / "LICENSE.txt"
    if not license_source.is_file():
        raise RuntimeError("SDL2 license file was not found in the pinned source")
    license_dir = SDK / "share" / "licenses" / "SDL2"
    license_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(license_source, license_dir / "LICENSE.txt")

    # The one-file launcher extracts SDK data into a temporary directory.
    # Materialize library symlinks now so the SDK remains portable when
    # PyInstaller packages it as ordinary application data.
    for path in list(SDK.rglob("*")):
        if path.is_symlink():
            target = path.resolve(strict=True)
            if target.is_file():
                payload = target.read_bytes()
                path.unlink()
                path.write_bytes(payload)

    config_names = ("SDL2Config.cmake", "sdl2-config.cmake", "SDL2-config.cmake")
    configs = [p for p in SDK.rglob("*") if p.is_file() and p.name in config_names]
    if not configs:
        raise RuntimeError("SDL2 installed, but no SDL2 CMake package was produced")

    print("\nSDL2 SDK installed at:", SDK)
    for config in configs:
        print("SDL2 CMake package:", config.parent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
