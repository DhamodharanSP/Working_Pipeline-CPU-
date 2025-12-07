const mongoose = require("mongoose");

const folderSchema = new mongoose.Schema({
  name: { type: String, required: true },
  description: String,
  createdBy: String,

  videos: [
    { type: mongoose.Schema.Types.ObjectId, ref: "Video" }
  ]

}, { timestamps: true });

module.exports = mongoose.model("Folder", folderSchema);
