"""Run TF-IDF feature extraction on the cleaned GovScheme AI dataset."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.feature_extraction import train_from_csv
from app.model_store import load_model_artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        default=str(Path(__file__).resolve().parents[1] / "data" / "cleaned_schemes.csv"),
        help="Path to the cleaned scheme CSV.",
    )
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parents[1] / "models"),
        help="Directory where fitted artifacts will be saved.",
    )
    args = parser.parse_args()
    metrics = train_from_csv(args.input, args.output)
    loaded = load_model_artifacts(args.output, expected_corpus_sha256=metrics["corpus_sha256"])
    metrics["persistence_verification"] = {
        "loaded_successfully": True,
        "matrix_shape_after_reload": list(loaded["matrix"].shape),
        "metadata_rows_after_reload": len(loaded["scheme_metadata"]),
        "artifact_version": loaded["manifest"]["artifact_version"],
    }
    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
