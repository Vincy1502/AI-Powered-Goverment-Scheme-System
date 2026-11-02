# GovScheme AI ML service

This FastAPI service performs content-based recommendation using a fitted TF-IDF corpus and cosine similarity. It receives scheme records from the Node backend, so it does not require a separate or invented dataset.

## Windows setup

```powershell
cd ml
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check: `http://127.0.0.1:8000/health`
Interactive API docs: `http://127.0.0.1:8000/docs`

The service loads the Stage 6 persisted TF-IDF artifacts once at startup and does not retrain on each request. It uses the cleaned 174-row dataset as the rule-bearing scheme catalogue; matching MongoDB records are used only to enrich display fields. `fit_time_ms`, vocabulary size, sparsity, and corpus fingerprint are descriptive pipeline diagnostics, not accuracy metrics.

No verified user-scheme labels were included in the project ZIP. Therefore classification accuracy, precision, recall, and F1 are intentionally not fabricated. Use `POST /evaluate-ranking` only with independently reviewed relevance judgements and the live scheme corpus.


## Stage 5: preprocessing and TF-IDF artifacts

The cleaned source dataset is stored at `ml/data/cleaned_schemes.csv`.
Run feature extraction from the `ml` directory:

```powershell
python -m scripts.train_tfidf
```

The script saves:
- `models/tfidf_vectorizer.joblib`
- `models/scheme_tfidf_matrix.joblib`
- `models/scheme_metadata.json`
- `models/model_metadata.json`

Eligibility fields that are blank remain unknown. Age and income are not inserted into the text query; they are reserved for the separate structured eligibility engine. The fitted TF-IDF artifacts are content-based ranking features, not a supervised eligibility classifier.


## Stage 6: reproducible training and persisted model loading

From the `ml` directory, train and save the fitted TF-IDF model:

```powershell
python -m scripts.train_tfidf
```

Artifacts are stored in `models/`:
- `tfidf_vectorizer.joblib`: fitted vocabulary and IDF weights
- `scheme_tfidf_matrix.npz`: sparse scheme feature matrix
- `scheme_metadata.json`: row-to-scheme mapping
- `model_metadata.json`: corpus and training diagnostics
- `manifest.json`: artifact version, corpus fingerprint and dimensions

The loader in `app/model_store.py` validates required files, artifact version,
dataset fingerprint (when supplied), sparse matrix dimensions, vocabulary size,
and metadata consistency. If the dataset fingerprint changes, retrain rather
than silently using stale model artifacts.

Run tests:

```powershell
python -m unittest discover -s tests -v
```

These artifacts support content-based ranking. They are not a supervised
eligibility classifier; classification metrics are not applicable without
verified labels.


## Stage 7: structured eligibility assessment and API integration

`app/eligibility.py` evaluates only explicit structured fields (`state`, `min_age`, `max_age`, `max_income`, `gender`, `target_categories`, and `target_occupation`). Every check includes its source field and a pass/fail/unknown result. Missing or malformed values are **unknown**, never a pass. Natural-language `eligibility_criteria` and `exclusions` are returned in `manual_review`; they are not guessed into rules.

The `/recommend` API ranks with the persisted Stage 6 TF-IDF artifacts and adds one of four conservative statuses: `confirmed_eligible`, `potential_eligibility`, `insufficient_information`, or `not_eligible`. A confirmed result requires a verified `eligibility_rule_provenance` object containing `verified: true`, `source_url`, and `checked_at`. The supplied cleaned dataset has no such verified provenance, so it does not establish confirmed eligibility.

Run the Stage 7 and regression tests from this directory:

```powershell
python -m unittest discover -s tests -v
```

The API still requires the Node backend/MongoDB and browser workflow to be exercised in the user's own environment. The ML service's API contract is covered by local FastAPI tests.
