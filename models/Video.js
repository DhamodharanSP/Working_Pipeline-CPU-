const mongoose = require("mongoose");

// Timeline events
const timelineSchema = new mongoose.Schema({
  time: String,
  event: String
}, { _id: false });

const videoSchema = new mongoose.Schema({

  folderId: { type: mongoose.Schema.Types.ObjectId, ref: "Folder" },

  originalName: String,
  videoUrl: String,
  duration: String,

  shortSummary: String,
  finalSummary: String,

  threatLevel: {
    type: String,
    enum: ["low", "medium", "high"],
    default: "low"
  },

  confidence: Number,
  status: { type: String, default: "processing" },

  timeline: [timelineSchema],

  overallStats: {
    totalFaces: { type: Number, default: 0 },
    totalWeapons: { type: Number, default: 0 },
    totalAnomalies: { type: Number, default: 0 },
    highestSeverity: { type: Number, default: 0 }
  }

}, { timestamps: true });

module.exports = mongoose.model("Video", videoSchema);
