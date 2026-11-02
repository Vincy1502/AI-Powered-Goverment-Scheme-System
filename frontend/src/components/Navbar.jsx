import { Link, useNavigate } from "react-router-dom";

export default function Navbar() {
  const navigate = useNavigate();
  const user = (() => { try { return JSON.parse(localStorage.getItem("govscheme_user") || "null"); } catch { return null; } })();
  function logout() {
    localStorage.removeItem("govscheme_token");
    localStorage.removeItem("govscheme_user");
    navigate("/login");
  }
  return <header className="site-header"><nav className="navbar container">
    <Link className="brand" to="/"><span className="brand-mark">G</span><span>GovScheme<span className="brand-ai"> AI</span><small>Government benefits, made clearer</small></span></Link>
    <div className="nav-links"><Link to="/">Home</Link><Link to="/eligibility">Find schemes</Link>{user && <Link to="/performance">ML performance</Link>}
      {user ? <><span className="nav-user">Hi, {user.name?.split(" ")[0] || "there"}</span><button className="button button-ghost button-small" onClick={logout}>Log out</button></> : <><Link to="/login">Log in</Link><Link className="button button-primary button-small" to="/register">Create account</Link></>}
    </div>
  </nav></header>;
}
