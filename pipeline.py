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

# --------------------------
# CONFIGS
# --------------------------
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
# Helper: Format timecodes
# --------------------------
def format_time(seconds):
    seconds = int(seconds)
    m = seconds // 60
    s = seconds % 60
    return f"{m:02d}:{s:02d}"


# --------------------------
# Load Models
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
    print(f"\n🎥 Processing video: {video_path}\n")

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_interval = int(fps // 3)  # reduce fps → ~3 FPS for speed; safe default

    recognized_once = False
    recognized_name = None
    snapshot_url = None

    # Calculate total video duration
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    video_length_sec = total_frames / fps
    duration_str = format_time(video_length_sec)

    frame_id = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

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

            # -------------------------------------------
            # FIRST TIME RECOGNITION TRIGGER
            # -------------------------------------------
            if not recognized_once and name != "Unknown":

                recognized_once = True
                recognized_name = name

                # ---------------------------
                # Draw bounding box + label
                # ---------------------------
                color = (0, 255, 0)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

                label = f"{name} ({score:.2f})"
                cv2.putText(
                    frame, label,
                    (x1, y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, color, 2
                )

                # ---------------------------
                # Upload annotated frame
                # ---------------------------
                success, encoded_image = cv2.imencode(".jpg", frame)
                upload_res = cloudinary.uploader.upload(encoded_image.tobytes())
                snapshot_url = upload_res["secure_url"]

                print("📤 Uploaded annotated snapshot:", snapshot_url)

                # ---------------------------
                # Calculate in-video timestamp
                # ---------------------------
                current_time_sec = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
                timestamp_str = format_time(current_time_sec)

                # ---------------------------
                # Generate summary from Gemini
                # ---------------------------
                summary = generate_incident_summary(
                    snapshot_url=snapshot_url,
                    category="Face Recognition",
                    suspects=[recognized_name],
                    cam_id="CAM-01"
                )

                # ---------------------------
                # SEND DATA TO BACKEND
                # ---------------------------
                payload = {
                    "video_name": os.path.basename(video_path),

                    "timestamp": timestamp_str,      # 00:29 style
                    "duration": duration_str,        # full video duration
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
                        "location": f"{x1},{y1},{x2},{y2}"
                    },

                    "anomaly": {
                        "anomaly_type": "",
                        "severity_score": 0,
                        "description": ""
                    }
                }

                print("📩 Sending payload to backend…")
                send_to_backend(payload)

        frame_id += 1

    cap.release()
    print("🎉 Video processing finished.\n")


# ------------------------------------------------------
# WATCH FOLDER FOR NEW VIDEOS
# ------------------------------------------------------
def watch_folder():
    print(f"👀 Watching folder: {INPUT_FOLDER}")
    processed = set()

    while True:
        videos = [
            f for f in os.listdir(INPUT_FOLDER)
            if f.lower().endswith((".mp4", ".avi", ".mov"))
        ]

        for v in videos:
            path = os.path.join(INPUT_FOLDER, v)

            if path not in processed:
                processed.add(path)
                process_video(path)

        time.sleep(2)


# RUN IF CALLED DIRECTLY
if __name__ == "__main__":
    watch_folder()
