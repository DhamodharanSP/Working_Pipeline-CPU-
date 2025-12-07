


# # pipeline.py
# import os
# import math
# import time
# import logging
# from pathlib import Path

# import cv2
# import requests
# import cloudinary
# import cloudinary.uploader
# from tqdm import tqdm
# from ultralytics import YOLO

# # Local modules (your existing files)
# from FaceRecognition import load_known_faces, recognize_faces
# from summarizer import generate_incident_summary

# # ---------------------------
# # CONFIG
# # ---------------------------
# UPLOAD_ROOT = "uploads"                     # Drop folders here
# API_BASE = "http://localhost:5000/api"      # Your backend
# CLOUDINARY_FOLDER = "events/"

# # Sampling / processing
# TARGET_FPS = 10                # desired effective FPS to sample (Option B)
# FRAME_SAMPLE_THRESHOLD = 0.001 # small tolerance for time checks
# PERSON_CLASS_ID = 0            # YOLO class id for person

# # Cloudinary config (keep as you have)
# cloudinary.config(
#     cloud_name="dprwjya79",
#     api_key="943616652546731",
#     api_secret="khRZlG5lvjBiuvzJZZbmdIyf3OE"
# )

# # Logging
# logging.basicConfig(
#     level=logging.INFO,
#     format="%(asctime)s | %(levelname)s | %(message)s",
#     datefmt="%H:%M:%S",
# )

# # ---------------------------
# # Load models + faces
# # ---------------------------
# logging.info("Loading YOLO model...")
# yolo = YOLO("yolov8n.pt")

# logging.info("Loading known faces...")
# known_embeddings, known_names = load_known_faces("known_faces")
# logging.info(f"Loaded {len(known_names)} known persons.")


# # ---------------------------
# # Backend API wrappers
# # ---------------------------
# def create_folder(folder_name):
#     payload = {
#         "name": folder_name,
#         "description": "Automated face recognition analysis",
#         "createdBy": "AI Analyzer"
#     }
#     r = requests.post(f"{API_BASE}/folders", json=payload)
#     r.raise_for_status()
#     folder_id = r.json()["_id"]
#     logging.info(f"Folder created -> {folder_name} (id={folder_id})")
#     return folder_id


# def register_video(folder_id, video_name, duration):
#     payload = {
#         "folderId": folder_id,
#         "originalName": video_name,
#         "videoUrl": "",
#         "duration": duration
#     }
#     r = requests.post(f"{API_BASE}/videos", json=payload)
#     r.raise_for_status()
#     video_id = r.json()["_id"]
#     logging.info(f"Video registered -> {video_name} (id={video_id})")
#     return video_id


# def send_frame(folder_id, video_id, payload):
#     # server expects folderId + videoId included
#     payload["folderId"] = folder_id
#     payload["videoId"] = video_id
#     try:
#         r = requests.post(f"{API_BASE}/frames", json=payload, timeout=10)
#         # not raising here to avoid stopping the whole pipeline on a single network glitch
#         if r.status_code >= 400:
#             logging.warning(f"POST /frames returned {r.status_code}: {r.text}")
#     except Exception as e:
#         logging.error(f"Failed to POST frame: {e}")


# def complete_video(video_id, payload):
#     try:
#         r = requests.post(f"{API_BASE}/videos/{video_id}/complete", json=payload, timeout=10)
#         if r.status_code >= 400:
#             logging.warning(f"POST /videos/{video_id}/complete returned {r.status_code}: {r.text}")
#     except Exception as e:
#         logging.error(f"Failed to POST complete video: {e}")
#     logging.info(f"Marked video completed -> {video_id}")


# # ---------------------------
# # Helpers
# # ---------------------------
# def format_timestamp(seconds):
#     """Return HH:MM:SS or MM:SS depending on duration."""
#     try:
#         s = int(seconds)
#     except Exception:
#         s = 0
#     h = s // 3600
#     m = (s % 3600) // 60
#     sec = s % 60
#     if h > 0:
#         return f"{h:02d}:{m:02d}:{sec:02d}"
#     return f"{m:02d}:{sec:02d}"


# def upload_annotated_frame(frame, public_id=None):
#     """Upload annotated frame (numpy BGR) to Cloudinary and return url (or None)."""
#     try:
#         ok, buf = cv2.imencode(".jpg", frame)
#         if not ok:
#             return None
#         res = cloudinary.uploader.upload(
#             buf.tobytes(),
#             folder=CLOUDINARY_FOLDER,
#             public_id=public_id,
#             resource_type="image"
#         )
#         return res.get("secure_url")
#     except Exception as e:
#         logging.error(f"Cloudinary upload failed: {e}")
#         return None


# # ---------------------------
# # Core: process single video
# # ---------------------------
# def process_video(video_path, folder_id, video_index=1, total_videos=1):
#     video_name = os.path.basename(video_path)
#     logging.info(f"[{video_index}/{total_videos}] Start processing video: {video_name}")

#     cap = cv2.VideoCapture(video_path)
#     if not cap.isOpened():
#         logging.error(f"Cannot open video: {video_path}")
#         return

#     orig_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
#     total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
#     duration_seconds = (total_frames / orig_fps) if orig_fps else 0
#     duration_str = format_timestamp(duration_seconds)

#     # Register video in backend (Mongo)
#     video_id = register_video(folder_id, video_name, duration_str)

#     # compute sampling times (Option B)
#     sample_interval = 1.0 / TARGET_FPS
#     # total samples expected (rounded)
#     total_samples = max(1, int(math.ceil(duration_seconds * TARGET_FPS)))

#     logging.info(f"Video fps: {orig_fps:.2f}, frames: {total_frames}, duration: {duration_seconds:.2f}s")
#     logging.info(f"Sampling: target_fps={TARGET_FPS}, samples ~ {total_samples}")

#     # progress bar over samples (not raw frames)
#     pbar = tqdm(total=total_samples, desc=f"{video_name}", unit="sample", ncols=90)

#     next_sample_time = 0.0
#     frame_idx = 0
#     samples_sent = 0
#     frames_read = 0

#     try:
#         while True:
#             ret, frame = cap.read()
#             if not ret:
#                 break

#             frames_read += 1
#             frame_time = (frame_idx / orig_fps) if orig_fps else 0.0

#             # If the frame's timestamp meets/exceeds the next sampling time -> process
#             if frame_time + FRAME_SAMPLE_THRESHOLD >= next_sample_time:
#                 # run YOLO (person detection) on this sampled frame
#                 try:
#                     yolo_results = yolo(frame, verbose=False)[0]
#                 except Exception as e:
#                     logging.error(f"YOLO inference error at frame {frame_idx}: {e}")
#                     # advance sampling
#                     next_sample_time += sample_interval
#                     frame_idx += 1
#                     continue

#                 persons = []
#                 # parse results safely (handles tensor shapes differences)
#                 try:
#                     for box in yolo_results.boxes:
#                         cls_tensor = box.cls
#                         cls_val = int(cls_tensor[0]) if hasattr(cls_tensor, "__len__") else int(cls_tensor)
#                         if cls_val != PERSON_CLASS_ID:
#                             continue
#                         coords = box.xyxy[0].cpu().numpy().astype(int)
#                         x1, y1, x2, y2 = coords.tolist()
#                         persons.append((x1, y1, x2, y2))
#                 except Exception:
#                     # fallback extraction
#                     try:
#                         boxes_arr = yolo_results.boxes.xyxy.cpu().numpy().astype(int)
#                         classes = yolo_results.boxes.cls.cpu().numpy().astype(int)
#                         for coords, cls_val in zip(boxes_arr, classes):
#                             if int(cls_val) != PERSON_CLASS_ID:
#                                 continue
#                             x1, y1, x2, y2 = coords.tolist()
#                             persons.append((x1, y1, x2, y2))
#                     except Exception as e:
#                         logging.error(f"Failed to parse YOLO boxes: {e}")
#                         persons = []

#                 # If no person, skip heavy work and just advance sampling time
#                 if not persons:
#                     # advance sampling window and update progress
#                     next_sample_time += sample_interval
#                     pbar.update(1)
#                     frame_idx += 1
#                     continue

#                 # Person(s) detected in this sampled frame -> process each person ROI
#                 annotated = frame.copy()
#                 suspects = []
#                 # For each person, run FR (and later weapon/violence)
#                 for (x1, y1, x2, y2) in persons:
#                     # clamp coordinates
#                     h, w = frame.shape[:2]
#                     x1c = max(0, min(w - 1, int(x1)))
#                     y1c = max(0, min(h - 1, int(y1)))
#                     x2c = max(0, min(w - 1, int(x2)))
#                     y2c = max(0, min(h - 1, int(y2)))
#                     if x2c <= x1c or y2c <= y1c:
#                         continue

#                     roi = frame[y1c:y2c, x1c:x2c]
#                     # Face recognition (may return [] or list of (name,score,box))
#                     try:
#                         fr = recognize_faces(roi, known_embeddings, known_names, threshold=0.45)
#                     except Exception as e:
#                         logging.error(f"Face recognition error: {e}")
#                         fr = []

#                     person_name = "Unknown"
#                     face_conf = 0.0
#                     # if FR returns something, take best match
#                     if fr:
#                         try:
#                             person_name, face_conf, fbox = fr[0]
#                         except Exception:
#                             pass
#                     if person_name == "Unknown" or not person_name:
#                         continue
#                     suspects.append(person_name)

#                     # draw bbox + label
#                     label = f"{person_name} {face_conf:.2f}" if person_name else "Unknown"
#                     cv2.rectangle(annotated, (x1c, y1c), (x2c, y2c), (0, 255, 0), 2)
#                     cv2.putText(annotated, label, (x1c, max(y1c - 8, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)

#                 # Decide whether to upload annotated frame
#                 # Rule: upload if persons detected (you can change to only if recognized)
#                 img_url = upload_annotated_frame(annotated)
#                 print("Image Uploaded -> ", img_url)

#                 # build payload: true timestamp, duration (video length), short summary, suspects
#                 payload = {
#                     "timestamp": format_timestamp(frame_time),
#                     "duration": format_timestamp(duration_seconds),
#                     "imageUrl": img_url or "",
#                     "shortSummary": f"Persons detected: {', '.join(suspects)}",
#                     "weapon": {"detected": False, "weapon_type": "", "confidence": 0.0},
#                     "face": {
#                         # choose first suspect for top-level face meta (you can send list instead)
#                         "person_id": suspects[0] if suspects else "Unknown",
#                         "confidence": float(face_conf) if 'face_conf' in locals() else 0.0,
#                         "image_url": img_url or "",
#                         "location": ""  # optionally add combined bbox or first bbox
#                     },
#                     "anomaly": {"anomaly_type": "", "severity_score": 0, "description": ""}
#                 }

#                 # send to backend (non-blocking behavior isn't implemented; simple post)
#                 send_frame(folder_id, video_id, payload)
#                 samples_sent += 1
#                 pbar.update(1)

#                 # advance next sample time (one step)
#                 next_sample_time += sample_interval

#             frame_idx += 1

#     finally:
#         pbar.close()
#         cap.release()

#     # finalize video
#     complete_payload = {
#         "finalSummary": "Face recognition + person detection completed",
#         "threatLevel": "low",
#         "confidence": 0.9
#     }
#     complete_video(video_id, complete_payload)

#     logging.info(f"[{video_index}/{total_videos}] Video finished: {video_name} | frames read: {frames_read} | samples_sent: {samples_sent}")


# # ---------------------------
# # Process folder
# # ---------------------------
# def process_folder(folder_path):
#     folder_name = os.path.basename(folder_path)
#     logging.info(f"New folder detected: {folder_name}")

#     folder_id = create_folder(folder_name)

#     # collect videos
#     videos = [v for v in sorted(os.listdir(folder_path)) if v.lower().endswith((".mp4", ".avi", ".mov", ".mkv"))]
#     total_videos = len(videos)
#     logging.info(f"Found {total_videos} videos in folder: {folder_name}")

#     for idx, v in enumerate(videos, start=1):
#         video_path = os.path.join(folder_path, v)
#         process_video(video_path, folder_id, video_index=idx, total_videos=total_videos)


# # ---------------------------
# # Watch uploads directory
# # ---------------------------
# def watch_for_dropped_folders():
#     Path(UPLOAD_ROOT).mkdir(parents=True, exist_ok=True)
#     logging.info(f"Watching '{UPLOAD_ROOT}' for new folders. Drop your folder inside to start processing.")

#     processed = set()
#     try:
#         while True:
#             for item in sorted(os.listdir(UPLOAD_ROOT)):
#                 full = os.path.join(UPLOAD_ROOT, item)
#                 if os.path.isdir(full) and item not in processed:
#                     logging.info(f"Detected folder: {item}")
#                     processed.add(item)
#                     # process synchronously (one folder at a time). You can change to thread pool later.
#                     process_folder(full)
#             time.sleep(1)
#     except KeyboardInterrupt:
#         logging.info("Stopping watcher.")


# if __name__ == "__main__":
#     watch_for_dropped_folders()


# pipeline.py

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
