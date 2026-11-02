import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from app.feature_extraction import train_from_csv
from app.model_store import ModelArtifactError, load_model_artifacts


class ModelPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.csv = self.root / "schemes.csv"
        self.models = self.root / "models"
        pd.DataFrame([
            {"scheme_name": "Farmer Irrigation Support", "category_file": "Agriculture",
             "objectives": "Support irrigation for farmers", "state": "Tamil Nadu",
             "eligibility_criteria": "Resident farmer", "benefits": '{"grant":"water support"}',
             "min_age": None, "max_age": None, "max_income": None},
            {"scheme_name": "Student Scholarship", "category_file": "Education",
             "objectives": "Scholarship for students", "state": "All India",
             "eligibility_criteria": "Students enrolled in education", "benefits": '{"award":"scholarship"}',
             "min_age": None, "max_age": None, "max_income": None},
        ]).to_csv(self.csv, index=False)

    def tearDown(self):
        self.temp.cleanup()

    def test_train_and_persist_artifacts(self):
        metrics = train_from_csv(self.csv, self.models)
        self.assertEqual(metrics["records_used"], 2)
        for name in ("tfidf_vectorizer.joblib", "scheme_tfidf_matrix.npz",
                     "scheme_metadata.json", "model_metadata.json", "manifest.json"):
            self.assertTrue((self.models / name).exists(), name)

    def test_load_saved_model_and_check_dimensions(self):
        metrics = train_from_csv(self.csv, self.models)
        loaded = load_model_artifacts(self.models, metrics["corpus_sha256"])
        self.assertEqual(loaded["matrix"].shape, (2, len(loaded["vectorizer"].vocabulary_)))
        self.assertEqual(len(loaded["scheme_metadata"]), 2)

    def test_reject_changed_dataset_fingerprint(self):
        metrics = train_from_csv(self.csv, self.models)
        with self.assertRaises(ModelArtifactError):
            load_model_artifacts(self.models, expected_corpus_sha256="not-the-same-dataset")

    def test_reject_missing_artifact(self):
        train_from_csv(self.csv, self.models)
        (self.models / "scheme_metadata.json").unlink()
        with self.assertRaises(ModelArtifactError):
            load_model_artifacts(self.models)

    def test_manifest_has_version_and_fingerprint(self):
        metrics = train_from_csv(self.csv, self.models)
        manifest = json.loads((self.models / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["artifact_version"], 1)
        self.assertEqual(manifest["corpus_sha256"], metrics["corpus_sha256"])


if __name__ == "__main__":
    unittest.main()
