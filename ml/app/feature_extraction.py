"""TF-IDF feature extraction and persistence for GovScheme AI."""
from __future__ import annotations

import hashlib
import json
import time
import os
import tempfile
from pathlib import Path
from typing import Any

import joblib
from scipy.sparse import save_npz
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from app.preprocessing import build_scheme_document, prepare_record


def load_scheme_records(csv_path: str | Path) -> list[dict[str, Any]]:
    frame = pd.read_csv(csv_path, dtype=object, keep_default_na=True)
    return frame.to_dict(orient="records")


def corpus_fingerprint(records: list[dict[str, Any]], documents: list[str]) -> str:
    payload = [
        {"scheme_name": str(record.get("scheme_name", "")), "document": document}
        for record, document in zip(records, documents)
    ]
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def fit_tfidf(records: list[dict[str, Any]]) -> tuple[TfidfVectorizer, Any, list[dict[str, Any]], list[str], dict[str, Any]]:
    prepared = [prepare_record(record) for record in records]
    documents = [build_scheme_document(record) for record in prepared]
    usable = [(record, doc) for record, doc in zip(prepared, documents) if doc.strip()]
    if not usable:
        raise ValueError("No usable scheme text was found in the supplied dataset.")

    prepared = [item[0] for item in usable]
    documents = [item[1] for item in usable]
    vectorizer = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        stop_words="english",
        ngram_range=(1, 2),
        min_df=1,
        sublinear_tf=True,
        norm="l2",
        dtype=np.float64,
    )

    start = time.perf_counter()
    matrix = vectorizer.fit_transform(documents)
    elapsed_ms = (time.perf_counter() - start) * 1000
    total_cells = matrix.shape[0] * matrix.shape[1]
    nnz = int(matrix.nnz)
    metrics = {
        "method": "TF-IDF word unigrams and bigrams",
        "method_type": "content-based feature extraction; not supervised classification",
        "records_received": len(records),
        "records_used": len(prepared),
        "records_skipped_no_text": len(records) - len(prepared),
        "matrix_rows": int(matrix.shape[0]),
        "matrix_columns": int(matrix.shape[1]),
        "vocabulary_size": len(vectorizer.vocabulary_),
        "nonzero_weights": nnz,
        "sparsity_percent": round((1 - nnz / total_cells) * 100, 4) if total_cells else 0.0,
        "average_nonzero_terms_per_scheme": round(nnz / matrix.shape[0], 2),
        "fit_time_ms": round(elapsed_ms, 3),
        "corpus_sha256": corpus_fingerprint(prepared, documents),
        "classification_metrics": None,
        "evaluation_note": (
            "No verified user-scheme eligibility labels are supplied. "
            "Accuracy, precision, recall and F1 are therefore not applicable."
        ),
    }
    return vectorizer, matrix, prepared, documents, metrics



def save_artifacts(
    vectorizer: TfidfVectorizer,
    matrix: Any,
    records: list[dict[str, Any]],
    documents: list[str],
    metrics: dict[str, Any],
    output_dir: str | Path,
) -> None:
    """Persist fitted artifacts using temp files, then publish a manifest last."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    metadata_records = []
    for idx, (record, document) in enumerate(zip(records, documents)):
        metadata_records.append({
            "row_index": idx,
            "scheme_name": record.get("scheme_name"),
            "state": record.get("state"),
            "category_file": record.get("category_file"),
            "source_document_sha256": hashlib.sha256(document.encode("utf-8")).hexdigest(),
        })

    manifest = {
        "artifact_version": 1,
        "model_type": "tfidf_content_based_ranker",
        "corpus_sha256": metrics["corpus_sha256"],
        "records": len(records),
        "matrix_shape": [int(matrix.shape[0]), int(matrix.shape[1])],
        "vocabulary_size": len(vectorizer.vocabulary_),
        "sklearn_version": __import__("sklearn").__version__,
        "numpy_version": np.__version__,
    }

    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output) as temp_dir:
        temp = Path(temp_dir)
        joblib.dump(vectorizer, temp / "tfidf_vectorizer.joblib", compress=3)
        save_npz(temp / "scheme_tfidf_matrix.npz", matrix, compressed=True)
        (temp / "scheme_metadata.json").write_text(
            json.dumps(metadata_records, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        (temp / "model_metadata.json").write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        (temp / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        # Publish data files first; manifest is the final commit marker.
        for name in ("tfidf_vectorizer.joblib", "scheme_tfidf_matrix.npz",
                     "scheme_metadata.json", "model_metadata.json"):
            os.replace(temp / name, output / name)
        os.replace(temp / "manifest.json", output / "manifest.json")


def train_from_csv(csv_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    records = load_scheme_records(csv_path)
    vectorizer, matrix, prepared, documents, metrics = fit_tfidf(records)
    save_artifacts(vectorizer, matrix, prepared, documents, metrics, output_dir)
    return metrics
