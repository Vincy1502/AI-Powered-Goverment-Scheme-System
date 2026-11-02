import unittest
from app.eligibility import assess_eligibility


class EligibilityEngineTests(unittest.TestCase):
    def profile(self):
        return {"state": "Tamil Nadu", "age": 30, "income": 200000,
                "gender": "Female", "category": "OBC", "occupation": "Farmer"}

    def complete_scheme(self):
        return {"scheme_name": "Farm Support", "state": "Tamil Nadu", "min_age": 18,
                "max_age": 60, "max_income": 500000, "gender": "any",
                "target_categories": "OBC", "target_occupation": "Farmer"}

    def test_missing_structured_fields_are_unknown_not_pass(self):
        result = assess_eligibility({"scheme_name": "Unknown rules"}, self.profile())
        self.assertEqual(result["eligibility_status"], "insufficient_information")
        self.assertTrue(result["unknown_criteria"])
        self.assertTrue(all(c["status"] == "unknown" for c in result["eligibility_checks"]))

    def test_verified_structured_mismatch_is_not_eligible(self):
        scheme = self.complete_scheme()
        scheme["max_income"] = 100000
        result = assess_eligibility(scheme, self.profile())
        self.assertEqual(result["eligibility_status"], "not_eligible")
        self.assertIn("maximum income", result["failed_criteria"])

    def test_natural_language_conditions_are_manual_review(self):
        scheme = self.complete_scheme()
        scheme["eligibility_criteria"] = "Must be a registered farmer for 3 years"
        result = assess_eligibility(scheme, self.profile())
        self.assertEqual(result["eligibility_status"], "potential_eligibility")
        self.assertEqual(result["manual_review"][0]["field"], "eligibility_criteria")
        self.assertIn("3 years", result["manual_review"][0]["text"])

    def test_confirmed_requires_verified_rule_provenance(self):
        scheme = self.complete_scheme()
        scheme["eligibility_rule_provenance"] = {
            "verified": True, "source_url": "https://example.gov.in/rules",
            "checked_at": "2026-10-30"
        }
        result = assess_eligibility(scheme, self.profile())
        self.assertEqual(result["eligibility_status"], "confirmed_eligible")
        self.assertTrue(result["confirmed_eligibility_allowed"])

    def test_missing_profile_age_is_not_passed(self):
        result = assess_eligibility(self.complete_scheme(), {**self.profile(), "age": None})
        self.assertEqual(result["eligibility_status"], "insufficient_information")
        self.assertIn("minimum age", result["unknown_criteria"])


if __name__ == "__main__":
    unittest.main()
