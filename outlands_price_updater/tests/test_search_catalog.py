import unittest

from core.rare_items import rare_item_for_variable
from core.search_catalog import default_search_spec


class DefaultSearchSpecTests(unittest.TestCase):
    def test_new_aspect_names_use_full_vendor_search_names(self):
        cases = {
            "AgorawaveCorePrice": "agorawave aspect core",
            "AgorawaveDistillationPrice": "agorawave aspect distillation",
            "AgorawavePhylacteryPrice": "agorawave phylactery",
            "TemporalCorePrice": "temporal aspect core",
            "TemporalDistillationPrice": "temporal aspect distillation",
            "TemporalPhylacteryPrice": "temporal phylactery",
        }
        for variable, expected in cases.items():
            with self.subTest(variable=variable):
                spec = default_search_spec(variable)
                self.assertEqual(spec.search, expected)
                self.assertEqual(spec.match, expected)

    def test_rare_cloth_matches_hue(self):
        spec = default_search_spec("RareCloth2085Price")
        self.assertEqual(spec.search, "rare cloth 2085")
        self.assertEqual(spec.match, "rare cloth (hue 2085:")

    def test_skill_orb_is_a_rare_item_with_its_own_search_term(self):
        spec = default_search_spec("SkillOrbPrice")
        self.assertEqual(spec.search, "skill mastery orb")
        self.assertEqual(spec.match, "skill mastery orb")
        self.assertEqual(rare_item_for_variable("SkillOrbPrice").razor_type, "void orb")

    def test_mastercrafting_diagram_is_a_rare_item(self):
        spec = default_search_spec("MastercraftingDiagramPrice")
        self.assertEqual(spec.search, "mastercrafting diagram")
        self.assertEqual(rare_item_for_variable("MastercraftingDiagramPrice").razor_type, "Book of Truth")

    def test_research_materials_is_a_rare_item(self):
        spec = default_search_spec("ResearchMaterialsPrice")
        self.assertEqual(spec.search, "research materials")
        self.assertEqual(rare_item_for_variable("ResearchMaterialsPrice").razor_type, "research materials")

    def test_skill_scroll_stays_in_scroll_family(self):
        spec = default_search_spec("AlchemyPrice")
        self.assertEqual(spec.search, "alchemy skill mastery scroll")
        self.assertIsNone(rare_item_for_variable("AlchemyPrice"))

    def test_arcane_scroll_is_a_rare_item_with_separate_razor_type(self):
        spec = default_search_spec("ArcaneScrollPrice")
        self.assertEqual(spec.search, "an arcane scroll")
        self.assertEqual(spec.match, "an arcane scroll")
        self.assertEqual(rare_item_for_variable("ArcaneScrollPrice").razor_type, "blank scroll%s%")


if __name__ == "__main__":
    unittest.main()
