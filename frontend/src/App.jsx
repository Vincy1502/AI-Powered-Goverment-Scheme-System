import { BrowserRouter, Routes, Route } from "react-router-dom";
import Home from "./pages/Home";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Eligibility from "./pages/Eligibility";
import Performance from "./pages/Performance";
import ProtectedRoute from "./components/ProtectedRoute";

export default function App() {
  return <BrowserRouter><Routes>
    <Route path="/" element={<Home />} />
    <Route path="/login" element={<Login />} />
    <Route path="/register" element={<Register />} />
    <Route path="/eligibility" element={<ProtectedRoute><Eligibility /></ProtectedRoute>} />
    <Route path="/performance" element={<ProtectedRoute><Performance /></ProtectedRoute>} />
    <Route path="*" element={<Home />} />
  </Routes></BrowserRouter>;
}
