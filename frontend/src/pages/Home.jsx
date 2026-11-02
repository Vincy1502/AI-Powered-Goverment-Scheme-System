import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import Navbar from "../components/Navbar";
import { API_URL } from "../lib/api";

const features = [
  { icon: "✳", title: "Personalised discovery", text: "Explore schemes ranked against the details you choose, using your live scheme catalogue." },
  { icon: "⌁", title: "Eligibility-aware guidance", text: "Review source eligibility conditions and understand what still needs to be verified." },
  { icon: "▤", title: "Transparent recommendations", text: "See why a scheme appeared, with relevance scores clearly separated from eligibility decisions." }
];
export default function Home() {
  const loggedIn = Boolean(localStorage.getItem("govscheme_token"));
  const [recordCount, setRecordCount] = useState(null);
  useEffect(() => {
    fetch(`${API_URL}/api/schemes`).then(r => { if (!r.ok) throw new Error("Catalogue unavailable"); return r.json(); })
      .then(data => setRecordCount(Array.isArray(data) ? data.length : null)).catch(() => setRecordCount(null));
  }, []);
  return <><Navbar /><main>
    <section className="hero-section"><div className="container hero-grid"><div className="hero-copy"><div className="eyebrow"><span className="eyebrow-dot" /> AI-ASSISTED SCHEME DISCOVERY</div>
      <h1>Find support that<br/><span>fits your journey.</span></h1>
      <p className="hero-lead">Government schemes can be hard to navigate. Tell us a little about yourself and discover relevant opportunities from our scheme catalogue.</p>
      <div className="hero-actions"><Link className="button button-primary button-large" to={loggedIn ? "/eligibility" : "/register"}>Find my schemes <span>↗</span></Link><a className="text-link" href="#how-it-works">How it works <span>↓</span></a></div>
      <div className="hero-trust"><span>✓</span> Recommendations are guidance, not official eligibility decisions.</div>
    </div><div className="hero-art" aria-label="Scheme discovery illustration"><div className="art-orbit orbit-one"/><div className="art-orbit orbit-two"/><div className="art-glow"/><div className="art-card art-card-main"><div className="art-card-top"><span className="art-icon">✳</span><span className="status-pill"><i/> Discovery engine</span></div><p className="art-kicker">YOUR NEXT STEP</p><h3>Opportunity<br/>starts with clarity.</h3><div className="art-lines"><i/><i/><i/></div><div className="art-card-bottom"><span>Profile matching</span><b>● ● ●</b></div></div><div className="floating-chip chip-top"><span>⌕</span> Personalised search</div><div className="floating-chip chip-bottom"><span>✓</span> Transparent results</div><div className="art-spark spark-one">✦</div><div className="art-spark spark-two">✧</div></div></div></section>
    <section className="stats-strip"><div className="container stats-grid"><div><strong>{recordCount === null ? "Live" : recordCount.toLocaleString()}</strong><span>scheme records in the connected catalogue</span></div><div><strong>AI + NLP</strong><span>text-based relevance ranking</span></div><div><strong>Source-first</strong><span>review the official conditions before applying</span></div></div></section>
    <section className="features-section" id="how-it-works"><div className="container"><div className="section-heading"><div className="eyebrow">MADE TO BE CLEAR</div><h2>Less searching.<br/><span>More understanding.</span></h2><p>Useful guidance starts with relevant information and honest explanations.</p></div><div className="feature-grid">{features.map((feature, i) => <article className="feature-card" key={feature.title}><div className={`feature-icon feature-icon-${i}`}>{feature.icon}</div><span className="feature-number">0{i + 1}</span><h3>{feature.title}</h3><p>{feature.text}</p></article>)}</div><div className="cta-panel"><div><span className="eyebrow">READY WHEN YOU ARE</span><h2>Start with your profile.</h2><p>It only takes a few details to begin exploring relevant schemes.</p></div><Link className="button button-light button-large" to={loggedIn ? "/eligibility" : "/register"}>Get started <span>↗</span></Link></div></div></section>
  </main><footer className="site-footer"><div className="container footer-inner"><Link className="brand footer-brand" to="/"><span className="brand-mark">G</span><span>GovScheme<span className="brand-ai"> AI</span><small>Government benefits, made clearer</small></span></Link><p>AI-assisted discovery. Always verify final eligibility with the official scheme authority.</p><span>© {new Date().getFullYear()} GovScheme AI</span></div></footer></>;
}
