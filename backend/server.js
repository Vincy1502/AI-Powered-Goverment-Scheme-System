require("dotenv").config();
const express = require("express");
const mongoose = require("mongoose");
const cors = require("cors");
const schemeRoutes = require("./routes/schemeRoutes");
const authRoutes = require("./routes/authRoutes");

const app = express();
const PORT = Number(process.env.PORT || 5000);
if (!process.env.MONGODB_URI) console.error("Missing MONGODB_URI in backend/.env");
if (!process.env.JWT_SECRET || process.env.JWT_SECRET.length < 32) console.error("Set JWT_SECRET to a random secret of at least 32 characters in backend/.env");

app.use(cors({ origin: process.env.FRONTEND_ORIGIN || "http://localhost:5173" }));
app.use(express.json({ limit: "1mb" }));
app.get("/", (_req, res) => res.json({ message: "GovScheme AI API is running", apiVersion: "2.0" }));
app.get("/api/health", (_req, res) => res.json({ api: "ok", database: mongoose.connection.readyState === 1 ? "connected" : "disconnected" }));
app.use("/api/auth", authRoutes);
app.use("/api/schemes", schemeRoutes);

async function start() {
  try {
    if (!process.env.MONGODB_URI) throw new Error("MONGODB_URI is not configured");
    await mongoose.connect(process.env.MONGODB_URI, { serverSelectionTimeoutMS: 10000 });
    console.log("MongoDB connected");
    app.listen(PORT, () => console.log(`GovScheme AI backend listening at http://localhost:${PORT}`));
  } catch (error) {
    console.error("Startup failed:", error.message);
    process.exit(1);
  }
}
start();
