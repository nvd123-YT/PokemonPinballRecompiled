from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from build import apply_pokemon_pinball_enhancements


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


if __name__ == "__main__":
    unittest.main()
