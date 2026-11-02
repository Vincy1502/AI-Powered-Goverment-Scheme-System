from __future__ import annotations
import hashlib
import json
import time
import numpy as np
from typing import Any
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from pathlib import Path
import csv
from app.eligibility import assess_eligibility
from app.model_store import load_model_artifacts, ModelArtifactError
from app.preprocessing import build_profile_query, prepare_record

BASE_DIR = Path(__file__).resolve().parents[1]
MODEL_DIR = BASE_DIR / "models"
DATASET_PATH = BASE_DIR / "data" / "cleaned_schemes.csv"

app = FastAPI(title="GovScheme AI ML Service", version="1.1.0", description="Persisted TF-IDF scheme ranking with conservative structured eligibility assessment.")

class RequestBody(BaseModel):
    schemes: list[dict[str, Any]] = Field(default_factory=list)

class RecommendationRequest(BaseModel):
    profile: dict[str, Any]
    schemes: list[dict[str, Any]]
    limit: int = Field(default=5, ge=1, le=20)

class CompareRequest(BaseModel):
    profile: dict[str, Any]
    schemes: list[dict[str, Any]]
    limit: int = Field(default=5, ge=1, le=20)

class EvaluationCase(BaseModel):
    profile: dict[str, Any]
    relevant_scheme_names: list[str]

class EvaluationRequest(BaseModel):
    schemes: list[dict[str, Any]]
    cases: list[EvaluationCase]
    k: int = Field(default=5, ge=1, le=20)

vectorizer: TfidfVectorizer | None = None
matrix = None
cached_docs: list[dict[str, Any]] = []
corpus_hash: str | None = None
model_metrics: dict[str, Any] = {"status": "not_loaded"}
persisted_vectorizer = None
persisted_matrix = None
persisted_scheme_records: list[dict[str, Any]] = []
persisted_model_error: str | None = None


def load_persisted_ranker() -> None:
    """Load Stage 6 artifacts once; never retrain per request."""
    global persisted_vectorizer, persisted_matrix, persisted_scheme_records, model_metrics, persisted_model_error
    try:
        loaded = load_model_artifacts(MODEL_DIR)
        with DATASET_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
            records = [prepare_record(row) for row in csv.DictReader(handle)]
        metadata = loaded["scheme_metadata"]
        if len(records) != len(metadata) or len(records) != loaded["matrix"].shape[0]:
            raise ModelArtifactError("Cleaned dataset row count does not match persisted model metadata.")
        for index, (record, item) in enumerate(zip(records, metadata)):
            if str(record.get("scheme_name", "")).strip() != str(item.get("scheme_name", "")).strip():
                raise ModelArtifactError(f"Dataset/model row mapping mismatch at row {index}.")
        persisted_vectorizer = loaded["vectorizer"]
        persisted_matrix = loaded["matrix"]
        persisted_scheme_records = records
        model_metrics = dict(loaded["model_metadata"])
        model_metrics["status"] = "ready"
        model_metrics["loaded_from_persisted_artifacts"] = True
        persisted_model_error = None
    except Exception as exc:
        persisted_vectorizer = persisted_matrix = None
        persisted_scheme_records = []
        persisted_model_error = str(exc)
        model_metrics = {"status": "unavailable", "error": persisted_model_error}


load_persisted_ranker()

STOP_TEXT = {"n/a", "na", "none", "null", "not specified", "not available"}


def flatten(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return " ".join(flatten(v) for v in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(flatten(v) for v in value)
    text = str(value).strip()
    return "" if text.lower() in STOP_TEXT else text


def scheme_text(scheme: dict[str, Any]) -> str:
    # Keep eligibility text explicit so eligibility-related reasons can be generated.
    parts = [scheme.get("scheme_name"), scheme.get("parent_scheme"), scheme.get("ministry"),
             scheme.get("department"), scheme.get("objectives"), scheme.get("eligibility_criteria"),
             scheme.get("benefits")]
    return " ".join(flatten(part) for part in parts if flatten(part)).strip()


def profile_query(profile: dict[str, Any]) -> str:
    parts = [profile.get("state"), profile.get("occupation"), profile.get("gender"),
             profile.get("category"), profile.get("query")]
    # Income/age are not text-match labels; don't falsely treat numeric values as eligibility.
    return " ".join(flatten(p) for p in parts if flatten(p)).strip()


def stable_key(docs: list[dict[str, Any]]) -> str:
    compact = [{"name": d.get("scheme_name", ""), "text": scheme_text(d)} for d in docs]
    return hashlib.sha256(json.dumps(compact, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def fit(docs: list[dict[str, Any]]) -> dict[str, Any]:
    global vectorizer, matrix, cached_docs, corpus_hash, model_metrics
    cleaned = [d for d in docs if isinstance(d, dict) and scheme_text(d)]
    if not cleaned:
        vectorizer, matrix, cached_docs, corpus_hash = None, None, [], None
        model_metrics = {"status": "no_data", "records_received": len(docs), "records_used": 0,
                         "classification_metrics": None,
                         "evaluation_note": "No usable scheme text was available. Classification metrics cannot be computed without verified labels."}
        return model_metrics
    key = stable_key(cleaned)
    if key == corpus_hash and matrix is not None:
        return model_metrics
    start = time.perf_counter()
    new_vectorizer = TfidfVectorizer(lowercase=True, strip_accents="unicode", stop_words="english",
                                     ngram_range=(1, 2), min_df=1, sublinear_tf=True, norm="l2", dtype=np.float64)
    new_matrix = new_vectorizer.fit_transform([scheme_text(d) for d in cleaned])
    elapsed = time.perf_counter() - start
    nonzeros = int(new_matrix.nnz)
    total_cells = int(new_matrix.shape[0] * new_matrix.shape[1])
    vectorizer, matrix, cached_docs, corpus_hash = new_vectorizer, new_matrix, cleaned, key
    model_metrics = {
        "status": "ready",
        "method": "TF-IDF (word unigrams/bigrams) + cosine similarity",
        "method_type": "content-based NLP ranking; not a supervised classifier",
        "records_received": len(docs),
        "records_used": len(cleaned),
        "records_skipped_no_text": len(docs) - len(cleaned),
        "vocabulary_size": len(new_vectorizer.vocabulary_),
        "matrix_rows": int(new_matrix.shape[0]),
        "matrix_columns": int(new_matrix.shape[1]),
        "nonzero_tfidf_weights": nonzeros,
        "matrix_sparsity_percent": round((1 - nonzeros / total_cells) * 100, 4) if total_cells else 0.0,
        "avg_nonzero_terms_per_scheme": round(nonzeros / new_matrix.shape[0], 2),
        "fit_time_ms": round(elapsed * 1000, 3),
        "corpus_sha256": key,
        "classification_metrics": None,
        "evaluation_note": "Accuracy, precision, recall and F1 are not reported because the source corpus has not supplied verified user-scheme eligibility labels. Ranking metrics require independently verified relevance judgements.",
        "trained_model_note": "The fitted TF-IDF vocabulary and document matrix are built from the live scheme records when the corpus changes. This is content-based ranking, not supervised model training."
    }
    return model_metrics


def state_mentions(text: str) -> set[str]:
    states = ["andhra pradesh", "arunachal pradesh", "assam", "bihar", "chhattisgarh", "goa", "gujarat", "haryana", "himachal pradesh", "jharkhand", "karnataka", "kerala", "madhya pradesh", "maharashtra", "manipur", "meghalaya", "mizoram", "nagaland", "odisha", "punjab", "rajasthan", "sikkim", "tamil nadu", "telangana", "tripura", "uttar pradesh", "uttarakhand", "west bengal", "delhi", "jammu and kashmir", "ladakh", "puducherry"]
    low = text.lower().replace("-", " ")
    found = set()
    for state in states:
        if state in low or state.replace(" ", "") in low.replace(" ", ""):
            found.add(state)
    return found


def reasons_for(scheme: dict[str, Any], profile: dict[str, Any], similarity: float) -> list[str]:
    reasons: list[str] = []
    eligibility = flatten(scheme.get("eligibility_criteria")).lower()
    objective = flatten(scheme.get("objectives")).lower()
    combined = (scheme_text(scheme) + " " + eligibility).lower()
    state = flatten(profile.get("state")).lower().replace("-", " ")
    occupation = flatten(profile.get("occupation")).lower()
    gender = flatten(profile.get("gender")).lower()
    category = flatten(profile.get("category")).lower()
    if state and state in combined.replace("-", " "):
        reasons.append(f"Your selected state ({profile.get('state')}) appears in the scheme information.")
    occupation_terms = {
        "farmer": ["farmer", "agriculture", "agricultural", "farming", "crop", "cultivation", "irrigation"],
        "student": ["student", "education", "scholarship", "school", "college", "university", "fellowship"],
        "employee": ["employee", "worker", "employment", "labour", "labor", "workforce"],
        "business": ["business", "entrepreneur", "enterprise", "startup", "self employed"],
        "unemployed": ["unemployed", "employment", "job seeker", "skill development"]
    }
    matches = [word for word in occupation_terms.get(occupation, [occupation] if occupation else []) if word and word in combined]
    if matches:
        reasons.append(f"Occupation-related terms found: {', '.join(matches[:3])}.")
    if gender == "female" and any(w in eligibility for w in ["women", "woman", "female", "girl"]):
        reasons.append("The eligibility text mentions women, girls, or female applicants.")
    elif gender and gender in eligibility:
        reasons.append("Your selected gender appears in the eligibility text.")
    if category and category not in {"general", "none", "not specified"} and category in eligibility:
        reasons.append("Your selected category appears in the eligibility text.")
    if flatten(scheme.get("objectives")):
        reasons.append("The scheme objectives were included in the text relevance ranking.")
    if not reasons:
        reasons.append("Ranked by text similarity to the profile you entered; review the official eligibility conditions before applying.")
    reasons.append("Relevance score is a text-similarity score, not an eligibility probability.")
    return reasons


def explicit_state_conflict(scheme: dict[str, Any], profile: dict[str, Any]) -> bool:
    # Conservative: only inspect eligibility criteria, never the whole document.
    chosen = flatten(profile.get("state")).lower().replace("-", " ").strip()
    if not chosen:
        return False
    known_states = state_mentions("andhra pradesh arunachal pradesh assam bihar chhattisgarh goa gujarat haryana himachal pradesh jharkhand karnataka kerala madhya pradesh maharashtra manipur meghalaya mizoram nagaland odisha punjab rajasthan sikkim tamil nadu telangana tripura uttar pradesh uttarakhand west bengal delhi jammu and kashmir ladakh puducherry")
    chosen_normalized = chosen.replace(" ", "")
    if chosen_normalized not in {state.replace(" ", "") for state in known_states}:
        return False
    mentions = state_mentions(flatten(scheme.get("eligibility_criteria")))
    # Only exclude when the eligibility text explicitly names another known state.
    return bool(mentions and chosen_normalized not in {state.replace(" ", "") for state in mentions})


@app.get("/health")
def health():
    return {"status": "ok", "service": "govscheme-ai-ml", "model_ready": persisted_matrix is not None, "model_source": "persisted_stage6_artifacts", "model_error": persisted_model_error}

@app.post("/metrics")
def metrics(body: RequestBody):
    # Return the immutable Stage 6 training diagnostics; request-time fitting is avoided.
    if persisted_matrix is None:
        raise HTTPException(status_code=503, detail=f"Persisted model unavailable: {persisted_model_error}")
    return model_metrics

@app.post("/recommend")
def recommend(body: RecommendationRequest):
    if not body.schemes:
        raise HTTPException(status_code=422, detail="No scheme records were supplied by the backend.")
    if persisted_vectorizer is None or persisted_matrix is None:
        raise HTTPException(status_code=503, detail=f"Persisted model unavailable: {persisted_model_error}")
    profile = body.profile or {}
    query = build_profile_query(profile)
    if not query.strip():
        raise HTTPException(status_code=422, detail="Enter at least a state and occupation to create a recommendation query.")

    # The saved matrix is tied to the cleaned 174-row dataset. Join live Mongo records
    # by exact scheme name where possible, but use the dataset row for structured rules.
    live_by_name = {str(item.get("scheme_name", "")).strip().casefold(): item for item in body.schemes if item.get("scheme_name")}
    query_vector = persisted_vectorizer.transform([query])
    similarities = cosine_similarity(query_vector, persisted_matrix).ravel()
    results = []
    for index, (dataset_doc, score) in enumerate(zip(persisted_scheme_records, similarities)):
        if float(score) <= 0:
            continue
        eligibility = assess_eligibility(dataset_doc, profile)
        result_doc = dict(dataset_doc)
        live_doc = live_by_name.get(str(dataset_doc.get("scheme_name", "")).strip().casefold())
        if live_doc:
            result_doc["_id"] = str(live_doc.get("_id", ""))
            # Preserve richer live display fields without overriding dataset rule fields.
            for field in ("application_process", "official_links"):
                if live_doc.get(field) not in (None, "", [], {}):
                    result_doc[field] = live_doc[field]
        else:
            result_doc["_id"] = ""
        result_doc["relevance_score"] = round(float(score), 4)
        result_doc["relevance_percent"] = round(float(score) * 100, 1)
        result_doc["recommendation_reasons"] = reasons_for(dataset_doc, profile, float(score))
        result_doc.update(eligibility)
        result_doc["eligibility_disclaimer"] = "Automated structured checks are preliminary. Natural-language conditions/exclusions and official rules require review; this is not a government eligibility decision."
        results.append(result_doc)
    results.sort(key=lambda item: item["relevance_score"], reverse=True)
    return {
        "method": "Persisted TF-IDF + cosine similarity",
        "method_type": "content-based NLP ranking with structured eligibility screening",
        "model_source": "Stage 6 persisted artifacts",
        "total_schemes_received": len(body.schemes),
        "dataset_scheme_count": len(persisted_scheme_records),
        "live_catalog_matches": sum(1 for row in persisted_scheme_records if str(row.get("scheme_name", "")).strip().casefold() in live_by_name),
        "candidate_count": len(results),
        "recommendations": results[:body.limit],
        "model_metrics": model_metrics,
        "evaluation_note": "Eligibility status is conservative: missing values are unknown, natural-language rules are manual-review items, and confirmed eligibility requires verified official-rule provenance. Text similarity is not an eligibility probability."
    }

@app.post("/compare")
def compare_methods(body: CompareRequest):
    """Compare old keyword-score ordering with the new ranker; this is not a quality metric."""
    if not body.schemes:
        raise HTTPException(status_code=422, detail="No scheme records were supplied.")
    profile = body.profile or {}
    fit(body.schemes)
    if vectorizer is None or matrix is None:
        raise HTTPException(status_code=422, detail="No usable scheme text exists in the supplied records.")

    # Measure baseline ranking on the same corpus and profile.
    baseline_start = time.perf_counter()
    state = flatten(profile.get("state")).lower().replace("-", " ")
    occupation = flatten(profile.get("occupation")).lower()
    gender = flatten(profile.get("gender")).lower()
    category = flatten(profile.get("category")).lower()
    age = profile.get("age")
    try:
        age = int(age) if age not in (None, "") else None
    except (TypeError, ValueError):
        age = None
    try:
        income = float(profile.get("income")) if profile.get("income") not in (None, "") else None
    except (TypeError, ValueError):
        income = None
    state_aliases = {"tamil nadu": ["tamil nadu", "tamilnadu"], "kerala": ["kerala"], "karnataka": ["karnataka"], "andhra pradesh": ["andhra pradesh"], "telangana": ["telangana"]}
    occupation_terms = {"student": ["student", "education", "scholarship", "school", "college", "university", "academic", "fellowship"],
                        "farmer": ["farmer", "agriculture", "agricultural", "farming", "crop", "cultivation", "irrigation"],
                        "employee": ["employee", "worker", "employment", "labour", "labor", "workforce"],
                        "business": ["business", "entrepreneur", "enterprise", "startup", "self employed"],
                        "unemployed": ["unemployed", "employment", "job seeker", "skill development"]}
    baseline = []
    for doc in body.schemes:
        text = scheme_text(doc).lower()
        score = 0
        aliases = state_aliases.get(state, [])
        if aliases and any(alias in text for alias in aliases): score += 4
        if any(term in text for term in occupation_terms.get(occupation, [])): score += 4
        if gender and gender in text: score += 2
        if gender == "female" and any(term in text for term in ["women", "woman", "girl"]): score += 2
        if category and category not in {"general", "other / not specified"} and category in text: score += 3
        if age is not None and (("young" in text and 18 <= age <= 35) or ("youth" in text and 15 <= age <= 35)): score += 1
        if income == 0 and any(term in text for term in ["low income", "economically weaker", "poor"]): score += 2
        baseline.append({"scheme_name": str(doc.get("scheme_name", "")), "score": score})
    baseline.sort(key=lambda item: item["score"], reverse=True)
    baseline_top = [item for item in baseline if item["score"] >= 7][:body.limit]
    baseline_ms = round((time.perf_counter() - baseline_start) * 1000, 3)

    ml_start = time.perf_counter()
    query = profile_query(profile)
    if query:
        scores = cosine_similarity(vectorizer.transform([query]), matrix).ravel()
        ml_ranked = []
        for index, score in enumerate(scores):
            doc = cached_docs[index]
            if float(score) <= 0 or explicit_state_conflict(doc, profile):
                continue
            ml_ranked.append({"scheme_name": str(doc.get("scheme_name", "")), "relevance_score": round(float(score), 4), "relevance_percent": round(float(score) * 100, 1)})
        ml_ranked.sort(key=lambda item: item["relevance_score"], reverse=True)
    else:
        ml_ranked = []
    ml_top = ml_ranked[:body.limit]
    ml_ms = round((time.perf_counter() - ml_start) * 1000, 3)
    baseline_names = {item["scheme_name"].casefold() for item in baseline_top}
    ml_names = {item["scheme_name"].casefold() for item in ml_top}
    overlap = len(baseline_names & ml_names)
    union = len(baseline_names | ml_names)
    return {"baseline_method": "Legacy keyword scoring (recreated from the uploaded Eligibility.jsx)",
            "ml_method": "TF-IDF + cosine similarity", "records_compared": len(body.schemes), "limit": body.limit,
            "baseline_runtime_ms": baseline_ms, "ml_runtime_ms": ml_ms,
            "baseline_top_k": baseline_top, "ml_top_k": ml_top,
            "top_k_overlap_count": overlap, "top_k_jaccard_percent": round(overlap / union * 100, 1) if union else 0.0,
            "interpretation": "Overlap and runtime compare behavior only. They do not establish which method is more accurate or more relevant; that requires independently reviewed relevance labels."}

@app.post("/evaluate-ranking")
def evaluate_ranking(body: EvaluationRequest):
    """Evaluate this ranker against independently verified scheme-name relevance judgements."""
    if not body.cases:
        raise HTTPException(status_code=422, detail="At least one independently reviewed evaluation case is required.")
    if not body.schemes:
        raise HTTPException(status_code=422, detail="Provide the real scheme corpus to evaluate against.")
    fit(body.schemes)
    if vectorizer is None or matrix is None:
        raise HTTPException(status_code=422, detail="No usable scheme text exists in the supplied records.")
    precisions, recalls, reciprocal_ranks = [], [], []
    valid_cases = 0
    skipped_cases = 0
    for case in body.cases:
        relevant = {name.strip().casefold() for name in case.relevant_scheme_names if name.strip()}
        if not relevant:
            skipped_cases += 1
            continue
        query = profile_query(case.profile)
        if not query:
            skipped_cases += 1
            continue
        scores = cosine_similarity(vectorizer.transform([query]), matrix).ravel()
        ranked = []
        for index, score in enumerate(scores):
            doc = cached_docs[index]
            if float(score) <= 0 or explicit_state_conflict(doc, case.profile):
                continue
            ranked.append((float(score), str(doc.get("scheme_name", "")).strip().casefold()))
        ranked.sort(key=lambda pair: pair[0], reverse=True)
        top_names = [name for _, name in ranked[:body.k]]
        hits = [i for i, name in enumerate(top_names, start=1) if name in relevant]
        valid_cases += 1
        precisions.append(len(set(top_names) & relevant) / body.k)
        recalls.append(len(set(top_names) & relevant) / len(relevant))
        reciprocal_ranks.append(1 / hits[0] if hits else 0.0)
    if not valid_cases:
        raise HTTPException(status_code=422, detail="No cases contain both a usable profile and independently verified relevant scheme names.")
    return {"evaluation_type": "ranking metrics from caller-supplied relevance judgements",
            "verified_cases_used": valid_cases, "cases_skipped": skipped_cases, "k": body.k,
            "precision_at_k": round(sum(precisions)/valid_cases, 4),
            "recall_at_k": round(sum(recalls)/valid_cases, 4),
            "mean_reciprocal_rank": round(sum(reciprocal_ranks)/valid_cases, 4),
            "note": "These metrics evaluate this ranker only against independently reviewed relevance judgements supplied by the caller. They are not classification accuracy, and their validity depends on the quality of the annotations."}
