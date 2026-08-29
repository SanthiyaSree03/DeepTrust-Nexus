const express = require("express");
const cors = require("cors");
require("dotenv").config();

const app = express();

const PORT = process.env.PORT || 5000;

// Middleware
app.use(cors());
app.use(express.json());

// Health check
app.get("/api/health", (req, res) => {
  res.json({
    success: true,
    message: "DeepTrust Nexus Backend is running",
  });
});

// Start server
app.listen(PORT, () => {
  console.log(`DeepTrust Nexus Backend running on port ${PORT}`);
});
