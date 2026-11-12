#!/usr/bin/env python3
"""Build Pokémon Pinball locally from a ROM supplied by the user.

The ROM and generated game sources stay on the user's computer.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

RECOMP_VERSION = "v0.1.0"
RECOMP_RELEASE_BASE = (
    "https://github.com/arcanite24/gb-recompiled/releases/download/"
    + RECOMP_VERSION
)

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


def run_command(command: list[str], *, cwd: Path | None = None,
                env: dict[str, str] | None = None) -> None:
    print("\n> " + subprocess.list2cmdline(command), flush=True)
    subprocess.run(command, cwd=str(cwd) if cwd else None, env=env, check=True)


def find_recompiler(root: Path) -> Path | None:
    expected = "gbrecomp.exe" if os.name == "nt" else "gbrecomp"
    candidates = [p for p in root.rglob(expected) if p.is_file()]
    if not candidates:
        return None
    candidates.sort(key=lambda p: (len(p.parts), str(p)))
    executable = candidates[0]
    if os.name != "nt":
        executable.chmod(executable.stat().st_mode | 0o111)
    return executable


def platform_asset() -> str:
    system = platform.system()
    machine = platform.machine().lower()
    asset = ASSETS.get((system, machine))
    if not asset:
        supported = (
            "macOS arm64/x86_64, Windows x64, and Linux x86_64"
        )
        raise RuntimeError(
            "No upstream prebuilt recompiler archive is available for "
            + system + "/" + machine + ". Supported hosts: " + supported
        )
    return asset


def download_recompiler() -> Path:
    override = os.environ.get("GBRECOMP")
    if override:
        path = Path(override).expanduser().resolve()
        if not path.is_file():
            raise RuntimeError("GBRECOMP does not point to a file: " + str(path))
        return path

    # Reuse the exact local build used for the initial Apple-silicon test.
    if platform.system() == "Darwin":
        local = (
            Path.home()
            / "Tools"
            / "GBRecompiled"
            / "build"
            / "bin"
            / "gbrecomp"
        )
        if local.is_file():
            return local

    asset = platform_asset()
    cache = (
        Path.home()
        / ".cache"
        / "PokemonPinballRecompiled"
        / RECOMP_VERSION
    )
    cache.mkdir(parents=True, exist_ok=True)
    extracted = cache / "tool"
    existing = find_recompiler(extracted) if extracted.exists() else None
    if existing:
        return existing

    archive = cache / asset
    if not archive.exists():
        url = RECOMP_RELEASE_BASE + "/" + asset
        temporary = archive.with_suffix(archive.suffix + ".part")
        print("Downloading the ROM-free GB Recompiled tool: " + asset)
        request = urllib.request.Request(
            url, headers={"User-Agent": "PokemonPinballRecompiled-local-builder"}
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            with temporary.open("wb") as output:
                shutil.copyfileobj(response, output)
        temporary.replace(archive)

    if extracted.exists():
        shutil.rmtree(extracted)
    extracted.mkdir(parents=True)

    if asset.endswith(".zip"):
        with zipfile.ZipFile(archive) as package:
            package.extractall(extracted)
    else:
        with tarfile.open(archive, "r:gz") as package:
            package.extractall(extracted)

    executable = find_recompiler(extracted)
    if not executable:
        raise RuntimeError(
            "The downloaded archive did not contain " +
            ("gbrecomp.exe" if os.name == "nt" else "gbrecomp")
        )
    return executable


def choose_sdl2_root(argument: str | None) -> Path | None:
    candidate = argument or os.environ.get("SDL2_ROOT")
    if not candidate and platform.system() == "Darwin":
        default = Path.home() / "Tools" / "SDL2"
        if default.is_dir():
            candidate = str(default)
    if candidate:
        root = Path(candidate).expanduser().resolve()
        if not root.is_dir():
            raise RuntimeError("SDL2 root directory not found: " + str(root))
        return root
    return None


def prepare_work_directory(work_dir: Path) -> None:
    marker = work_dir / ".pokemon-pinball-builder"
    if work_dir.exists() and not marker.exists():
        if any(work_dir.iterdir()):
            raise RuntimeError(
                "Refusing to reuse a non-empty folder not created by this "
                "builder: " + str(work_dir) + ". Choose --work-dir."
            )
    work_dir.mkdir(parents=True, exist_ok=True)
    marker.write_text(
        "This directory is reserved for local Pokémon Pinball build output.\n",
        encoding="utf-8",
    )


def find_game_executable(build_dir: Path, generated_name: str) -> Path:
    names = [generated_name]
    if os.name == "nt":
        names.insert(0, generated_name + ".exe")
    for name in names:
        for candidate in (build_dir / name, build_dir / "bin" / name):
            if candidate.is_file():
                return candidate

    candidates: list[Path] = []
    for candidate in build_dir.rglob("*"):
        if not candidate.is_file() or "CMakeFiles" in candidate.parts:
            continue
        if os.name == "nt":
            if candidate.suffix.lower() == ".exe":
                candidates.append(candidate)
        elif candidate.suffix == "" and os.access(candidate, os.X_OK):
            candidates.append(candidate)

    if candidates:
        candidates.sort(key=lambda p: (len(p.parts), str(p)))
        return candidates[0]
    raise RuntimeError(
        "CMake completed, but the game executable was not found under "
        + str(build_dir)
    )


def runtime_environment(sdl2_root: Path | None, binary: Path) -> dict[str, str]:
    env = os.environ.copy()
    library_dirs: list[str] = []
    if sdl2_root:
        for relative in ("lib", "lib64", "bin", "lib/x64"):
            candidate = sdl2_root / relative
            if candidate.is_dir():
                library_dirs.append(str(candidate))

    vcpkg_root = os.environ.get("VCPKG_ROOT")
    if vcpkg_root and os.name == "nt":
        vcpkg_bin = Path(vcpkg_root) / "installed" / "x64-windows" / "bin"
        if vcpkg_bin.is_dir():
            library_dirs.append(str(vcpkg_bin))

    if os.name == "nt":
        env["PATH"] = os.pathsep.join(
            library_dirs + [str(binary.parent), env.get("PATH", "")]
        )
    elif platform.system() == "Darwin":
        env["DYLD_LIBRARY_PATH"] = os.pathsep.join(
            library_dirs + [env.get("DYLD_LIBRARY_PATH", "")]
        )
    else:
        env["LD_LIBRARY_PATH"] = os.pathsep.join(
            library_dirs + [env.get("LD_LIBRARY_PATH", "")]
        )
    return env


def apply_pokemon_pinball_enhancements(generated: Path) -> None:
    """Patch the generated local runtime with the optional widescreen backdrop.

    The original 160x144 game viewport remains unchanged. The effect only fills
    unused display space with a dimmed, linearly scaled copy of the current frame.
    """
    runtime_source = generated / "runtime" / "src" / "platform_sdl.cpp"
    if not runtime_source.is_file():
        raise RuntimeError(
            "Generated SDL runtime source was not found: " + str(runtime_source)
        )

    source = runtime_source.read_text(encoding="utf-8")
    if "POKEMON_PINBALL_WIDESCREEN_BACKDROP" in source:
        print("Widescreen backdrop enhancement is already applied.")
        return

    replacements = [
        (
            "static GBRenderFilterMode g_render_filter_mode = GB_RENDER_FILTER_NEAREST;\n",
            (
                "static GBRenderFilterMode g_render_filter_mode = GB_RENDER_FILTER_NEAREST;\n"
                "/* POKEMON_PINBALL_WIDESCREEN_BACKDROP: optional side-fill effect. */\n"
                "static bool g_widescreen_backdrop = false;\n"
            ),
            "runtime display-state declaration",
        ),
        (
            "                bool is_keyboard = strncmp(key, \"keyboard.\", 9) == 0;\n",
            (
                "                if (strcmp(key, \"display.widescreen_backdrop\") == 0) {\n"
                "                    g_widescreen_backdrop = (strcmp(value, \"0\") != 0);\n"
                "                    continue;\n"
                "                }\n"
                "\n"
                "                bool is_keyboard = strncmp(key, \"keyboard.\", 9) == 0;\n"
            ),
            "runtime preference loading",
        ),
        (
            "    fprintf(file, \"savestate.slot=%d\\n\", g_savestate_slot);\n",
            (
                "    fprintf(file, \"savestate.slot=%d\\n\", g_savestate_slot);\n"
                "    fprintf(file, \"display.widescreen_backdrop=%d\\n\",\n"
                "            g_widescreen_backdrop ? 1 : 0);\n"
            ),
            "runtime preference saving",
        ),
        (
            "            update_render_filter();\n"
            "        }\n"
            "\n"
            "        if (!g_fullscreen) {\n"
            "            int scale_idx = g_scale - 1;",
            (
                "            update_render_filter();\n"
                "        }\n"
                "\n"
                "        /* POKEMON_PINBALL_WIDESCREEN_BACKDROP */\n"
                "        if (ImGui::Checkbox(\"Widescreen Backdrop\", &g_widescreen_backdrop)) {\n"
                "            save_runtime_preferences();\n"
                "        }\n"
                "        ImGui::TextDisabled(\n"
                "            \"Fills unused widescreen space with a dimmed copy of the current frame.\");\n"
                "\n"
                "        if (!g_fullscreen) {\n"
                "            int scale_idx = g_scale - 1;"
            ),
            "graphics settings UI",
        ),
        (
            "    SDL_RenderClear(g_renderer);\n"
            "    SDL_RenderCopy(g_renderer, g_texture, NULL, &g_game_viewport);",
            (
                "    SDL_RenderClear(g_renderer);\n"
                "    if (g_widescreen_backdrop) {\n"
                "        int backdrop_width = 0;\n"
                "        int backdrop_height = 0;\n"
                "        SDL_GetWindowSize(g_window, &backdrop_width, &backdrop_height);\n"
                "        if (backdrop_width > 0 && backdrop_height > 0) {\n"
                "            SDL_Rect backdrop = {0, 0, backdrop_width, backdrop_height};\n"
                "            SDL_SetTextureColorMod(g_texture, 36, 44, 40);\n"
                "#if SDL_VERSION_ATLEAST(2, 0, 12)\n"
                "            SDL_SetTextureScaleMode(g_texture, SDL_ScaleModeLinear);\n"
                "#endif\n"
                "            SDL_RenderCopy(g_renderer, g_texture, NULL, &backdrop);\n"
                "            SDL_SetTextureColorMod(g_texture, 255, 255, 255);\n"
                "            update_render_filter();\n"
                "        }\n"
                "    }\n"
                "    SDL_RenderCopy(g_renderer, g_texture, NULL, &g_game_viewport);"
            ),
            "frame presentation",
        ),
    ]

    for old, new, label in replacements:
        count = source.count(old)
        if count != 1:
            raise RuntimeError(
                "Cannot safely apply widescreen enhancement: expected exactly "
                + "one " + label + " anchor, found " + str(count)
            )
        source = source.replace(old, new, 1)

    runtime_source.write_text(source, encoding="utf-8")
    print("Applied optional Widescreen Backdrop to the generated runtime.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Generate and build Pokémon Pinball locally from a user-supplied "
            "Game Boy or Game Boy Color ROM."
        )
    )
    parser.add_argument(
        "rom", nargs="?",
        help="path to your locally stored .gb or .gbc ROM",
    )
    parser.add_argument(
        "--work-dir",
        default=str(Path.home() / "PokemonPinballRecompiledBuild"),
        help="local output directory (default: ~/PokemonPinballRecompiledBuild)",
    )
    parser.add_argument(
        "--sdl2-root",
        help="SDL2 development package root; may also be set with SDL2_ROOT",
    )
    parser.add_argument(
        "--jobs", type=int,
        default=max(1, min(os.cpu_count() or 4, 4)),
        help="parallel build jobs (default: up to 4)",
    )
    parser.add_argument(
        "--no-run", action="store_true",
        help="compile the game but do not launch it",
    )
    args = parser.parse_args()

    rom_text = args.rom
    if not rom_text:
        rom_text = input(
            "Path to your legally obtained Pokémon Pinball .gb/.gbc file: "
        ).strip().strip('"').strip("'")
    if not rom_text:
        raise RuntimeError("No ROM path was supplied.")

    rom = Path(rom_text).expanduser().resolve()
    if not rom.is_file():
        raise RuntimeError("ROM file not found: " + str(rom))
    if rom.suffix.lower() not in (".gb", ".gbc"):
        raise RuntimeError("Expected a .gb or .gbc ROM file.")
    if args.jobs < 1:
        raise RuntimeError("--jobs must be at least 1.")

    for tool in ("cmake", "ninja"):
        if not shutil.which(tool):
            raise RuntimeError(
                tool + " was not found on PATH. Install it before building."
            )

    sdl2_root = choose_sdl2_root(args.sdl2_root)
    recompiler = download_recompiler()

    work_dir = Path(args.work_dir).expanduser().resolve()
    prepare_work_directory(work_dir)
    generated = work_dir / "generated"
    if generated.exists():
        shutil.rmtree(generated)
    build_dir = generated / "build"

    print("\nUsing local ROM: " + rom.name)
    print("Recompiler: " + str(recompiler))
    print("Build output: " + str(work_dir))
    print("The ROM is read locally and is not copied into this repository.")

    run_command(
        [
            str(recompiler),
            str(rom),
            "-o",
            str(generated),
            "-j",
            str(args.jobs),
            "--verbose",
        ]
    )

    apply_pokemon_pinball_enhancements(generated)

    cmake_command = [
        "cmake",
        "-G",
        "Ninja",
        "-S",
        str(generated),
        "-B",
        str(build_dir),
    ]
    if sdl2_root:
        cmake_command.append("-DCMAKE_PREFIX_PATH=" + str(sdl2_root))

    if os.name == "nt":
        vcpkg_root = os.environ.get("VCPKG_ROOT")
        if vcpkg_root:
            toolchain = (
                Path(vcpkg_root)
                / "scripts"
                / "buildsystems"
                / "vcpkg.cmake"
            )
            if toolchain.is_file():
                cmake_command.append(
                    "-DCMAKE_TOOLCHAIN_FILE=" + str(toolchain)
                )
                cmake_command.append("-DVCPKG_TARGET_TRIPLET=x64-windows")

    run_command(cmake_command)
    run_command(
        ["cmake", "--build", str(build_dir), "--parallel", str(args.jobs)]
    )

    executable = find_game_executable(build_dir, generated.name)
    print("\nBuild successful: " + str(executable))

    if not args.no_run:
        print("Launching the game. Local saves remain in: " + str(work_dir))
        run_command(
            [str(executable)],
            cwd=work_dir,
            env=runtime_environment(sdl2_root, executable),
        )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except subprocess.CalledProcessError as error:
        print("\nBuild command failed with exit code " + str(error.returncode))
        raise SystemExit(error.returncode or 1)
    except (OSError, RuntimeError, tarfile.TarError, zipfile.BadZipFile) as error:
        print("\nError: " + str(error), file=sys.stderr)
        raise SystemExit(1)
