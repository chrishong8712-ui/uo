import re
import unittest

from core.inventory_ocr import match_inventory_text, ocr_image, parse_region
from core.razor_generator import generate_script, price_variables


def sample_prices() -> dict[str, int]:
    return {name: 1000 + index for index, name in enumerate(price_variables())}


class MatchInventoryTextTests(unittest.TestCase):
    def test_duplicates_are_removed_and_order_follows_script(self):
        text = "\n".join(
            [
                "You have: plainly drawn map",
                "You have: Air",  # ambiguous, checked separately
                "You have: plainly drawn map",
                "You have: dull copper map",
            ]
        )
        result = match_inventory_text(text)
        self.assertEqual(result.owned, ["T1Price", "DullCopperOreMapPrice"])

    def test_longest_label_wins_over_shorter_label(self):
        result = match_inventory_text("dull copper ore map")
        self.assertEqual(result.owned, ["DullCopperOreMapPrice"])
        self.assertNotIn("CopperOreMapPrice", result.owned)

    def test_label_must_match_whole_word(self):
        result = match_inventory_text("coppery sheen")
        self.assertEqual(result.owned, [])
        self.assertEqual(result.unmapped, ["coppery sheen"])

    def test_ocr_inserted_space_inside_label_still_matches(self):
        result = match_inventory_text("lumber jacking")
        self.assertIn("LumberjackingPrice", result.owned)
        self.assertEqual(result.unmapped, [])

    def test_fixed_region_is_default_for_live_capture(self):
        from core.inventory_ocr import INVENTORY_REGION

        self.assertEqual(INVENTORY_REGION, (0, 300, 410, 720))

    def test_unmapped_lines_are_reported_not_defaulted(self):
        result = match_inventory_text("Item 0x1A2B\nplainly drawn map")
        self.assertEqual(result.owned, ["T1Price"])
        self.assertEqual(result.unmapped, ["Item 0x1A2B"])

    def test_label_shared_by_two_variables_is_ambiguous(self):
        result = match_inventory_text("Air")
        self.assertEqual(result.owned, [])
        self.assertEqual(
            result.ambiguous,
            [("Air", ("AirCorePrice", "AirDistillationPrice", "AirPhylacteryPrice"))],
        )

    def test_item_type_word_resolves_shared_label(self):
        result = match_inventory_text("a chromatic core\na chromatic distillation")
        self.assertEqual(result.ambiguous, [])
        self.assertEqual(result.owned, ["ChromaticCorePrice", "ChromaticDistillationPrice"])

    def test_blank_and_noise_lines_are_ignored(self):
        result = match_inventory_text("\n  \n.\nplainly drawn map\n")
        self.assertEqual(result.owned, ["T1Price"])
        self.assertEqual(result.unmapped, [])


class RareClothOcrTests(unittest.TestCase):
    def test_rare_cloth_is_identified_by_hue_number(self):
        result = match_inventory_text(
            "rare cloth (hue 2085: pulma)\nrare cloth (hue 2263: air aspect)"
        )
        self.assertEqual(list(result.rare_cloth), [2085, 2263])
        self.assertEqual(result.owned, [])
        self.assertEqual(result.ambiguous, [])

    def test_bracket_noise_and_spacing_still_read(self):
        result = match_inventory_text("rare cloth [hue 2653 : metallic lemon lime)")
        self.assertEqual(list(result.rare_cloth), [2653])

    def test_unreadable_hue_is_unmapped_not_guessed(self):
        result = match_inventory_text("rare cloth (hue 2O85: pulma)")
        self.assertEqual(result.rare_cloth, {})
        self.assertEqual(result.unmapped, ["rare cloth (hue 2O85: pulma)"])

    def test_live_message_keeps_parenthesized_name_and_drops_description(self):
        from core.inventory_ocr import InventoryAccumulator

        accumulator = InventoryAccumulator()
        accumulator.add_text("[Razor]: rare cloth (hue 2085: pulma) (used to dye)")
        self.assertEqual(accumulator.text(), "rare cloth (hue 2085: pulma)")
        self.assertEqual(list(accumulator.match().rare_cloth), [2085])


class OcrInjectionTests(unittest.TestCase):
    def test_injected_engine_replaces_tesseract(self):
        calls = []

        def fake_engine(image):
            calls.append(image)
            return "plainly drawn map"

        text = ocr_image("fake-image", engine=fake_engine)
        self.assertEqual(calls, ["fake-image"])
        self.assertEqual(match_inventory_text(text).owned, ["T1Price"])


class ParseRegionTests(unittest.TestCase):
    def test_valid_region(self):
        self.assertEqual(parse_region("10,20,300,80"), (10, 20, 300, 80))

    def test_invalid_region_raises(self):
        for value in ("10,20,300", "a,b,c,d", "0,0,0,10"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_region(value)


class ZeroFilledScriptTests(unittest.TestCase):
    def test_unowned_items_are_declared_as_zero_and_format_is_unchanged(self):
        owned = {"T1Price", "DullCopperOreMapPrice"}
        prices = {name: 0 for name in price_variables()}
        prices.update({"T1Price": 5000, "DullCopperOreMapPrice": 900})
        text = generate_script(prices)

        for name in price_variables():
            with self.subTest(name=name):
                values = re.findall(rf"^setvar! {name} '(\d+)'$", text, re.M)
                expected = prices[name]
                self.assertEqual(values, [str(expected)])
        self.assertEqual(
            len(re.findall(r"^setvar! \w+ '0'$", text, re.M)),
            len(price_variables()) - len(owned),
        )

    def test_zero_filled_script_has_same_line_layout_as_full_script(self):
        full = generate_script(sample_prices())
        zero_filled = {name: 0 for name in price_variables()}
        zero_filled["T1Price"] = 1234
        partial = generate_script(zero_filled)
        self.assertEqual(full.count("\n"), partial.count("\n"))


if __name__ == "__main__":
    unittest.main()
