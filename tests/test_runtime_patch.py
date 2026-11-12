from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from build import (
    apply_pokemon_pinball_enhancements,
    find_sdl2_cmake_dir,
    prepare_bundled_sdl2,
    create_zig_tool_wrappers,
    recompiler_has_runtime_snapshot,
)


class WidescreenRuntimePatchTests(unittest.TestCase):
    def fixture_source(self) -> str:
        return (
            "static GBRenderFilterMode g_render_filter_mode = GB_RENDER_FILTER_NEAREST;\n"
            "static void load_runtime_preferences(void) {\n"
            "                bool is_keyboard = strncmp(key, \"keyboard.\", 9) == 0;\n"
            "}\n"
            "static void save_runtime_preferences(void) {\n"
            "    fprintf(file, \"savestate.slot=%d\\n\", g_savestate_slot);\n"
            "}\n"
            "static void draw_settings(void) {\n"
            "            update_render_filter();\n"
            "        }\n"
            "\n"
            "        if (!g_fullscreen) {\n"
            "            int scale_idx = g_scale - 1;\n"
            "}\n"
            "static void draw_frame(void) {\n"
            "    SDL_RenderClear(g_renderer);\n"
            "    SDL_RenderCopy(g_renderer, g_texture, NULL, &g_game_viewport);\n"
            "}\n"
        )

    def test_patch_adds_backdrop_and_persistence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp) / "runtime" / "src"
            runtime.mkdir(parents=True)
            source = runtime / "platform_sdl.cpp"
            source.write_text(self.fixture_source(), encoding="utf-8")

            apply_pokemon_pinball_enhancements(Path(temp))
            result = source.read_text(encoding="utf-8")

            self.assertIn("static bool g_widescreen_backdrop = false;", result)
            self.assertIn('ImGui::Checkbox("Widescreen Backdrop"', result)
            self.assertIn("display.widescreen_backdrop=%d", result)
            self.assertIn("SDL_SetTextureColorMod(g_texture, 36, 44, 40)", result)
            self.assertIn("SDL_RenderCopy(g_renderer, g_texture, NULL, &g_game_viewport);", result)

    def test_patch_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp) / "runtime" / "src"
            runtime.mkdir(parents=True)
            source = runtime / "platform_sdl.cpp"
            source.write_text(self.fixture_source(), encoding="utf-8")

            apply_pokemon_pinball_enhancements(Path(temp))
            once = source.read_text(encoding="utf-8")
            apply_pokemon_pinball_enhancements(Path(temp))
            twice = source.read_text(encoding="utf-8")

            self.assertEqual(once, twice)
            self.assertEqual(twice.count("POKEMON_PINBALL_WIDESCREEN_BACKDROP"), 2)

    def test_missing_anchor_fails_without_partial_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            runtime = Path(temp) / "runtime" / "src"
            runtime.mkdir(parents=True)
            source = runtime / "platform_sdl.cpp"
            original = self.fixture_source().replace(
                "    SDL_RenderCopy(g_renderer, g_texture, NULL, &g_game_viewport);\n",
                "    SDL_RenderPresent(g_renderer);\n",
            )
            source.write_text(original, encoding="utf-8")

            with self.assertRaises(RuntimeError):
                apply_pokemon_pinball_enhancements(Path(temp))

            self.assertEqual(source.read_text(encoding="utf-8"), original)



class LocalBuildDependencyTests(unittest.TestCase):
    def test_finds_sdl2_cmake_package_in_common_sdk_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "lib" / "cmake" / "SDL2"
            package.mkdir(parents=True)
            (package / "SDL2Config.cmake").write_text("# SDL2 test package\\n")

            self.assertEqual(find_sdl2_cmake_dir(root), package)

    def test_recompiler_requires_adjacent_runtime_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            executable = root / "bin" / "gbrecomp"
            executable.parent.mkdir(parents=True)
            executable.write_text("test binary")
            self.assertFalse(recompiler_has_runtime_snapshot(executable))

            runtime = root / "runtime"
            (runtime / "include").mkdir(parents=True)
            (runtime / "src").mkdir(parents=True)
            (runtime / "vendor" / "imgui").mkdir(parents=True)
            (runtime / "include" / "gbrt.h").write_text("/* test */")
            (runtime / "src" / "gbrt.c").write_text("/* test */")
            (runtime / "vendor" / "imgui" / "imgui.cpp").write_text("// test")
            self.assertTrue(recompiler_has_runtime_snapshot(executable))


    def test_bundled_sdl2_is_copied_to_persistent_work_directory(self) -> None:
        import sys

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            extracted = root / "bundle"
            sdk = extracted / "vendor-tools" / "sdl2"
            config = sdk / "lib" / "cmake" / "SDL2" / "SDL2Config.cmake"
            config.parent.mkdir(parents=True)
            config.write_text("# relocatable sdk test\\n")
            old = getattr(sys, "_MEIPASS", None)
            sys._MEIPASS = str(extracted)
            try:
                persistent = prepare_bundled_sdl2(root / "work")
            finally:
                if old is None:
                    del sys._MEIPASS
                else:
                    sys._MEIPASS = old

            self.assertEqual(persistent, root / "work" / ".toolchain" / "sdl2")
            self.assertTrue((persistent / "lib" / "cmake" / "SDL2" / "SDL2Config.cmake").is_file())

    def test_zig_archiver_wrappers_are_created(self) -> None:
        import os

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            zig = root / ("zig.exe" if os.name == "nt" else "zig")
            zig.write_text("placeholder")
            ar, ranlib = create_zig_tool_wrappers(zig, root / "work")
            self.assertTrue(ar.is_file())
            self.assertTrue(ranlib.is_file())
            if os.name != "nt":
                self.assertTrue(ar.stat().st_mode & 0o111)
                self.assertTrue(ranlib.stat().st_mode & 0o111)



if __name__ == "__main__":
    unittest.main()
