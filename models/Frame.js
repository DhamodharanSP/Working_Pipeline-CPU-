const mongoose = require("mongoose");

const frameSchema = new mongoose.Schema({

  folderId: { type: mongoose.Schema.Types.ObjectId, ref: "Folder" },
  videoId:  { type: mongoose.Schema.Types.ObjectId, ref: "Video" },

  timestamp: String,
  duration: String,
  imageUrl: String,
  shortSummary: String,

  weapon: {
    detected: Boolean,
    weapon_type: String,
    confidence: Number
  },

  face: {
    person_id: String,
    confidence: Number,
    image_url: String,
    location: String
  },

  anomaly: {
    anomaly_type: String,
    severity_score: Number,
    description: String
  }

}, { timestamps: true });

module.exports = mongoose.model("Frame", frameSchema);
