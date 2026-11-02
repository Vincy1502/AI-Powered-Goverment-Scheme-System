import unittest

from app.preprocessing import (
    build_profile_query,
    build_scheme_document,
    normalize_application_mode,
    prepare_record,
)


class PreprocessingTests(unittest.TestCase):
    def test_application_mode_variants(self):
        self.assertEqual(normalize_application_mode("Offline/Online"), "Online and Offline")
        self.assertEqual(normalize_application_mode("Online"), "Online")

    def test_blank_age_remains_unknown(self):
        record = prepare_record({"scheme_name": "Example", "min_age": None})
        self.assertIsNone(record["min_age"])

    def test_json_benefits_are_searchable(self):
        record = {
            "scheme_name": "Example Scheme",
            "benefits": {"loan_amount": "₹65,000"},
            "state": "Tamil Nadu",
        }
        text = build_scheme_document(record)
        self.assertIn("loan_amount", text)
        self.assertIn("Tamil Nadu", text)

    def test_profile_numeric_fields_not_added_to_text(self):
        query = build_profile_query({
            "state": "Tamil Nadu",
            "occupation": "Farmer",
            "age": 25,
            "income": 200000,
        })
        self.assertIn("Tamil Nadu", query)
        self.assertNotIn("25", query)
        self.assertNotIn("200000", query)

    def test_document_uses_target_fields(self):
        record = {
            "scheme_name": "Farm Support",
            "category_file": "Agriculture",
            "target_occupation": "Farmer",
            "eligibility_criteria": "Resident farmer",
        }
        text = build_scheme_document(record)
        self.assertIn("category: Agriculture", text)
        self.assertIn("target occupation: Farmer", text)


if __name__ == "__main__":
    unittest.main()
