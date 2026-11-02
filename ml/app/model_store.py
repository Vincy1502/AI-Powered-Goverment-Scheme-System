"""Versioned, validated loading for persisted GovScheme AI TF-IDF artifacts."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
from scipy.sparse import load_npz, save_npz, issparse
from sklearn.feature_extraction.text import TfidfVectorizer


ARTIFACT_VERSION = 1
REQUIRED_FILES = (
    "tfidf_vectorizer.joblib",
    "scheme_tfidf_matrix.npz",
    "scheme_metadata.json",
    "model_metadata.json",
    "manifest.json",
)


class ModelArtifactError(RuntimeError):
    """Raised when model artifacts are absent, incompatible, or inconsistent."""


def load_model_artifacts(model_dir: str | Path, expected_corpus_sha256: str | None = None) -> dict[str, Any]:
    directory = Path(model_dir)
    missing = [name for name in REQUIRED_FILES if not (directory / name).is_file()]
    if missing:
        raise ModelArtifactError(f"Missing model artifact files: {', '.join(missing)}")

    try:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        metadata = json.loads((directory / "model_metadata.json").read_text(encoding="utf-8"))
        scheme_metadata = json.loads((directory / "scheme_metadata.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelArtifactError(f"Could not read model metadata: {exc}") from exc

    if manifest.get("artifact_version") != ARTIFACT_VERSION:
        raise ModelArtifactError("Unsupported model artifact version.")
    if expected_corpus_sha256 and manifest.get("corpus_sha256") != expected_corpus_sha256:
        raise ModelArtifactError("Dataset fingerprint does not match the persisted model. Retrain the model.")

    try:
        vectorizer = joblib.load(directory / "tfidf_vectorizer.joblib")
        matrix = load_npz(directory / "scheme_tfidf_matrix.npz")
    except Exception as exc:
        raise ModelArtifactError(f"Could not load fitted model artifacts: {exc}") from exc

    if not isinstance(vectorizer, TfidfVectorizer):
        raise ModelArtifactError("Persisted vectorizer has an unexpected type.")
    if not issparse(matrix):
        raise ModelArtifactError("Persisted scheme matrix is not sparse.")
    if matrix.shape[0] != len(scheme_metadata):
        raise ModelArtifactError("Scheme metadata count does not match matrix rows.")
    if matrix.shape[1] != len(vectorizer.vocabulary_):
        raise ModelArtifactError("Matrix columns do not match vectorizer vocabulary.")
    if metadata.get("corpus_sha256") != manifest.get("corpus_sha256"):
        raise ModelArtifactError("Model metadata and manifest fingerprints disagree.")
    if metadata.get("matrix_rows") != matrix.shape[0] or metadata.get("matrix_columns") != matrix.shape[1]:
        raise ModelArtifactError("Model metadata dimensions do not match the matrix.")

    return {
        "vectorizer": vectorizer,
        "matrix": matrix,
        "scheme_metadata": scheme_metadata,
        "model_metadata": metadata,
        "manifest": manifest,
    }
