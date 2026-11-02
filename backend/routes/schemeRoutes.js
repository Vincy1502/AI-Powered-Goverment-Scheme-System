const express = require("express");
const Scheme = require("../models/Scheme");
const { requireAuth } = require("../middleware/auth");

const router = express.Router();
const ML_URL = (process.env.ML_SERVICE_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

router.get("/", async (req, res) => {
  try {
    const schemes = await Scheme.find().lean();
    res.json(schemes);
  } catch (error) {
    console.error("Scheme fetch error:", error.message);
    res.status(500).json({ message: "Error fetching schemes." });
  }
});

router.post("/recommend", requireAuth, async (req, res) => {
  try {
    const { name, age, gender, state, occupation, income, category, query } = req.body;
    if (!state || !occupation) return res.status(400).json({ message: "State and occupation are required." });
    const schemes = await Scheme.find().lean();
    if (!schemes.length) return res.status(503).json({ message: "No scheme records are available in MongoDB yet." });
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 20000);
    let mlResponse;
    try {
      mlResponse = await fetch(`${ML_URL}/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          profile: { name, age: age === "" ? null : Number(age), gender, state, occupation, income: income === "" ? null : Number(income), category, query: query || "" },
          schemes
        }),
        signal: controller.signal
      });
    } finally { clearTimeout(timeout); }
    if (!mlResponse.ok) {
      const details = await mlResponse.text();
      console.error("ML service error:", mlResponse.status, details.slice(0, 300));
      return res.status(502).json({ message: "The ML recommendation service returned an error. Check that FastAPI is running." });
    }
    const result = await mlResponse.json();
    res.json({ ...result, sourceRecordCount: schemes.length });
  } catch (error) {
    console.error("Recommendation error:", error.message);
    if (error.name === "AbortError") return res.status(504).json({ message: "ML service timed out. Please try again." });
    if (error.cause || error.message.includes("fetch failed")) return res.status(503).json({ message: "Cannot connect to the Python ML service. Start FastAPI and try again." });
    res.status(500).json({ message: "Could not generate recommendations." });
  }
});

router.post("/ml-comparison", requireAuth, async (req, res) => {
  try {
    const schemes = await Scheme.find().lean();
    const response = await fetch(`${ML_URL}/compare`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile: req.body || {}, schemes, limit: 5 })
    });
    if (!response.ok) return res.status(502).json({ message: "Could not compare the recommendation methods." });
    res.json(await response.json());
  } catch (error) {
    console.error("ML comparison error:", error.message);
    res.status(503).json({ message: "ML service is unavailable. Start FastAPI first." });
  }
});

router.get("/ml-performance", requireAuth, async (req, res) => {
  try {
    const schemes = await Scheme.find().lean();
    const response = await fetch(`${ML_URL}/metrics`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ schemes })
    });
    if (!response.ok) return res.status(502).json({ message: "Could not get metrics from the ML service." });
    res.json(await response.json());
  } catch (error) {
    console.error("Metrics error:", error.message);
    res.status(503).json({ message: "ML service is unavailable. Start FastAPI first." });
  }
});

module.exports = router;
