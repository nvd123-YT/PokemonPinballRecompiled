# Pokémon Pinball Recompiled

A public, source-first local build project for Pokémon Pinball (Game Boy Color).

**This repository does not contain the game ROM, generated ROM-derived source, or a prebuilt copy of the game.** Each player supplies a legally obtained .gb or .gbc file on their own computer. The builder reads that local file, generates the C project locally, compiles it, and launches the result. The ROM is not uploaded to GitHub or sent to this project.

## Quick start

### macOS (Apple silicon or Intel)

Install or make available:

- Xcode Command Line Tools (Clang)
- CMake 3.20 or newer
- Ninja
- Python 3
- SDL2 development files

Your local SDL2 installation can be selected with the SDL2_ROOT environment variable. The builder automatically checks ~/Tools/SDL2, which is useful for the setup used during this project's initial macOS test.

From a Terminal in this repository:

    python3 build.py "/path/to/your/Pokemon Pinball.gbc"

Or:

    SDL2_ROOT="$HOME/Tools/SDL2" python3 build.py "/path/to/your/Pokemon Pinball.gbc"

The builder reuses ~/Tools/GBRecompiled/build/bin/gbrecomp when it exists. Otherwise, it downloads the ROM-free GB Recompiled 0.1.0 tool archive for your Mac architecture.

### Windows x64

Install:

- Python 3
- CMake 3.20 or newer
- Ninja
- Visual Studio 2022 with the Desktop development with C++ workload
- vcpkg and the SDL2 development package

In a Visual Studio Developer PowerShell, install SDL2 for x64:

    vcpkg install sdl2:x64-windows

Set VCPKG_ROOT to your vcpkg directory, then run:

    .\build-windows.ps1 "C:\Games\Pokemon Pinball.gbc"

The builder uses the upstream Windows x64 recompiler package. The ROM remains on your PC.

### Linux x64 (Ubuntu/Debian)

Install the build dependencies:

    sudo apt update
    sudo apt install python3 cmake ninja-build build-essential libsdl2-dev

Then run:

    python3 build.py "$HOME/Games/Pokemon Pinball.gbc"

The builder uses the upstream Linux x64 recompiler package.

## Output and saves

Generated source and build products are kept outside this Git repository, under:

    ~/PokemonPinballRecompiledBuild/

The builder only replaces its own generated project folder during a rebuild. It launches the game with the build directory as its working directory so runtime save files remain in the surrounding build folder rather than being committed to Git.

Use --no-run to compile without launching, --jobs N to set the build parallelism, --sdl2-root PATH to select SDL2, and --work-dir PATH to choose another output folder. Run:

    python3 build.py --help

## What the public GitHub workflow does

GitHub Actions checks the Python builder and the platform launch scripts on macOS, Windows, and Linux. It does not build or release the game: a public runner does not have your local ROM, and this repository intentionally never stores one. The actual game generation and compilation happen on each player's computer.

## Compatibility and scope

The upstream GB Recompiled project supplies the static recompiler and SDL2-based Game Boy runtime. Its published 0.1.0 tool archives cover macOS Apple silicon, macOS Intel, Windows x64, and Linux x64. This project has been confirmed to generate and run the game on the developer's Apple-silicon Mac; Windows and Linux builds still need independent testing.

This is an unofficial fan project and is not affiliated with or endorsed by Nintendo, The Pokémon Company, Game Freak, or Creatures. Pokémon and related marks are the property of their respective owners. Users are responsible for obtaining and using ROM images lawfully.

## Upstream

- GB Recompiled: https://github.com/arcanite24/gb-recompiled
- GB Recompiled releases: https://github.com/arcanite24/gb-recompiled/releases
