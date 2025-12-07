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


# ============================================================
# CONFIG
# ============================================================
API_BASE = "http://localhost:5000/api"
FOLDER_ID = "PUT_FOLDER_ID_HERE"   # 🔥 you will dynamically set this later

INPUT_FOLDER = "input_videos"
KNOWN_FACES_DIR = "known_faces"


# ============================================================
# CLOUDINARY CONFIG
# ============================================================
cloudinary.config(
    cloud_name="dprwjya79",
    api_key="943616652546731",
    api_secret="khRZlG5lvjBiuvzJZZbmdIyf3OE"
)


# ============================================================
# UTIL: Format timestamp
# ============================================================
def format_time(seconds):
    seconds = int(seconds)
    m = seconds // 60
    s = seconds % 60
    return f"{m:02d}:{s:02d}"


# ============================================================
# BACKEND API CALLS
# ============================================================

def register_video(folder_id, video_name, video_url="", duration=""):
    """POST → /api/videos"""
    payload = {
        "folderId": folder_id,
        "originalName": video_name,
        "videoUrl": video_url,
        "duration": duration
    }

    r = requests.post(f"{API_BASE}/videos", json=payload)
    r.raise_for_status()
    data = r.json()

    print("🎬 Registered video → videoId:", data["_id"])
    return data["_id"]



def send_frame(video_id, folder_id, timestamp, duration, image_url, summary,
               weapon, face, anomaly):
    """POST → /api/frames"""

    payload = {
        "videoId": video_id,
        "folderId": folder_id,
        "timestamp": timestamp,
        "duration": duration,
        "imageUrl": image_url,
        "shortSummary": summary,
        "weapon": weapon,
        "face": face,
        "anomaly": anomaly
    }

    try:
        res = requests.post(f"{API_BASE}/frames", json=payload)
        print("📤 Frame sent →", res.status_code)
    except Exception as e:
        print("❌ Failed sending frame:", e)



def complete_video(video_id, final_summary, threat, confidence, duration):
    """POST → /api/videos/:id/complete"""

    payload = {
        "finalSummary": final_summary,
        "shortSummary": final_summary,
        "threatLevel": threat,
        "confidence": confidence,
        "duration": duration
    }

    r = requests.post(f"{API_BASE}/videos/{video_id}/complete", json=payload)
    print("🏁 Video completed:", r.status_code)



# ============================================================
# LOAD MODELS
# ============================================================
print("Loading YOLOv8n...")
yolo = YOLO("yolov8n.pt")

print("Loading known faces...")
known_embeddings, known_names = load_known_faces(KNOWN_FACES_DIR)
print(f"Loaded {len(known_names)} known persons.")


# ============================================================
# MAIN PROCESSOR
# ============================================================
def process_video(video_path):

    print(f"\n🎥 Processing video: {video_path}\n")
    video_name = os.path.basename(video_path)

    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_interval = int(fps // 3)

    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    video_length_sec = total_frames / fps
    duration_str = format_time(video_length_sec)

    # 🔥 REGISTER VIDEO FIRST
    video_id = register_video(FOLDER_ID, video_name, "", duration_str)

    frame_id = 0
    recognized_once = False
    snapshot_url = None

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        if frame_id % frame_interval != 0:
            frame_id += 1
            continue

        results = yolo(frame)[0]

        for box in results.boxes:
            cls = int(box.cls[0])
            if cls != 0:
                continue

            x1, y1, x2, y2 = map(int, box.xyxy[0])
            roi = frame[y1:y2, x1:x2]

            recog = recognize_faces(
                roi,
                known_embeddings,
                known_names,
                threshold=0.45
            )

            if len(recog) == 0:
                continue

            name, score, _ = recog[0]

            if not recognized_once and name != "Unknown":
                recognized_once = True

                color = (0, 255, 0)
                cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                label = f"{name} ({score:.2f})"
                cv2.putText(frame, label, (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

                success, encoded = cv2.imencode(".jpg", frame)
                uploaded = cloudinary.uploader.upload(encoded.tobytes())
                snapshot_url = uploaded["secure_url"]

                timestamp_sec = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
                timestamp_str = format_time(timestamp_sec)

                summary = generate_incident_summary(
                    snapshot_url=snapshot_url,
                    category="Face Recognition",
                    suspects=[name],
                    cam_id="CAM-01"
                )

                # --------------------------------------------
                # SEND FRAME TO BACKEND
                # --------------------------------------------
                send_frame(
                    video_id=video_id,
                    folder_id=FOLDER_ID,
                    timestamp=timestamp_str,
                    duration=duration_str,
                    image_url=snapshot_url,
                    summary=summary,
                    weapon={
                        "detected": False,
                        "weapon_type": "",
                        "confidence": 0.0
                    },
                    face={
                        "person_id": name,
                        "confidence": float(score),
                        "image_url": snapshot_url,
                        "location": f"{x1},{y1},{x2},{y2}"
                    },
                    anomaly={
                        "anomaly_type": "",
                        "severity_score": 0,
                        "description": ""
                    }
                )

                print("📩 Sent payload for recognition")

        frame_id += 1

    cap.release()

    # ============================================================
    # FINAL VIDEO COMPLETION CALL
    # ============================================================
    complete_video(
        video_id=video_id,
        final_summary="Face recognition completed",
        threat="low",
        confidence=0.95,
        duration=duration_str
    )

    print("\n🎉 DONE: Full pipeline executed!\n")



# ============================================================
# WATCH FOLDER
# ============================================================
def watch_folder():
    print(f"👀 Watching folder: {INPUT_FOLDER}")
    processed = set()

    while True:
        videos = [f for f in os.listdir(INPUT_FOLDER)
                  if f.lower().endswith((".mp4", ".avi", ".mov"))]

        for v in videos:
            path = os.path.join(INPUT_FOLDER, v)
            if path not in processed:
                processed.add(path)
                process_video(path)

        time.sleep(2)



if __name__ == "__main__":
    watch_folder()
