# GovScheme AI — ML-enabled full-stack version

This package adds a FastAPI NLP ranking service, Express JWT authentication, and a refreshed React interface to the supplied project. It intentionally does **not** contain the live MongoDB scheme records or credentials. The API reads the real scheme collection from your configured Atlas database.

## Architecture

- React + Vite: improved responsive UI, registration/login, protected scheme discovery and model diagnostics.
- Node.js + Express + Mongoose: reads `govschemeai.schemes`, stores user accounts, hashes passwords with bcrypt, signs JWTs, and proxies requests to FastAPI.
- Python + FastAPI + scikit-learn: loads the Stage 6 persisted TF-IDF artifacts and ranks profile queries using cosine similarity; a separate conservative eligibility engine checks structured rules.

## Important evaluation note

The cleaned source dataset contains 174 scheme records and is included at `ml/data/cleaned_schemes.csv`. The persisted Stage 6 artifacts are loaded by the ML service at startup. TF-IDF vocabulary size, matrix sparsity and fit time are displayed as pipeline diagnostics. They are **not classification performance**. No verified user-scheme relevance labels were supplied, so accuracy/precision/recall/F1 are not fabricated. The ML service includes `POST /evaluate-ranking` for Precision@K, Recall@K and MRR when independently reviewed relevance judgements are available. `POST /recommend` uses the persisted artifact matrix and returns structured eligibility assessments from the included cleaned dataset.

## 0. Security first

The original ZIP contained `backend/.env`. It has been excluded from this output. Rotate the MongoDB Atlas database user's password if that uploaded secret was real. Never share or commit `.env`.

## 1. Configure MongoDB and backend

1. Open `backend/`.
2. Copy `.env.example` to `.env`.
3. Put your rotated/current MongoDB connection string into `MONGODB_URI` and set a random `JWT_SECRET` of at least 32 characters.
4. Install dependencies and start:

```powershell
cd backend
npm install
npm run dev
```

Backend listens on `http://localhost:5000`. It will exit if it cannot connect to MongoDB, so check the Atlas network access list and credentials. Existing scheme records are read-only from these routes. Do not run the old `importData.js`; it contains `Scheme.deleteMany({})` and points at a separate reference dataset.

## 2. Start the ML service

Open a second terminal:

```powershell
cd ml
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Check `http://127.0.0.1:8000/health`. The service uses its versioned persisted Stage 6 artifacts and the included cleaned dataset for stable ranking and structured eligibility rules. Matching MongoDB scheme records are used to enrich display fields where names match.

## 3. Start frontend

Open a third terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open the Vite URL (normally `http://localhost:5173`). Optional: copy `.env.example` to `.env` if your backend URL differs.

## 4. User flow

1. Create an account on `/register`.
2. Log in at `/login`.
3. Open Find schemes, enter a state and occupation, then submit.
4. Open ML performance to view diagnostics for the persisted Stage 6 model.

Authentication uses a bearer JWT stored in localStorage for this student/demo application. For production use, consider secure HttpOnly cookies, rate limiting, email verification, password reset, and HTTPS.

## API endpoints

- `GET /api/health` — backend/database status.
- `POST /api/auth/register` — `{name,email,password}`.
- `POST /api/auth/login` — `{email,password}`.
- `GET /api/auth/me` — current JWT user.
- `GET /api/schemes` — scheme documents.
- `POST /api/schemes/recommend` — authenticated; user profile in JSON body; calls FastAPI.
- `GET /api/schemes/ml-performance` — authenticated; returns persisted Stage 6 TF-IDF diagnostics.
- `GET http://127.0.0.1:8000/docs` — ML service docs.
- `POST http://127.0.0.1:8000/recommend` — persisted TF-IDF ranking plus structured eligibility assessment.
- `POST http://127.0.0.1:8000/evaluate-ranking` — calculate Precision@K, Recall@K and MRR from caller-supplied schemes and independently reviewed relevance judgements.

## Recommendation limitations

- The model is content-based NLP ranking, not a supervised eligibility classifier.
- Relevance scores are not eligibility probabilities.
- Text-based recommendations can miss implied eligibility rules or misinterpret ambiguous text. Verify all conditions and official links.
- Missing structured values are unknown, never a pass. Natural-language criteria and exclusions are shown for manual review.
- Confirmed eligibility requires verified official-rule provenance (`source_url`, `checked_at`, and `verified=true`); the supplied dataset does not establish this provenance.
- The service uses the persisted Stage 6 model. Retrain and validate artifacts when the cleaned source dataset changes.

## Tests

Backend and frontend dependencies must be installed first. Run `npm run build` in `frontend`. Start both services and test register/login, recommendations, and the metrics page. The current environment used to prepare this package did not have access to your Atlas cluster, so end-to-end behavior against the live records still needs to be verified on your machine.


## Stage 7: eligibility engine and persisted API integration

The Stage 7 report is in `STAGE7_REPORT.txt`. The FastAPI `/recommend` response includes one of four conservative eligibility outcomes, individual structured checks, unknown/failed criteria, manual-review text, and a disclaimer. The implementation was verified with 17 passing Python tests, including API smoke tests. The live MongoDB/browser workflow remains unverified because Atlas credentials and the local environment were not available.

## Stage 8 – frontend eligibility display

The existing React eligibility page posts the profile to the authenticated Node endpoint (`POST /api/schemes/recommend`). Stage 8 now displays each scheme's structured eligibility status and summary, expandable pass/fail/unknown checks, and natural-language criteria/exclusions for manual review. Relevance remains a ranking score, not an eligibility probability. See `STAGE8_REPORT.txt` for validation results and limitations.
