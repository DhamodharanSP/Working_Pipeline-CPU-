import os
import math
import time
import logging
from pathlib import Path

import cv2
import requests
import cloudinary
import cloudinary.uploader
from tqdm import tqdm
from ultralytics import YOLO

# Local code
from FaceRecognition import load_known_faces, recognize_faces
from summarizer import generate_incident_summary


# ============================================================
# CONFIGURATION
# ============================================================
UPLOAD_ROOT = "uploads"
API_BASE = "http://localhost:5000/api"

TARGET_FPS = 10                     # sampling frames per second
FRAME_SAMPLE_THRESHOLD = 0.001
PERSON_CLASS_ID = 0

FACE_COOLDOWN = 5                  # seconds (your selection)

cloudinary.config(
    cloud_name="dprwjya79",
    api_key="943616652546731",
    api_secret="khRZlG5lvjBiuvzJZZbmdIyf3OE"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)


# ============================================================
# MODEL LOADING
# ============================================================
logging.info("Loading YOLOv8 model...")
yolo = YOLO("yolov8n.pt")

logging.info("Loading known faces...")
known_embeddings, known_names = load_known_faces("known_faces")
logging.info(f"Loaded {len(known_names)} known identities.")


# ============================================================
# API HELPERS
# ============================================================
def create_folder(folder_name):
    r = requests.post(f"{API_BASE}/folders", json={
        "name": folder_name,
        "description": "Automated analysis",
        "createdBy": "AI Analyzer"
    })
    r.raise_for_status()
    return r.json()["_id"]


def register_video(folder_id, video_name, duration):
    r = requests.post(f"{API_BASE}/videos", json={
        "folderId": folder_id,
        "originalName": video_name,
        "videoUrl": "",
        "duration": duration
    })
    r.raise_for_status()
    return r.json()["_id"]


def send_frame(folder_id, video_id, payload):
    payload["folderId"] = folder_id
    payload["videoId"] = video_id
    try:
        requests.post(f"{API_BASE}/frames", json=payload)
    except Exception as e:
        logging.error(f"Failed posting frame: {e}")


def complete_video(video_id, payload):
    try:
        requests.post(f"{API_BASE}/videos/{video_id}/complete", json=payload)
    except:
        pass
    logging.info(f"✔ Video completed → {video_id}")


# ============================================================
# HELPERS
# ============================================================
def format_timestamp(seconds):
    s = int(seconds)
    return f"{s//60:02d}:{s%60:02d}"


def upload_frame(frame):
    ok, buf = cv2.imencode(".jpg", frame)
    if not ok:
        return ""
    try:
        upload = cloudinary.uploader.upload(buf.tobytes(), folder="events/")
        return upload.get("secure_url", "")
    except Exception as e:
        logging.error(f"Upload failed: {e}")
        return ""


# ============================================================
# VIDEO PROCESSOR
# ============================================================
def process_video(video_path, folder_id, video_index, total_videos):
    video_name = os.path.basename(video_path)
    logging.info(f"\n🎥 [{video_index}/{total_videos}] Start → {video_name}")

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        logging.error(f"Cannot open video: {video_path}")
        return

    orig_fps = cap.get(cv2.CAP_PROP_FPS) or 24
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_seconds = total_frames / orig_fps
    duration_str = format_timestamp(duration_seconds)

    # Register video
    video_id = register_video(folder_id, video_name, duration_str)

    # Sampling setup
    sample_interval = 1.0 / TARGET_FPS
    next_sample_time = 0.0
    frame_idx = 0

    # Track last upload time per person
    last_uploaded = {}     # { "PersonName": timestamp }

    pbar = tqdm(total=int(duration_seconds * TARGET_FPS), 
                desc=f"Sampling {video_name}", 
                unit="frame", 
                ncols=90)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_time = frame_idx / orig_fps

        if frame_time + FRAME_SAMPLE_THRESHOLD >= next_sample_time:

            # -----------------------------
            # YOLO PERSON DETECTION
            # -----------------------------
            results = yolo(frame, verbose=False)[0]

            persons = []
            for b in results.boxes:
                cls_id = int(b.cls[0])
                if cls_id == PERSON_CLASS_ID:
                    x1, y1, x2, y2 = map(int, b.xyxy[0])
                    persons.append((x1, y1, x2, y2))

            if not persons:
                next_sample_time += sample_interval
                pbar.update(1)
                frame_idx += 1
                continue

            # -----------------------------
            # FACE RECOGNITION
            # -----------------------------
            recognized_faces = []    # list of (name, conf, bbox)

            for (x1, y1, x2, y2) in persons:

                roi = frame[y1:y2, x1:x2]
                fr_results = recognize_faces(roi, known_embeddings, known_names)

                if fr_results:
                    rec_name, rec_conf, box = fr_results[0]
                    recognized_faces.append((rec_name, rec_conf, (x1, y1, x2, y2)))

            # No known faces in frame → skip
            if not recognized_faces:
                next_sample_time += sample_interval
                pbar.update(1)
                frame_idx += 1
                continue

            # -----------------------------
            # APPLY 5-SECOND COOLDOWN
            # -----------------------------
            now = frame_time
            newly_recognized = []

            for name, conf, bbox in recognized_faces:
                last_time = last_uploaded.get(name, -9999)
                if now - last_time >= FACE_COOLDOWN:
                    newly_recognized.append((name, conf, bbox))
                    last_uploaded[name] = now

            # All recognized faces still in cooldown → skip upload
            if not newly_recognized:
                next_sample_time += sample_interval
                pbar.update(1)
                frame_idx += 1
                continue

            # -----------------------------
            # DRAW BBOXES & UPLOAD
            # -----------------------------
            annotated = frame.copy()

            for name, conf, (x1, y1, x2, y2) in newly_recognized:
                cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(annotated, f"{name} {conf:.2f}", 
                            (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6, (0, 255, 0), 2)

            img_url = upload_frame(annotated)

            suspects_list = [name for name, _, _ in newly_recognized]

            # -----------------------------
            # SEND EVENT TO BACKEND
            # -----------------------------
            payload = {
                "timestamp": format_timestamp(frame_time),
                "duration": duration_str,
                "imageUrl": img_url,
                "shortSummary": f"Recognized: {', '.join(suspects_list)}",

                "weapon": {"detected": False, "weapon_type": "", "confidence": 0},
                "face": {
                    "person_id": ", ".join(suspects_list),
                    "confidence": float(newly_recognized[0][1]),
                    "image_url": img_url,
                    "location": ""
                },
                "anomaly": {"anomaly_type": "", "severity_score": 0, "description": ""}
            }

            send_frame(folder_id, video_id, payload)

            logging.info(f"📤 Uploaded event → {suspects_list}")

            next_sample_time += sample_interval
            pbar.update(1)

        frame_idx += 1

    pbar.close()
    cap.release()

    # FINALIZE VIDEO
    complete_video(video_id, {
        "finalSummary": "Face recognition completed",
        "threatLevel": "low",
        "confidence": 0.95
    })

    logging.info(f"✔ Finished video: {video_name}")


# ============================================================
# FOLDER PROCESSOR
# ============================================================
def process_folder(folder_path):
    folder_name = os.path.basename(folder_path)
    logging.info(f"\n📁 Processing folder: {folder_name}")

    folder_id = create_folder(folder_name)

    videos = [
        v for v in sorted(os.listdir(folder_path))
        if v.lower().endswith((".mp4", ".avi", ".mov", ".mkv"))
    ]

    total_videos = len(videos)

    for idx, v in enumerate(videos, start=1):
        process_video(os.path.join(folder_path, v), folder_id, idx, total_videos)


# ============================================================
# WATCHER
# ============================================================
def watch_for_folders():
    Path(UPLOAD_ROOT).mkdir(exist_ok=True)
    logging.info(f"👀 Watching for folders in: {UPLOAD_ROOT}")

    processed = set()

    while True:
        for item in os.listdir(UPLOAD_ROOT):
            path = os.path.join(UPLOAD_ROOT, item)

            if os.path.isdir(path) and item not in processed:
                processed.add(item)
                process_folder(path)

        time.sleep(1)


if __name__ == "__main__":
    watch_for_folders()
