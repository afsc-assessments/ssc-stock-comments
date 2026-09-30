import unittest

from scripts.build_data import model_choice_relationship, stock_matches


class StockScopeTests(unittest.TestCase):
    def test_goa_tanner_section_is_separate_from_ebs(self):
        matches = {stock.stock for stock, _ in stock_matches(
            "The SSC recommends reviewing Tanner crab closures.", "C5 GOA Tanner Crab Protection Measures")}
        self.assertIn("GOA Tanner crab (bycatch)", matches)
        self.assertNotIn("EBS Tanner crab", matches)

    def test_explicit_ebs_comparison_remains_searchable(self):
        matches = {stock.stock for stock, _ in stock_matches(
            "The SSC compares GOA Tanner crab with EBS Tanner crab.")}
        self.assertIn("EBS Tanner crab", matches)
        self.assertIn("GOA Tanner crab (bycatch)", matches)

    def test_pribilof_golden_crab_is_separate_from_aleutians(self):
        matches = {stock.stock for stock, _ in stock_matches(
            "The SSC thanks the authors of the Pribilof Islands golden king crab assessment.")}
        self.assertIn("Pribilof Islands golden king crab", matches)
        self.assertNotIn("Aleutian Islands golden king crab", matches)


class ModelChoiceRelationshipTests(unittest.TestCase):
    def test_different_from_both(self):
        text = (
            "Noting the uncertainty, the SSC disagreed with the author and CPT "
            "and instead recommended using the Tier 3 model 24.1a."
        )
        result = model_choice_relationship(text)
        self.assertEqual(result["model_choice_relationship"], "different_from_both")
        self.assertTrue(result["model_choice_flag"])
        self.assertEqual(result["model_choice_confidence"], "high")

    def test_agrees_with_plan_team(self):
        text = "The SSC agrees with the Plan Team that Model 1 is the best model presented."
        result = model_choice_relationship(text)
        self.assertEqual(result["model_choice_relationship"], "agrees_with_plan_team")
        self.assertFalse(result["model_choice_flag"])

    def test_abc_disagreement_is_not_a_model_difference(self):
        text = (
            "The SSC disagrees with the Plan Team recommended ABC. "
            "The assessment was produced with a new model."
        )
        result = model_choice_relationship(text)
        self.assertFalse(result["model_choice_flag"])

    def test_research_suggestion_is_not_a_model_difference(self):
        text = (
            "The SSC supports the Plan Team's suggestion of examining simpler "
            "alternative growth models instead of Models 2 and 3."
        )
        result = model_choice_relationship(text)
        self.assertFalse(result["model_choice_flag"])

    def test_adjacent_context_is_review_only(self):
        text = "The SSC discussed the assessment model and requested more diagnostics."
        adjacent = "The author preferred Model 2 instead of the Plan Team's Model 3."
        result = model_choice_relationship(text, adjacent)
        self.assertEqual(result["model_choice_relationship"], "unclear")
        self.assertEqual(result["model_choice_confidence"], "review")
        self.assertTrue(result["model_choice_flag"])

    def test_irrelevant_comment_has_no_classification(self):
        result = model_choice_relationship("The SSC recommends additional survey work.")
        self.assertEqual(result["model_choice_relationship"], "")
        self.assertEqual(result["model_choice_confidence"], "")


if __name__ == "__main__":
    unittest.main()
