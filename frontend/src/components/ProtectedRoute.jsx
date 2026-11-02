import { Navigate, useLocation } from "react-router-dom";
export default function ProtectedRoute({ children }) {
  const location = useLocation();
  return localStorage.getItem("govscheme_token") ? children : <Navigate to="/login" replace state={{ from: location.pathname }} />;
}
