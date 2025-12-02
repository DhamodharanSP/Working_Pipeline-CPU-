import os
import cv2
import time
import json
import requests
import cloudinary
import cloudinary.uploader
from ultralytics import YOLO
from FaceRecognition import load_known_faces, recognize_faces

from summarizer import generate_incident_summary

INPUT_FOLDER = "input_videos"
KNOWN_FACES_DIR = "known_faces"
BACKEND_ENDPOINT = "http://localhost:4000/api/frames"

# --------------------------
# Cloudinary Config
# --------------------------
cloudinary.config(
    cloud_name="dprwjya79",
    api_key="943616652546731",
    api_secret="khRZlG5lvjBiuvzJZZbmdIyf3OE"
)

# --------------------------
# Load models
# --------------------------
print("Loading YOLOv8n...")
yolo = YOLO("yolov8n.pt")

print("Loading known faces...")
known_embeddings, known_names = load_known_faces(KNOWN_FACES_DIR)
print(f"Loaded {len(known_names)} known persons.")


# ------------------------------------------------------
# SEND TO BACKEND
# ------------------------------------------------------
def send_to_backend(data):
    try:
        res = requests.post(BACKEND_ENDPOINT, json=data)
        print("Backend Response:", res.text)
    except Exception as e:
        print("❌ Backend failed:", e)


# ------------------------------------------------------
# PROCESS VIDEO PIPELINE
# ------------------------------------------------------
def process_video(video_path):
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_interval = int(fps // 3)  # reduce fps → 3 FPS for speed

    recognized_once = False
    recognized_name = None
    snapshot_url = None

    print(f"Processing video: {video_path}")

    frame_id = 0
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret: break

        if frame_id % frame_interval != 0:
            frame_id += 1
            continue

        # --------------------------
        # 1) Person Detection (YOLO)
        # --------------------------
        results = yolo(frame)[0]

        for box in results.boxes:
            cls = int(box.cls[0])
            if cls != 0:   # person class id = 0
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            roi = frame[y1:y2, x1:x2]

            # --------------------------
            # 2) Face Recognition
            # --------------------------
            recog = recognize_faces(
                roi,
                known_embeddings,
                known_names,
                threshold=0.45
            )

            if len(recog) == 0:
                continue

            name, score, _ = recog[0]

            # === first successful recognition ===
            if not recognized_once and name != "Unknown":
                recognized_once = True
                recognized_name = name

                # --------------------------
                # Upload snapshot to Cloudinary
                # --------------------------
                upload_res = cloudinary.uploader.upload(
                    cv2.imencode(".jpg", frame)[1].tobytes()
                )
                snapshot_url = upload_res["secure_url"]
                print("Uploaded snapshot:", snapshot_url)

                # --------------------------
                # Generate summary with Gemini
                # --------------------------
                summary = generate_incident_summary(
                    snapshot_url=snapshot_url,
                    category="Face Recognition",
                    suspects=[recognized_name],
                    cam_id="CAM-01"
                )

                # --------------------------
                # Send to backend
                # --------------------------
                payload = {
                    "timestamp": str(time.time()),
                    "duration": "N/A",
                    "description": summary,
                    "imageUrl": snapshot_url,
                    "shortSummary": summary,

                    "weapon": {
                        "detected": False,
                        "weapon_type": "",
                        "confidence": 0.0
                    },

                    "face": {
                        "person_id": recognized_name,
                        "confidence": float(score),
                        "image_url": snapshot_url,
                        "location": "ROI"
                    },

                    "anomaly": {
                        "anomaly_type": "",
                        "severity_score": 0,
                        "description": ""
                    }
                }

                send_to_backend(payload)

        frame_id += 1

    cap.release()
    print("Video processing finished.")


# ------------------------------------------------------
# WATCH FOLDER FOR NEW VIDEOS
# ------------------------------------------------------
def watch_folder():
    print(f"Watching folder: {INPUT_FOLDER}")
    processed = set()

    while True:
        videos = [f for f in os.listdir(INPUT_FOLDER) if f.endswith((".mp4",".avi",".mov"))]

        for v in videos:
            path = os.path.join(INPUT_FOLDER, v)

            if path not in processed:
                processed.add(path)
                process_video(path)

        time.sleep(2)


