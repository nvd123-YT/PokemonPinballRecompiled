#!/usr/bin/env python3
"""Desktop launcher for building and running a local Pokémon Pinball recomp."""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import build as builder


APP_NAME = "Pokémon Pinball Recompiled"
DEFAULT_WORK_DIR = Path.home() / "PokemonPinballRecompiledBuild"


def app_config_path() -> Path:
    if sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        root = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    folder = root / "PokemonPinballRecompiled"
    folder.mkdir(parents=True, exist_ok=True)
    return folder / "launcher.json"


def load_config() -> dict:
    try:
        value = json.loads(app_config_path().read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(value: dict) -> None:
    path = app_config_path()
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(path)


def launcher_environment(sdl2_root: str = "") -> dict[str, str]:
    env = os.environ.copy()
    path_entries: list[str] = []

    candidates = [
        Path.home() / "Tools" / "bin",
        Path.home() / ".local" / "bin",
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
        Path("/usr/bin"),
        Path("/bin"),
        Path("/Applications/CMake.app/Contents/bin"),
    ]
    for candidate in candidates:
        if candidate.is_dir():
            path_entries.append(str(candidate))

    existing = env.get("PATH", "")
    env["PATH"] = os.pathsep.join(path_entries + [existing])

    if sdl2_root.strip():
        env["SDL2_ROOT"] = str(Path(sdl2_root).expanduser())
    elif sys.platform == "darwin":
        default_sdl = Path.home() / "Tools" / "SDL2"
        if default_sdl.is_dir():
            env["SDL2_ROOT"] = str(default_sdl)

    return env


def internal_build_mode() -> bool:
    if len(sys.argv) >= 2 and sys.argv[1] == "--internal-build":
        sys.argv = ["build.py", *sys.argv[2:]]
        try:
            raise SystemExit(builder.main())
        except SystemExit:
            raise
        except Exception as exc:
            print("Build failed: " + str(exc), file=sys.stderr)
            raise SystemExit(1)
    return False


class Launcher:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(APP_NAME)
        self.root.minsize(700, 640)
        self.root.geometry("820x760")

        self.config = load_config()
        self.rom_var = tk.StringVar(value=self.config.get("rom", ""))
        self.work_var = tk.StringVar(
            value=self.config.get("work_dir", str(DEFAULT_WORK_DIR))
        )
        default_sdl = Path.home() / "Tools" / "SDL2"
        self.sdl_var = tk.StringVar(
            value=self.config.get(
                "sdl2_root",
                str(default_sdl) if default_sdl.is_dir() else "",
            )
        )
        self.status_var = tk.StringVar(value="Ready")
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.busy = False
        self.built_executable: Path | None = self.find_existing_build()

        self._build_ui()
        self.refresh_existing_state()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.root.after(100, self.process_events)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=20)
        outer.pack(fill=tk.BOTH, expand=True)

        heading = ttk.Frame(outer)
        heading.pack(fill=tk.X)
        ttk.Label(
            heading,
            text=APP_NAME,
            font=("TkDefaultFont", 20, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            heading,
            text="Build the game on this computer from your own ROM, then play.",
        ).pack(anchor=tk.W, pady=(4, 16))

        rom_frame = ttk.LabelFrame(outer, text="Game ROM", padding=12)
        rom_frame.pack(fill=tk.X, pady=(0, 10))
        rom_row = ttk.Frame(rom_frame)
        rom_row.pack(fill=tk.X)
        self.rom_entry = ttk.Entry(rom_row, textvariable=self.rom_var)
        self.rom_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.browse_rom_button = ttk.Button(
            rom_row, text="Browse…", command=self.browse_rom
        )
        self.browse_rom_button.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(
            rom_frame,
            text="Accepted files: .gb, .gbc and .sgb. The ROM stays on your computer.",
        ).pack(anchor=tk.W, pady=(7, 0))

        output_frame = ttk.LabelFrame(outer, text="Build location", padding=12)
        output_frame.pack(fill=tk.X, pady=(0, 10))
        output_row = ttk.Frame(output_frame)
        output_row.pack(fill=tk.X)
        ttk.Entry(output_row, textvariable=self.work_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        self.browse_work_button = ttk.Button(
            output_row, text="Choose…", command=self.browse_work_dir
        )
        self.browse_work_button.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(
            output_frame,
            text="Generated code, the executable, and local runtime files are kept here.",
        ).pack(anchor=tk.W, pady=(7, 0))

        sdk_frame = ttk.LabelFrame(outer, text="SDL2 development files (optional path)", padding=12)
        sdk_frame.pack(fill=tk.X, pady=(0, 10))
        sdk_row = ttk.Frame(sdk_frame)
        sdk_row.pack(fill=tk.X)
        ttk.Entry(sdk_row, textvariable=self.sdl_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        self.browse_sdl_button = ttk.Button(
            sdk_row, text="Choose…", command=self.browse_sdl_dir
        )
        self.browse_sdl_button.pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(
            sdk_frame,
            text="Leave blank to use SDL2 installed in a standard system location.",
        ).pack(anchor=tk.W, pady=(7, 0))

        actions = ttk.Frame(outer)
        actions.pack(fill=tk.X, pady=(4, 8))
        self.build_play_button = ttk.Button(
            actions, text="Build & Play", command=lambda: self.start_build(True)
        )
        self.build_play_button.pack(side=tk.LEFT)
        self.build_only_button = ttk.Button(
            actions, text="Build Only", command=lambda: self.start_build(False)
        )
        self.build_only_button.pack(side=tk.LEFT, padx=(8, 0))
        self.play_button = ttk.Button(
            actions, text="Play Existing Build", command=self.play_existing
        )
        self.play_button.pack(side=tk.LEFT, padx=(8, 0))
        self.open_folder_button = ttk.Button(
            actions, text="Open Build Folder", command=self.open_work_dir
        )
        self.open_folder_button.pack(side=tk.RIGHT)

        enhancement_frame = ttk.LabelFrame(outer, text="Graphics & gameplay enhancements", padding=12)
        enhancement_frame.pack(fill=tk.X, pady=(0, 10))
        ttk.Label(
            enhancement_frame,
            text=(
                "While the game is running, press F10 or Escape to open Settings. "
                "Choose Fullscreen and a Scaling Mode: Aspect Fit preserves the "
                "complete picture, Aspect Fill fills the display but crops the "
                "image, and Stretch fills the screen but distorts the original image."
            ),
            wraplength=740,
            justify=tk.LEFT,
        ).pack(anchor=tk.W)
        ttk.Label(
            enhancement_frame,
            text=(
                "The renderer can use your display's native fullscreen resolution, "
                "including 4K/8K displays when supported by your monitor and graphics "
                "driver. Scale Filter offers Nearest (sharp pixel art) or Linear "
                "(smoother scaling). Other runtime options include V-Sync, slow-frame "
                "smoothing, audio controls, speed controls, overlays, save states, "
                "and keyboard/controller remapping."
            ),
            wraplength=740,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(8, 0))
        ttk.Label(
            enhancement_frame,
            text=(
                "Resolution is output scaling: the original Game Boy frame remains "
                "160×144. It does not create new HD textures or extra game-world detail."
            ),
            wraplength=740,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(8, 0))

        status_frame = ttk.Frame(outer)
        status_frame.pack(fill=tk.X, pady=(2, 4))
        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT)
        ttk.Label(status_frame, textvariable=self.status_var).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        self.progress = ttk.Progressbar(outer, mode="indeterminate")
        self.progress.pack(fill=tk.X, pady=(0, 8))

        log_frame = ttk.LabelFrame(outer, text="Build log", padding=8)
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log = tk.Text(
            log_frame,
            height=12,
            wrap=tk.WORD,
            font=("TkFixedFont", 9),
            state=tk.DISABLED,
        )
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log.yview)
        self.log.configure(yscrollcommand=scrollbar.set)
        self.log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        footer = ttk.Label(
            outer,
            text=(
                "Unofficial fan project. No ROM, generated game source, or game "
                "binary is included in the launcher download."
            ),
            wraplength=740,
            justify=tk.LEFT,
        )
        footer.pack(anchor=tk.W, pady=(10, 0))

    def log_line(self, line: str) -> None:
        self.log.configure(state=tk.NORMAL)
        self.log.insert(tk.END, line)
        self.log.see(tk.END)
        self.log.configure(state=tk.DISABLED)

    def browse_rom(self) -> None:
        path = filedialog.askopenfilename(
            title="Choose your Game Boy / Game Boy Color ROM",
            filetypes=[
                ("Game Boy ROMs", "*.gb *.gbc *.sgb"),
                ("All files", "*"),
            ],
        )
        if path:
            self.rom_var.set(path)

    def browse_work_dir(self) -> None:
        path = filedialog.askdirectory(
            title="Choose build output folder",
            initialdir=str(Path(self.work_var.get()).expanduser()),
            mustexist=False,
        )
        if path:
            self.work_var.set(path)
            self.refresh_existing_state()

    def browse_sdl_dir(self) -> None:
        path = filedialog.askdirectory(
            title="Choose SDL2 development folder",
            initialdir=str(Path(self.sdl_var.get()).expanduser())
            if self.sdl_var.get().strip()
            else str(Path.home()),
            mustexist=True,
        )
        if path:
            self.sdl_var.set(path)

    def find_existing_build(self) -> Path | None:
        work_dir = Path(self.work_var.get()).expanduser()
        generated = work_dir / "generated"
        build_dir = generated / "build"
        if not build_dir.is_dir():
            return None
        try:
            return builder.find_game_executable(build_dir, generated.name)
        except RuntimeError:
            return None

    def refresh_existing_state(self) -> None:
        self.built_executable = self.find_existing_build()
        self.play_button.configure(
            state=tk.NORMAL if self.built_executable else tk.DISABLED
        )

    def set_busy(self, value: bool) -> None:
        self.busy = value
        state = tk.DISABLED if value else tk.NORMAL
        for widget in (
            self.rom_entry,
            self.browse_rom_button,
            self.browse_work_button,
            self.browse_sdl_button,
            self.build_play_button,
            self.build_only_button,
            self.play_button,
            self.open_folder_button,
        ):
            widget.configure(state=state)
        if value:
            self.progress.start(10)
        else:
            self.progress.stop()
            self.refresh_existing_state()

    def build_command(self, launch_after_build: bool) -> list[str]:
        rom = Path(self.rom_var.get().strip().strip('"')).expanduser()
        if not rom.is_file():
            raise RuntimeError("Choose an existing .gb, .gbc, or .sgb ROM first.")
        if rom.suffix.lower() not in (".gb", ".gbc", ".sgb"):
            raise RuntimeError("The selected file must have a .gb, .gbc, or .sgb extension.")

        work_text = self.work_var.get().strip()
        if not work_text:
            raise RuntimeError("Choose a build output folder.")
        work_dir = Path(work_text).expanduser()

        if getattr(sys, "frozen", False):
            command = [sys.executable, "--internal-build"]
        else:
            command = [sys.executable, str(Path(__file__).resolve()), "--internal-build"]

        command.extend([
            str(rom),
            "--work-dir",
            str(work_dir),
            "--no-run",
        ])
        if self.sdl_var.get().strip():
            command.extend(["--sdl2-root", str(Path(self.sdl_var.get()).expanduser())])
        return command

    def start_build(self, launch_after_build: bool) -> None:
        if self.busy:
            return
        try:
            command = self.build_command(launch_after_build)
        except RuntimeError as exc:
            messagebox.showerror(APP_NAME, str(exc), parent=self.root)
            return

        self.save_settings()
        self.log.configure(state=tk.NORMAL)
        self.log.delete("1.0", tk.END)
        self.log.configure(state=tk.DISABLED)
        self.status_var.set("Building from your local ROM…")
        self.set_busy(True)
        threading.Thread(
            target=self.build_worker,
            args=(command, launch_after_build),
            daemon=True,
        ).start()

    def build_worker(self, command: list[str], launch_after_build: bool) -> None:
        env = launcher_environment(self.sdl_var.get())
        try:
            self.events.put(("log", "Starting local ROM build.\n"))
            self.events.put(("log", "The ROM is not copied into the Git repository.\n\n"))
            process = subprocess.Popen(
                command,
                cwd=str(Path.home()),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                bufsize=1,
            )
            assert process.stdout is not None
            for line in process.stdout:
                self.events.put(("log", line))
            code = process.wait()
            if code != 0:
                self.events.put(("failed", f"Build failed with exit code {code}."))
                return

            work_dir = Path(self.work_var.get()).expanduser()
            generated = work_dir / "generated"
            executable = builder.find_game_executable(
                generated / "build", generated.name
            )
            self.events.put(("built", str(executable)))
            if launch_after_build:
                self.events.put(("launch", str(executable)))
            self.events.put(("complete", "Build finished."))
        except Exception as exc:
            self.events.put(("failed", "Build failed: " + str(exc)))

    def process_events(self) -> None:
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "log":
                    self.log_line(value)
                elif kind == "built":
                    self.built_executable = Path(value)
                    self.status_var.set("Build complete.")
                    self.log_line("\nBuild complete: " + value + "\n")
                elif kind == "launch":
                    self.launch_game(Path(value))
                elif kind == "complete":
                    self.status_var.set(value)
                    self.set_busy(False)
                elif kind == "failed":
                    self.status_var.set(value)
                    self.log_line("\n" + value + "\n")
                    self.set_busy(False)
                    messagebox.showerror(APP_NAME, value, parent=self.root)
        except queue.Empty:
            pass
        self.root.after(100, self.process_events)

    def play_existing(self) -> None:
        executable = self.find_existing_build()
        if not executable:
            messagebox.showinfo(
                APP_NAME,
                "No completed build was found. Select your ROM and choose Build & Play.",
                parent=self.root,
            )
            self.refresh_existing_state()
            return
        self.launch_game(executable)

    def launch_game(self, executable: Path) -> None:
        try:
            work_dir = Path(self.work_var.get()).expanduser()
            process = subprocess.Popen(
                [str(executable)],
                cwd=str(work_dir),
                env=launcher_environment(self.sdl_var.get()),
            )
            self.status_var.set("Game launched.")
            self.log_line("\nLaunched: " + str(executable) + "\n")
        except OSError as exc:
            messagebox.showerror(APP_NAME, "Could not launch the game:\n" + str(exc), parent=self.root)

    def open_work_dir(self) -> None:
        work_dir = Path(self.work_var.get()).expanduser()
        work_dir.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", str(work_dir)])
            elif os.name == "nt":
                os.startfile(str(work_dir))  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", str(work_dir)])
        except OSError as exc:
            messagebox.showerror(APP_NAME, "Could not open folder:\n" + str(exc), parent=self.root)

    def save_settings(self) -> None:
        save_config({
            "rom": self.rom_var.get(),
            "work_dir": self.work_var.get(),
            "sdl2_root": self.sdl_var.get(),
        })

    def on_close(self) -> None:
        if self.busy:
            if not messagebox.askyesno(
                APP_NAME,
                "A build is running. Close the launcher anyway?",
                parent=self.root,
            ):
                return
        self.save_settings()
        self.root.destroy()


def main() -> int:
    if len(sys.argv) >= 2 and sys.argv[1] == "--internal-build":
        internal_build_mode()
        return 0

    root = tk.Tk()
    Launcher(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
