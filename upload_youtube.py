
import os
import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

OUT = Path("output")
VIDEO = OUT / "short.mp4"
METADATA = OUT / "youtube_metadata.json"

if not VIDEO.is_file() or VIDEO.stat().st_size == 0:
    raise FileNotFoundError("Video missing or empty")

if not METADATA.is_file():
    raise FileNotFoundError("YouTube metadata missing")

data = json.loads(METADATA.read_text(encoding="utf-8"))

title = str(data["title"]).strip()[:100]
description = str(data["description"]).strip()[:5000]

if not title or not description:
    raise ValueError("Title or description is empty")

credentials = Credentials(
    token=None,
    refresh_token=os.environ["YOUTUBE_REFRESH_TOKEN"],
    token_uri="https://oauth2.googleapis.com/token",
    client_id=os.environ["YOUTUBE_CLIENT_ID"],
    client_secret=os.environ["YOUTUBE_CLIENT_SECRET"],
    scopes=["https://www.googleapis.com/auth/youtube.upload"],
)

credentials.refresh(Request())

youtube = build(
    "youtube",
    "v3",
    credentials=credentials,
    cache_discovery=False
)

privacy = os.getenv("YOUTUBE_PRIVACY", "private").lower()

if privacy not in ("private", "unlisted", "public"):
    raise ValueError("Invalid privacy setting")

print("Uploading FactShock AI video...", flush=True)

request = youtube.videos().insert(
    part="snippet,status",
    body={
        "snippet": {
            "title": title,
            "description": description,
            "categoryId": "28",
            "defaultLanguage": "en",
            "defaultAudioLanguage": "en-US",
            "tags": [
                "FactShock",
                "Science Facts",
                "Mind Blowing Facts",
                "Artificial Intelligence",
                "Space",
                "Technology",
                "Did You Know",
                "YouTube Shorts"
            ]
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False
        }
    },
    media_body=MediaFileUpload(
        str(VIDEO),
        mimetype="video/mp4",
        resumable=True,
        chunksize=5 * 1024 * 1024
    )
)

response = None

while response is None:
    status, response = request.next_chunk()

    if status:
        print(
            f"Upload progress: {status.progress() * 100:.0f}%",
            flush=True
        )

video_id = response["id"]

print("UPLOAD SUCCESSFUL!", flush=True)
print("Video ID:", video_id, flush=True)
print("Title:", title, flush=True)
print("Privacy:", privacy, flush=True)

(OUT / "uploaded_id.txt").write_text(
    video_id,
    encoding="utf-8"
)
