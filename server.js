// const express = require("express");
// const cors = require("cors");
// const mongoose = require("mongoose");

// // --------------------------------------------------
// // APP INIT
// // --------------------------------------------------
// const app = express();
// app.use(cors());
// app.use(express.json({ limit: "20mb" }));

// // --------------------------------------------------
// // DB CONNECTION
// // --------------------------------------------------
// mongoose
//   .connect("mongodb://127.0.0.1:27017/video_analysis")
//   .then(() => console.log("✅ MongoDB Connected"))
//   .catch((err) => {
//     console.error("❌ MongoDB Error:", err.message);
//     process.exit(1);
//   });

// // --------------------------------------------------
// // SCHEMAS & MODELS
// // --------------------------------------------------

// // -------- Folder Schema
// const folderSchema = new mongoose.Schema(
//   {
//     name: String,
//     description: String,
//     createdBy: String,
//     videos: [{ type: mongoose.Schema.Types.ObjectId, ref: "Video" }]
//   },
//   { timestamps: true }
// );
// const Folder = mongoose.model("Folder", folderSchema);

// // -------- Video Schema
// const timelineSchema = new mongoose.Schema(
//   {
//     time: String,
//     event: String
//   },
//   { _id: false }
// );

// const videoSchema = new mongoose.Schema(
//   {
//     folderId: { type: mongoose.Schema.Types.ObjectId, ref: "Folder" },

//     originalName: String,
//     videoUrl: String,
//     duration: String,

//     shortSummary: String,
//     finalSummary: String,

//     threatLevel: {
//       type: String,
//       enum: ["low", "medium", "high"],
//       default: "low"
//     },

//     confidence: Number,
//     status: { type: String, default: "processing" },

//     timeline: [timelineSchema],

//     overallStats: {
//       totalWeapons: { type: Number, default: 0 },
//       totalAnomalies: { type: Number, default: 0 },
//       totalFaces: { type: Number, default: 0 },
//       highestSeverity: { type: Number, default: 0 }
//     }
//   },
//   { timestamps: true }
// );

// const Video = mongoose.model("Video", videoSchema);

// // -------- Frame Schema
// const frameSchema = new mongoose.Schema(
//   {
//     videoId: { type: mongoose.Schema.Types.ObjectId, ref: "Video" },
//     folderId: { type: mongoose.Schema.Types.ObjectId, ref: "Folder" },

//     timestamp: String,
//     duration: String,
//     imageUrl: String,
//     shortSummary: String,

//     weapon: Object,
//     face: Object,
//     anomaly: Object
//   },
//   { timestamps: true }
// );

// const Frame = mongoose.model("Frame", frameSchema);

// // --------------------------------------------------
// // ROUTES
// // --------------------------------------------------

// // ---------------- CREATE FOLDER ----------------
// app.post("/api/folders", async (req, res) => {
//   try {
//     const folder = await Folder.create(req.body);
//     res.status(201).json(folder);
//   } catch (err) {
//     res.status(500).json({ message: err.message });
//   }
// });

// // ---------------- CREATE VIDEO ----------------
// app.post("/api/videos", async (req, res) => {
//   try {
//     const video = await Video.create(req.body);

//     await Folder.updateOne(
//       { _id: req.body.folderId },
//       { $push: { videos: video._id } }
//     );

//     res.status(201).json(video);
//   } catch (err) {
//     res.status(500).json({ message: err.message });
//   }
// });

// // ---------------- COMPLETE VIDEO ----------------
// app.post("/api/videos/:id/complete", async (req, res) => {
//   try {
//     const video = await Video.findByIdAndUpdate(
//       req.params.id,
//       { ...req.body, status: "completed" },
//       { new: true }
//     );

//     res.json(video);
//   } catch (err) {
//     res.status(500).json({ message: err.message });
//   }
// });

// // ---------------- GET VIDEO ----------------
// app.get("/api/videos/:id", async (req, res) => {
//   try {
//     const video = await Video.findById(req.params.id);
//     res.json(video);
//   } catch (err) {
//     res.status(500).json({ message: err.message });
//   }
// });

// // ---------------- FRAME UPLOAD ----------------
// app.post("/api/frames", async (req, res) => {
//   try {
//     const frame = await Frame.create(req.body);

//     const { weapon, anomaly } = req.body;
//     const inc = {};

//     if (weapon?.detected) inc["overallStats.totalWeapons"] = 1;
//     if (anomaly?.anomaly_type) inc["overallStats.totalAnomalies"] = 1;
//     if (req.body.face?.person_id) inc["overallStats.totalFaces"] = 1;

//     const update = { $inc: inc };

//     if (anomaly?.severity_score !== undefined) {
//       update.$max = {
//         "overallStats.highestSeverity": anomaly.severity_score
//       };
//     }

//     if (weapon?.detected || anomaly?.anomaly_type) {
//       update.$push = {
//         timeline: {
//           time: req.body.timestamp,
//           event: req.body.shortSummary || "Event detected"
//         }
//       };
//     }

//     await Video.updateOne({ _id: req.body.videoId }, update);

//     res.status(201).json(frame);
//   } catch (err) {
//     res.status(500).json({ message: err.message });
//   }
// });

// // --------------------------------------------------
// // START SERVER
// // --------------------------------------------------
// const PORT = 5000;
// app.listen(PORT, () => {
//   console.log(`🚀 Server running at http://localhost:${PORT}`);
// });


// server.js

const express = require("express");
const cors = require("cors");
const mongoose = require("mongoose");

const app = express();
app.use(cors());
app.use(express.json({ limit: "20mb" }));

// --------------------------------------------------
// CONNECT MONGO
// --------------------------------------------------
mongoose
  .connect("mongodb://127.0.0.1:27017/video_analysis")
  .then(() => console.log("✅ MongoDB Connected"))
  .catch((err) => {
    console.error("❌ MongoDB Error:", err.message);
    process.exit(1);
  });


// --------------------------------------------------
// IMPORT MODELS
// --------------------------------------------------
const Folder = require("./models/Folder");
const Video = require("./models/Video");
const Frame = require("./models/Frame");


// --------------------------------------------------
// LOGGING UTILITIES
// --------------------------------------------------
function logDivider(title) {
  console.log("\n------------------------------------------------------------");
  console.log(`📝 ${title}`);
  console.log("------------------------------------------------------------");
}


// --------------------------------------------------
// CREATE FOLDER
// --------------------------------------------------
app.post("/api/folders", async (req, res) => {
  try {
    logDivider("NEW FOLDER REQUEST");

    const folder = await Folder.create(req.body);

    console.log("📁 Folder Created:");
    console.log("ID:", folder._id);
    console.log("Name:", folder.name);
    console.log("Created By:", folder.createdBy);

    res.status(201).json(folder);
  } catch (err) {
    console.error("❌ Folder Error:", err.message);
    res.status(500).json({ message: err.message });
  }
});


// --------------------------------------------------
// REGISTER NEW VIDEO
// --------------------------------------------------
app.post("/api/videos", async (req, res) => {
  try {
    logDivider("NEW VIDEO REQUEST");

    const video = await Video.create(req.body);

    console.log("🎬 New Video Registered:");
    console.log("Video ID:", video._id);
    console.log("Folder ID:", video.folderId);
    console.log("Original Name:", video.originalName);
    console.log("Duration:", video.duration);

    // Link inside Folder
    await Folder.updateOne(
      { _id: req.body.folderId },
      { $push: { videos: video._id } }
    );

    console.log("🔗 Video linked inside Folder.");

    res.status(201).json(video);
  } catch (err) {
    console.error("❌ Video Creation Error:", err.message);
    res.status(500).json({ message: err.message });
  }
});


// --------------------------------------------------
// FRAME EVENT RECEIVED
// --------------------------------------------------
app.post("/api/frames", async (req, res) => {
  try {
    logDivider("FRAME RECEIVED");

    const frame = await Frame.create(req.body);

    console.log("🖼 Frame Stored:");
    console.log("Frame ID:", frame._id);
    console.log("Video ID:", frame.videoId);
    console.log("Timestamp:", frame.timestamp);
    console.log("Summary:", frame.shortSummary);

    let inc = {};

    if (req.body.weapon?.detected)
      inc["overallStats.totalWeapons"] = 1;

    if (req.body.face?.person_id)
      inc["overallStats.totalFaces"] = 1;

    if (req.body.anomaly?.anomaly_type)
      inc["overallStats.totalAnomalies"] = 1;

    let update = {};
    if (Object.keys(inc).length > 0) {
      update.$inc = inc;
    }

    if (req.body.anomaly?.severity_score) {
      update.$max = {
        "overallStats.highestSeverity": req.body.anomaly.severity_score
      };
    }

    // Push timeline event only for meaningful frames
    update.$push = {
      timeline: {
        time: req.body.timestamp,
        event: req.body.shortSummary
      }
    };

    await Video.updateOne({ _id: req.body.videoId }, update);

    console.log("📈 Video Stats Updated:");

    if (inc["overallStats.totalFaces"]) console.log(" + Face Detected");
    if (inc["overallStats.totalWeapons"]) console.log(" + Weapon Detected");
    if (inc["overallStats.totalAnomalies"]) console.log(" + Anomaly Event");

    console.log("🕒 Timeline updated with new event.");

    res.status(201).json(frame);
  } catch (err) {
    console.error("❌ Frame Error:", err.message);
    res.status(500).json({ message: err.message });
  }
});


// --------------------------------------------------
// COMPLETE VIDEO
// --------------------------------------------------
app.post("/api/videos/:id/complete", async (req, res) => {
  try {
    logDivider("VIDEO COMPLETION");

    const videoId = req.params.id;

    const updated = await Video.findByIdAndUpdate(
      videoId,
      { ...req.body, status: "completed" },
      { new: true }
    );

    console.log("🏁 Video Marked as Completed");
    console.log("Video ID:", videoId);
    console.log("Final Summary:", updated.finalSummary);
    console.log("Threat Level:", updated.threatLevel);
    console.log("Confidence:", updated.confidence);
    console.log("Status:", updated.status);

    res.json(updated);
  } catch (err) {
    console.error("❌ Video Complete Error:", err.message);
    res.status(500).json({ message: err.message });
  }
});


// --------------------------------------------------
// START SERVER
// --------------------------------------------------
const PORT = 5000;
app.listen(PORT, () => {
  console.log(`🚀 Backend running at http://localhost:${PORT}`);
});
