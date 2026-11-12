#!/usr/bin/env python3
"""Stage the official prebuilt SDL2 64-bit Visual C SDK for Windows.

The launcher uses Zig as its native compiler, so it only needs SDL2 headers,
the x64 import library, the runtime DLL, and a small relocatable CMake package.
This avoids rebuilding SDL2 itself on every Windows launcher release.
"""
from __future__ import annotations

import hashlib
import shutil
import urllib.request
import zipfile
from pathlib import Path

VERSION = "2.32.10"
ASSET = f"SDL2-devel-{VERSION}-VC.zip"
URL = f"https://github.com/libsdl-org/SDL/releases/download/release-{VERSION}/{ASSET}"
SHA256 = "af347939395a58b365846aaea27391e69f9ec9d4dd650d6ac40802159b418a6e"

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".build-deps"
SDK = ROOT / "vendor-tools" / "sdl2"


def download_archive() -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    archive = CACHE / ASSET
    if not archive.is_file():
        temporary = archive.with_suffix(".zip.part")
        request = urllib.request.Request(
            URL, headers={"User-Agent": "PokemonPinballRecompiled-build"}
        )
        print("Downloading official SDL2 Windows x64 SDK:", ASSET, flush=True)
        with urllib.request.urlopen(request, timeout=180) as response:
            with temporary.open("wb") as output:
                shutil.copyfileobj(response, output)
        temporary.replace(archive)

    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != SHA256:
        archive.unlink(missing_ok=True)
        raise RuntimeError(
            f"SDL2 SDK checksum mismatch: expected {SHA256}, got {digest}"
        )
    return archive


def safe_extract(archive: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as package:
        for member in package.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(destination.resolve()):
                raise RuntimeError("Unsafe path in SDL2 SDK archive: " + member.filename)
        package.extractall(destination)


def find_sdk_root(extracted: Path) -> Path:
    candidates = [p for p in extracted.rglob("SDL.h") if p.parent.name.lower() == "include"]
    for header in candidates:
        root = header.parent.parent
        import_library = root / "lib" / "x64" / "SDL2.lib"
        runtime_dll = root / "lib" / "x64" / "SDL2.dll"
        if import_library.is_file() and runtime_dll.is_file():
            return root
    raise RuntimeError(
        "Official SDL2 archive did not contain include/SDL.h, lib/x64/SDL2.lib, "
        "and lib/x64/SDL2.dll"
    )


def main() -> int:
    archive = download_archive()
    extracted = CACHE / "SDL2-windows-sdk"
    if extracted.exists():
        shutil.rmtree(extracted)
    safe_extract(archive, extracted)
    source = find_sdk_root(extracted)

    if SDK.exists():
        shutil.rmtree(SDK)
    SDK.mkdir(parents=True)
    shutil.copytree(source / "include", SDK / "include")
    shutil.copytree(source / "lib" / "x64", SDK / "lib" / "x64")

    dll = SDK / "lib" / "x64" / "SDL2.dll"
    (SDK / "bin").mkdir(parents=True, exist_ok=True)
    shutil.copy2(dll, SDK / "bin" / "SDL2.dll")

    cmake_dir = SDK / "lib" / "cmake" / "SDL2"
    cmake_dir.mkdir(parents=True, exist_ok=True)
    config = cmake_dir / "SDL2Config.cmake"
    config.write_text(
        """# Relocatable SDL2 package generated from the official Windows SDK.
get_filename_component(_SDL2_ROOT "\\${CMAKE_CURRENT_LIST_DIR}/../../.." ABSOLUTE)
set(SDL2_FOUND TRUE)
set(SDL2_INCLUDE_DIR "\\${_SDL2_ROOT}/include")
set(SDL2_INCLUDE_DIRS "\\${SDL2_INCLUDE_DIR}")
set(SDL2_LIBRARIES SDL2::SDL2)
if(NOT TARGET SDL2::SDL2)
  add_library(SDL2::SDL2 SHARED IMPORTED)
  set_target_properties(SDL2::SDL2 PROPERTIES
    INTERFACE_INCLUDE_DIRECTORIES "\\${SDL2_INCLUDE_DIR}"
    IMPORTED_IMPLIB "\\${_SDL2_ROOT}/lib/x64/SDL2.lib"
    IMPORTED_LOCATION "\\${_SDL2_ROOT}/bin/SDL2.dll"
  )
endif()
set(SDL2_SDL2_FOUND TRUE)
""".replace("\\${", "${"),
        encoding="utf-8",
    )

    license_candidates = list(source.glob("LICENSE*")) + list(source.glob("COPYING*"))
    license_dir = SDK / "share" / "licenses" / "SDL2"
    if license_candidates:
        license_dir.mkdir(parents=True, exist_ok=True)
        for candidate in license_candidates:
            if candidate.is_file():
                shutil.copy2(candidate, license_dir / candidate.name)

    if not config.is_file() or not (SDK / "include" / "SDL.h").is_file():
        raise RuntimeError("Failed to stage a complete SDL2 Windows SDK")

    print("Staged official SDL2 Windows SDK at:", SDK)
    print("SDL2 CMake package:", config)
    print("SDL2 import library:", SDK / "lib" / "x64" / "SDL2.lib")
    print("SDL2 runtime DLL:", SDK / "bin" / "SDL2.dll")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
