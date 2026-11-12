# Pokémon Pinball Recompiled

A public, source-first local build project for Pokémon Pinball (Game Boy Color).

**This repository does not contain the game ROM, generated ROM-derived source, or a prebuilt copy of the game.** Each player supplies a legally obtained .gb, .gbc, or .sgb file on their own computer. The launcher reads that local file, generates the C project locally, compiles it, and launches the result. The ROM is not uploaded to GitHub or sent to this project.

## Desktop launcher

Download a platform launcher from the [GitHub Releases page](https://github.com/nvd123-YT/PokemonPinballRecompiled/releases). Each successful build has its own release (for example, `Build #16`) and separate download counters, so older build statistics are preserved:

- **macOS Apple silicon:** `PokemonPinballRecompiled-macos-arm64.dmg`
- **Windows x64:** `PokemonPinballRecompiled.exe`
- **Linux x64:** `PokemonPinballRecompiled-linux-x86_64.AppImage`

Open the launcher, select your local Game Boy/Game Boy Color ROM, choose a build folder, and click **Build & Play**. The launcher remembers the selected paths. After the first successful build, use **Play Existing Build** to start it again without recompiling.

The launcher package contains no game ROM, generated game code, or game executable. It does include the ROM-free GB Recompiled tool, CMake, Ninja, the Zig C/C++ compiler toolchain, and a platform-matched SDL2 development SDK. These are extracted privately by the launcher and used to generate and compile the game locally. No separate Python, CMake, Ninja, Zig, SDL2 SDK, Visual Studio, or vcpkg installation is required on Windows or Linux.

### Build prerequisites

**Windows x64 and Linux x64**
- No separate compiler or build-system installation is required; the launcher bundles those tools and its SDL2 SDK.
- A normal desktop environment with the platform's graphics/audio runtime libraries is still required to run the game.

**macOS Apple silicon**
- Xcode Command Line Tools are required for Apple's macOS system SDK and frameworks. Install them with `xcode-select --install` if they are not already present.
- CMake, Ninja, Zig, the GB recompiler, and SDL2 development files are bundled with the launcher.

The Apple SDK is provided by Apple and is not redistributed inside this project. The launcher checks for it before configuring the native build and displays an actionable message if it is missing.

**Building from a source checkout**
- Install Python 3.12, CMake, Ninja, and the Zig toolchain.
- Build or install SDL2 development files for your platform, then run `python3 launcher.py` or `python3 build.py "/path/to/your/Pokemon Pinball.gbc"`.

## Graphics and runtime enhancements

While the game is running, press **F10** or **Escape** to open the built-in runtime settings.

- **Fullscreen:** uses the current desktop display mode. On a compatible 8K display and graphics system, the game can be presented at the display's 8K output resolution.
- **Widescreen Backdrop:** an optional dimmed, softly scaled copy of the current frame fills unused widescreen space while the original playfield stays centered and undistorted. The setting is saved between launches.
- **Scaling Mode:** Pixel Perfect, Aspect Fit, Aspect Fill, and Stretch.
- **Scale Filter:** Nearest for crisp pixel art or Linear for smoother scaling.
- **Runtime:** V-Sync, performance overlay, slow-frame smoothing, and adjustable speed.
- **Audio:** enable/disable output, mute, volume, latency, and output-device selection.
- **Controls:** remap keyboard and controller actions.
- **Persistence:** battery saves and ten savestate slots.

**Important resolution note:** the original Game Boy frame is 160×144 pixels. Fullscreen uses the current desktop display mode, so output can reach 4K or 8K on a compatible monitor/GPU/OS setup. That is output upscaling, not newly generated HD artwork or additional game detail. The Widescreen Backdrop fills unused screen space without changing the playfield. Aspect Fit shows the complete image without distortion; Aspect Fill fills the display by cropping part of the image; Stretch fills the display but distorts the original aspect ratio. None of these modes expands the game's original playfield or viewing area.

## Build from source

Install Python 3, CMake, Ninja, a C/C++ compiler, and SDL2 development files, then run:

    python3 launcher.py

Or build without the GUI:

    python3 build.py "/path/to/your/Pokemon Pinball.gbc"

Generated source and build products are kept outside this Git repository by default, under:

    ~/PokemonPinballRecompiledBuild/

Use `python3 build.py --help` for command-line options.

## GitHub Actions

Every push to `main` validates and packages the standalone launcher for macOS arm64, Windows x64, and Linux x64. Each successful main-branch build creates a new immutable, uniquely tagged GitHub Release (`build-<run number>`) with its own assets and download counters. Existing releases are not overwritten. Pull requests run validation and packaging checks but do not publish releases.

The release contains the launcher only. It does not build or publish the game because GitHub runners do not receive a user's local ROM.

## Compatibility and scope

The upstream GB Recompiled project supplies the static recompiler and SDL2-based Game Boy runtime. This project has been confirmed to generate and run the game on an Apple-silicon Mac. Windows and Linux game builds still need independent testing.

This is an unofficial fan project and is not affiliated with or endorsed by Nintendo, The Pokémon Company, Game Freak, or Creatures. Pokémon and related marks are the property of their respective owners. Users are responsible for obtaining and using ROM images lawfully.

The macOS package is ad-hoc signed by CI but is not Developer ID signed or notarized. Windows builds are also unsigned; operating systems may display their normal first-run security warnings.

## Upstream

- GB Recompiled: https://github.com/arcanite24/gb-recompiled
- GB Recompiled releases: https://github.com/arcanite24/gb-recompiled/releases
