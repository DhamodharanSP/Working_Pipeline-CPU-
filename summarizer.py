from typing import Iterable
import requests
from google import genai
from google.genai import types

from dotenv import load_dotenv
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=GEMINI_API_KEY)


def generate_incident_summary(
    snapshot_url: str,
    category: str,
    suspects: Iterable[str],
    cam_id: str,
) -> str:
    """
    Use Gemini to generate a short, incident-style summary
    based on the snapshot image + metadata.

    Returns a SINGLE sentence summary.
    Falls back to a simple summary if anything fails.
    """
    suspects_list = list(suspects)
    suspects_str = ", ".join(suspects_list) if suspects_list else "Unknown person"

    base_prompt = (
        "Analyze the surveillance image and generate EXACTLY one security-oriented point.\n"
        "Focus on behavior, posture, suspicious objects, risk indicators, and scene context.\n"
        "All observations must come strictly from visible content—no assumptions.\n\n"
        f"Camera ID: {cam_id}\nCategory: {category}\nSuspects: {suspects_str}\n\n"
        "Keep the total summary under 10 words"
    )       

    try:
        # 1) Download the snapshot image from Cloudinary
        resp = requests.get(snapshot_url, timeout=5)
        resp.raise_for_status()
        image_bytes = resp.content

        # 2) Build multimodal contents: [text_prompt, image_part]
        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type="image/jpeg",  # Cloudinary snapshot is JPEG
        )

        response = client.models.generate_content(
            model="gemini-2.5-flash",  # or "gemini-2.5-flash" if enabled on your key
            contents=[base_prompt, image_part],
        )

        text = (response.text or "").strip()
        if not text:
            raise ValueError("Empty Gemini response")

        return text

    except Exception as e:
        print(f"⚠️ Gemini summary failed: {e}")
        # Fallback summary if Gemini fails
        return f"{category} event. Suspects: {suspects_str}"
