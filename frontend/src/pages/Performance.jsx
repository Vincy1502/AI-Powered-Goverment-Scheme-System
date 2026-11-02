import { useEffect, useState } from "react";
import Navbar from "../components/Navbar";
import { apiRequest } from "../lib/api";

export default function Performance() {
  const [metrics, setMetrics] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [comparison, setComparison] = useState(null);
  const [compareError, setCompareError] = useState("");
  const [compareBusy, setCompareBusy] = useState(false);
  const [profile, setProfile] = useState({ state: "Tamil Nadu", occupation: "Student", gender: "", category: "General", age: "", income: "", query: "education scholarship" });

  useEffect(() => {
    apiRequest("/api/schemes/ml-performance").then(setMetrics).catch(e => setError(e.message)).finally(() => setLoading(false));
  }, []);

  function updateProfile(e) { setProfile({ ...profile, [e.target.name]: e.target.value }); }
  async function compare(e) {
    e.preventDefault(); setCompareError(""); setComparison(null); setCompareBusy(true);
    try { setComparison(await apiRequest("/api/schemes/ml-comparison", { method: "POST", body: JSON.stringify(profile) })); }
    catch (err) { setCompareError(err.message); }
    finally { setCompareBusy(false); }
  }

  return <><Navbar /><main className="workspace-page"><div className="container performance-container">
    <div className="page-heading"><div><div className="eyebrow">MODEL MONITORING</div><h1>Model performance <span>& diagnostics.</span></h1><p>Live corpus and TF-IDF fitting diagnostics from your MongoDB scheme records.</p></div><div className="page-heading-badge"><span>⌁</span><div><strong>Transparent metrics</strong><small>No invented scores</small></div></div></div>
    {loading && <div className="panel-loading">Reading live scheme data and fitting the text representation…</div>}
    {error && <div className="alert alert-error"><strong>Could not load performance diagnostics</strong><p>{error}</p><small>Make sure the backend and FastAPI ML service are running.</small></div>}
    {metrics && <>
      <div className="metrics-grid">
        <article className="metric-card"><span>Scheme records received</span><strong>{metrics.records_received ?? "—"}</strong><small>Live database corpus</small></article>
        <article className="metric-card"><span>Records used</span><strong>{metrics.records_used ?? "—"}</strong><small>Non-empty scheme text</small></article>
        <article className="metric-card"><span>Vocabulary size</span><strong>{metrics.vocabulary_size?.toLocaleString?.() ?? "—"}</strong><small>TF-IDF word features</small></article>
        <article className="metric-card"><span>Fit time</span><strong>{metrics.fit_time_ms != null ? `${metrics.fit_time_ms} ms` : "—"}</strong><small>Measured during this fit</small></article>
        <article className="metric-card"><span>Non-zero weights</span><strong>{metrics.nonzero_tfidf_weights?.toLocaleString?.() ?? "—"}</strong><small>Document-term matrix</small></article>
        <article className="metric-card"><span>Matrix sparsity</span><strong>{metrics.matrix_sparsity_percent != null ? `${metrics.matrix_sparsity_percent}%` : "—"}</strong><small>Zero-valued matrix cells</small></article>
      </div>
      <section className="performance-panel"><div className="panel-heading"><div className="panel-icon">01</div><div><h2>What these numbers mean</h2><p>Measured diagnostics of the actual scheme text corpus.</p></div></div>
        <div className="performance-detail-grid"><div><span>Selected method</span><strong>{metrics.method || "TF-IDF + cosine similarity"}</strong><p>{metrics.method_type || "Content-based NLP ranking"}</p></div><div><span>Corpus status</span><strong>{metrics.status || "Unknown"}</strong><p>Fingerprint: <code>{metrics.corpus_sha256 ? `${metrics.corpus_sha256.slice(0, 16)}…` : "not available"}</code></p></div></div>
        <div className="alert alert-warning"><strong>Accuracy / precision / recall / F1 are not available yet.</strong><p>{metrics.evaluation_note || "No verified user-scheme labels have been supplied. These metrics must not be invented."}</p></div>
        <p className="metric-explainer">TF-IDF vocabulary size, matrix sparsity and fit time describe the fitted text representation. They do not prove recommendation quality. To calculate valid ranking metrics, provide independently reviewed relevance judgements and run the ranking evaluation endpoint.</p>
      </section>
      <section className="performance-panel"><div className="panel-heading"><div className="panel-icon">02</div><div><h2>Compare the two recommenders</h2><p>Run both methods against the same live scheme records and profile.</p></div></div>
        <form className="comparison-form" onSubmit={compare}>
          <label>State<select name="state" value={profile.state} onChange={updateProfile}><option>Tamil Nadu</option><option>Kerala</option><option>Karnataka</option><option>Andhra Pradesh</option><option>Telangana</option><option>Maharashtra</option><option>Delhi</option><option>Other</option></select></label>
          <label>Occupation<select name="occupation" value={profile.occupation} onChange={updateProfile}><option>Student</option><option>Farmer</option><option>Employee</option><option>Business</option><option>Unemployed</option><option>Other</option></select></label>
          <label>Gender<select name="gender" value={profile.gender} onChange={updateProfile}><option value="">Not specified</option><option>Female</option><option>Male</option><option>Other</option></select></label>
          <label>Category<select name="category" value={profile.category} onChange={updateProfile}><option>General</option><option>SC</option><option>ST</option><option>OBC</option><option>Other</option></select></label>
          <label>Age (optional)<input type="number" name="age" min="0" max="120" value={profile.age} onChange={updateProfile} placeholder="e.g. 23" /></label>
          <label>Income (optional)<input type="number" name="income" min="0" value={profile.income} onChange={updateProfile} placeholder="Annual family income" /></label>
          <label className="comparison-query">Support / search phrase<input name="query" value={profile.query} onChange={updateProfile} placeholder="e.g. education scholarship" /></label>
          <button className="button button-primary button-large" disabled={compareBusy}>{compareBusy ? "Comparing…" : "Compare on live data"}<span>↗</span></button>
        </form>
        {compareError && <div className="alert alert-error">{compareError}</div>}
        {comparison && <>
          <div className="comparison-summary"><div><span>Records compared</span><strong>{comparison.records_compared}</strong></div><div><span>Legacy method runtime</span><strong>{comparison.baseline_runtime_ms} ms</strong></div><div><span>TF-IDF runtime</span><strong>{comparison.ml_runtime_ms} ms</strong></div><div><span>Top-5 overlap</span><strong>{comparison.top_k_overlap_count} / {comparison.limit}</strong><small>Jaccard {comparison.top_k_jaccard_percent}%</small></div></div>
          <div className="comparison-lists"><div className="comparison-list"><h3>Existing keyword scoring</h3>{comparison.baseline_top_k.length ? comparison.baseline_top_k.map((x,i)=><div className="comparison-item" key={`${x.scheme_name}-${i}`}><b>{i+1}</b><span>{x.scheme_name}</span><small>score {x.score}</small></div>) : <p className="no-list">No records met the old score threshold.</p>}</div><div className="comparison-list"><h3>TF-IDF + cosine similarity</h3>{comparison.ml_top_k.length ? comparison.ml_top_k.map((x,i)=><div className="comparison-item" key={`${x.scheme_name}-${i}`}><b>{i+1}</b><span>{x.scheme_name}</span><small>{x.relevance_percent}%</small></div>) : <p className="no-list">No positive text matches for this profile.</p>}</div></div>
          <div className="alert alert-warning"><strong>Interpret the comparison carefully.</strong><p>{comparison.interpretation}</p></div>
        </>}
      </section>
      <section className="performance-panel"><div className="panel-heading"><div className="panel-icon">03</div><div><h2>Evaluation status</h2><p>Honest reporting for your academic project.</p></div></div><div className="evaluation-status"><span className="status-icon">!</span><div><strong>Ground-truth relevance labels not configured</strong><p>Prepare reviewed test profiles with scheme names that are genuinely relevant for each profile. Only then report Precision@K, Recall@K and Mean Reciprocal Rank. Classification metrics require verified binary or multiclass labels.</p></div></div></section>
    </>}
  </div></main></>;
}
