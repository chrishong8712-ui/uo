import re
import unittest

from core.razor_generator import ScriptGenerationError, generate_script, price_variables


def sample_prices() -> dict[str, int]:
    return {name: 1000 + index for index, name in enumerate(price_variables())}


class GenerateScriptTests(unittest.TestCase):
    def test_every_variable_is_declared_once_with_its_price(self):
        prices = sample_prices()
        text = generate_script(prices)
        for name, value in prices.items():
            with self.subTest(name=name):
                declarations = re.findall(rf"^setvar! {name} '(\d+)'$", text, re.M)
                self.assertEqual(declarations, [str(value)])

    def test_missing_price_raises(self):
        prices = sample_prices()
        prices.pop(price_variables()[0])
        with self.assertRaises(ScriptGenerationError):
            generate_script(prices)

    def test_unexpected_price_raises(self):
        prices = sample_prices()
        prices["UnknownPrice"] = 5
        with self.assertRaises(ScriptGenerationError):
            generate_script(prices)

    def test_invalid_value_raises(self):
        for bad in (True, -1, 1.5, "10"):
            with self.subTest(value=bad):
                prices = sample_prices()
                prices[price_variables()[0]] = bad
                with self.assertRaises(ScriptGenerationError):
                    generate_script(prices)

    def test_arcane_scroll_is_a_rare_item_declared_and_processed(self):
        text = generate_script(sample_prices())
        self.assertIn("setvar! ArcaneScrollPrice ", text)
        self.assertIn("'blank scroll%s%'", text)
        self.assertNotIn("setvar! ArcaneScrollPrice '30000'", text)

    def test_new_phylactery_and_variant_variables_are_generated(self):
        text = generate_script(sample_prices())
        for name in (
            "AgorawavePhylacteryPrice",
            "TemporalPhylacteryPrice",
            "AirPhylacteryPrice",
            "FirePhylacteryPrice",
            "AgorawaveCorePrice",
            "TemporalCorePrice",
            "AgorawaveDistillationPrice",
            "TemporalDistillationPrice",
        ):
            with self.subTest(name=name):
                self.assertIn(f"setvar! {name} ", text)

    def test_rare_items_are_declared_and_processed(self):
        text = generate_script(sample_prices())
        for name in ("SkillOrbPrice", "MastercraftingDiagramPrice", "ResearchMaterialsPrice", "ArcaneScrollPrice"):
            with self.subTest(name=name):
                self.assertIn(f"setvar! {name} ", text)
        self.assertIn("//Rare Items", text)
        self.assertIn("'void orb'", text)
        self.assertIn("'Book of Truth'", text)
        self.assertIn("'research materials'", text)

    def test_missing_rare_item_price_raises(self):
        prices = sample_prices()
        del prices["SkillOrbPrice"]
        with self.assertRaises(ScriptGenerationError):
            generate_script(prices)


class PlacementLayoutTests(unittest.TestCase):
    def test_placements_are_in_range_and_spaced_within_each_container(self):
        from core.razor_generator import (
            COORD_MAX,
            COORD_MIN,
            DECLARATION_SECTIONS,
            MIN_SPACING,
            PROCESSING_SECTIONS,
        )

        for section in set(DECLARATION_SECTIONS) | set(PROCESSING_SECTIONS):
            with self.subTest(container=section.container):
                placements = [p for loop in section.loops for p in loop.placements]
                for p in placements:
                    self.assertTrue(COORD_MIN <= p.x <= COORD_MAX)
                    self.assertTrue(COORD_MIN <= p.y <= COORD_MAX)
                for i, a in enumerate(placements):
                    for b in placements[i + 1:]:
                        distance = max(abs(a.x - b.x), abs(a.y - b.y))
                        self.assertGreaterEqual(distance, MIN_SPACING, (a, b))

    def test_rare_cloth_positions_are_in_range_and_spaced(self):
        from core.razor_generator import COORD_MAX, COORD_MIN, MIN_SPACING, rare_cloth_section

        placements = rare_cloth_section(list(range(2085, 2085 + 30))).loops[0].placements
        for a in placements:
            self.assertTrue(COORD_MIN <= a.x <= COORD_MAX and COORD_MIN <= a.y <= COORD_MAX)
        for i, a in enumerate(placements):
            for b in placements[i + 1:]:
                self.assertGreaterEqual(max(abs(a.x - b.x), abs(a.y - b.y)), MIN_SPACING)

    def test_phylactery_section_covers_every_aspect_except_chromatic(self):
        from core.razor_generator import PHYLACTERIES

        variables = {p.variable for loop in PHYLACTERIES.loops for p in loop.placements}
        self.assertNotIn("ChromaticPhylacteryPrice", variables)
        self.assertIn("AgorawavePhylacteryPrice", variables)
        self.assertIn("TemporalPhylacteryPrice", variables)
        self.assertEqual(len(variables), 25)

    def test_rare_cloth_section_is_dynamic_and_hue_based(self):
        hues = [2085, 2263]
        prices = {name: 1 for name in price_variables(hues)}
        script = generate_script(prices, hues)
        self.assertIn("while findtype 'folded cloth' backpack as item", script)
        self.assertIn("setvar! RareCloth2085Price '1'", script)
        self.assertIn("RareCloth2263Price", script)
        self.assertIn("hue 2085", script)
        self.assertNotIn("RareCloth2085Price", generate_script(
            {name: 1 for name in price_variables()}
        ))

    def test_duplicate_rare_cloth_hue_is_rejected(self):
        from core.razor_generator import ScriptGenerationError

        with self.assertRaises(ScriptGenerationError):
            generate_script({name: 1 for name in price_variables()}, [2085, 2085])


if __name__ == "__main__":
    unittest.main()
