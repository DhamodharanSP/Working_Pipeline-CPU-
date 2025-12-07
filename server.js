const express = require("express");
const cors = require("cors");
const app = express();

app.use(cors());
app.use(express.json());


// ----------------------------------------------------------
// 1️⃣ REGISTER VIDEO  →  POST /api/videos
// ----------------------------------------------------------
app.post("/api/videos", (req, res) => {
  console.log("🎬 Incoming video registration:");
  console.log(JSON.stringify(req.body, null, 2));

  // Simulate DB creation
  const fakeVideoId = "VIDEO_" + Math.floor(Math.random() * 999999);

  res.json({
    _id: fakeVideoId,
    status: "processing",
    message: "Video registered successfully"
  });
});


// ----------------------------------------------------------
// 2️⃣ RECEIVE FRAME DATA  →  POST /api/frames
// ----------------------------------------------------------
app.post("/api/frames", (req, res) => {
  console.log("📩 Incoming Frame Data:");
  console.log(JSON.stringify(req.body, null, 2));

  res.json({
    status: "success",
    message: "Frame data received"
  });
});


// ----------------------------------------------------------
// 3️⃣ MARK VIDEO COMPLETE  →  POST /api/videos/:id/complete
// ----------------------------------------------------------
app.post("/api/videos/:id/complete", (req, res) => {
  console.log("🏁 Video Completed:", req.params.id);
  console.log("Summary:", JSON.stringify(req.body, null, 2));

  res.json({
    status: "completed",
    videoId: req.params.id,
    message: "Video processing finished"
  });
});


// ----------------------------------------------------------
const PORT = 5000;
app.listen(PORT, () => {
  console.log(`🚀 Backend running at http://localhost:${PORT}`);
});
