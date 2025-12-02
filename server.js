// server.js

const express = require("express");
const cors = require("cors");
const app = express();

app.use(cors());
app.use(express.json());

// -------------------------
// SIMPLE ENDPOINT TO RECEIVE DATA
// -------------------------
app.post("/api/frames", (req, res) => {
  console.log("📩 Incoming Frame Data:");
  console.log(JSON.stringify(req.body, null, 2));

  res.json({
    status: "success",
    message: "Frame data received",
  });
});

// -------------------------
const PORT = 4000;
app.listen(PORT, () => {
  console.log(`🚀 Backend server running on http://localhost:${PORT}`);
});
