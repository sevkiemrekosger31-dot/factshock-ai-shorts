
import os
import json
import base64
import re
import subprocess
from pathlib import Path

from anthropic import Anthropic
from openai import OpenAI

OUT = Path("output")
OUT.mkdir(exist_ok=True)

claude = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
openai = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

TEXT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "gpt-image-1-mini")

IMAGE_COUNT = 5
FPS = 25


def run(command):
    subprocess.run(command, check=True)


def duration(path):
    result = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ])
    return float(result.decode().strip())


def clean_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def ass_time(seconds):
    cs = max(0, round(seconds * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02}:{s:02}.{c:02}"


def write_subtitles(segments):
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,64,&H00FFFFFF,&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,5,2,2,95,95,360,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    with open(OUT / "subtitles.ass", "w", encoding="utf-8") as f:
        f.write(header)

        for seg in segments:
            start = float(seg.start)
            end = float(seg.end)
            words = seg.text.strip().split()

            if not words or end <= start:
                continue

            chunks = [
                words[i:i + 5]
                for i in range(0, len(words), 5)
            ]

            pos = start
            total = len(words)

            for chunk in chunks:
                nxt = pos + (end - start) * len(chunk) / total
                txt = " ".join(chunk)
                txt = txt.replace("\\", "").replace("{", "").replace("}", "")

                f.write(
                    f"Dialogue: 0,{ass_time(pos)},"
                    f"{ass_time(nxt)},Default,,0,0,0,,{txt}\n"
                )
                pos = nxt


print("1/8 - Selecting a verified science topic", flush=True)

topic_result = openai.responses.create(
    model=TEXT_MODEL,
    instructions=(
        "You are a science fact-checking researcher. "
        "Choose ONE fascinating, scientifically established fact "
        "suitable for a 35-45 second American YouTube Short. "
        "Topics: AI, NASA, space, robotics, human brain, "
        "science, future technology, real discoveries. "
        "Use conservative, well-established facts. "
        "Never invent statistics, studies or discoveries. "
        "Return ONLY valid JSON with keys: "
        "topic, verified_fact, source_name, source_url. "
        "source_url must be a real authoritative URL you know. "
        "Do not fabricate URLs. "
        "If uncertain, use a well-known official homepage."
    ),
    input=(
        "Select a surprising educational fact for FactShock AI. "
        "Prefer a visually impressive topic."
    )
)

fact = clean_json(topic_result.output_text)

(OUT / "fact_check.json").write_text(
    json.dumps(fact, indent=2, ensure_ascii=False),
    encoding="utf-8"
)

print("Topic:", fact["topic"], flush=True)

print("2/8 - Claude writing American English script", flush=True)

message = claude.messages.create(
    model=CLAUDE_MODEL,
    max_tokens=700,
    messages=[{
        "role": "user",
        "content": (
            "Write an original American English YouTube Shorts "
            "voiceover script for FactShock AI.\n"
            "Target 35-45 seconds, approximately 85-105 words.\n"
            "One surprising scientifically accurate fact.\n"
            "Strong hook in the first 2 seconds.\n"
            "Explain the discovery clearly.\n"
            "Build toward an impressive wow moment.\n"
            "End with one natural question for comments.\n"
            "No stage directions, headings or hashtags.\n"
            "Do not invent facts or exaggerate claims.\n\n"
            f"Verified topic: {fact['topic']}\n"
            f"Verified fact: {fact['verified_fact']}"
        )
    }]
)

source = "".join(
    block.text for block in message.content
    if block.type == "text"
).strip()

print("3/8 - Editing and preparing metadata", flush=True)

edited = openai.responses.create(
    model=TEXT_MODEL,
    instructions=(
        "Return ONLY valid JSON with keys "
        "script, title, description, hashtags. "
        "Edit the supplied science script into natural American English. "
        "Keep it approximately 85-105 words. "
        "Preserve scientific accuracy. "
        "Start with a powerful hook. "
        "End with a thoughtful comment question. "
        "No stage directions in the script. "
        "Title: compelling, accurate, under 65 characters. "
        "Description: 2 short sentences and an invitation to comment. "
        "Hashtags: array of 3-5 relevant hashtags. "
        "No invented discoveries or misleading claims."
    ),
    input=source
)

data = clean_json(edited.output_text)
story = data["script"].strip()

(OUT / "script.txt").write_text(
    story, encoding="utf-8"
)

metadata = {
    "title": data["title"][:95],
    "description": (
        data["description"]
        + "\n\n"
        + " ".join(data["hashtags"])
        + "\n\nSource: "
        + fact["source_name"]
        + " - "
        + fact["source_url"]
    )
}

(OUT / "youtube_metadata.json").write_text(
    json.dumps(metadata, ensure_ascii=False, indent=2),
    encoding="utf-8"
)

print("Script words:", len(story.split()), flush=True)

print("4/8 - Generating American English narration", flush=True)

with openai.audio.speech.with_streaming_response.create(
    model="tts-1",
    voice="onyx",
    input=story,
    speed=1.05
) as response:
    response.stream_to_file(OUT / "voice.mp3")

audio_len = duration(OUT / "voice.mp3")

print("Audio duration:", audio_len, flush=True)

if not 30 <= audio_len <= 45:
    raise ValueError(
        f"Audio duration {audio_len:.1f}s outside 30-45s. "
        "Stopping before image generation to avoid extra costs."
    )

print("5/8 - Creating synchronized subtitles", flush=True)

with open(OUT / "voice.mp3", "rb") as f:
    transcription = openai.audio.transcriptions.create(
        model="whisper-1",
        file=f,
        response_format="verbose_json",
        timestamp_granularities=["segment"]
    )

write_subtitles(transcription.segments)

print("6/8 - Planning cinematic scenes", flush=True)

scene_response = openai.responses.create(
    model=TEXT_MODEL,
    instructions=(
        "Return ONLY a JSON array of exactly 5 strings. "
        "Each string is a detailed English image prompt. "
        "Create 5 sequential, visually distinct scenes "
        "that accurately illustrate the provided science script. "
        "Photorealistic cinematic documentary style, "
        "dramatic lighting, vertical 9:16 composition, "
        "high visual quality, no captions, no logos, "
        "no watermark, no text. "
        "Avoid scientifically misleading visual claims."
    ),
    input=story
)

prompts = clean_json(scene_response.output_text)

if not isinstance(prompts, list) or len(prompts) != IMAGE_COUNT:
    raise ValueError("Expected exactly five image prompts")

print("7/8 - Generating AI visuals", flush=True)

for i, prompt in enumerate(prompts, 1):
    print(f"Image {i}/{IMAGE_COUNT}", flush=True)

    result = openai.images.generate(
        model=IMAGE_MODEL,
        prompt=prompt,
        size="1024x1536",
        quality="medium",
        n=1
    )

    image_data = result.data[0].b64_json

    if not image_data:
        raise RuntimeError(f"Image {i} returned no data")

    (OUT / f"scene_{i:02}.png").write_bytes(
        base64.b64decode(image_data)
    )

print("8/8 - Rendering vertical Shorts video", flush=True)

scene_len = audio_len / IMAGE_COUNT

for i in range(1, IMAGE_COUNT + 1):
    image_path = OUT / f"scene_{i:02}.png"
    clip_path = OUT / f"clip_{i:02}.mp4"

    vf = (
        "scale=1080:1920:"
        "force_original_aspect_ratio=increase,"
        "crop=1080:1920,"
        "setsar=1,"
        f"fps={FPS},"
        f"trim=duration={scene_len:.4f},"
        "setpts=PTS-STARTPTS"
    )

    run([
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-y",
        "-loop", "1",
        "-framerate", str(FPS),
        "-i", str(image_path),
        "-vf", vf,
        "-t", str(scene_len),
        "-an",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "24",
        "-pix_fmt", "yuv420p",
        str(clip_path)
    ])

with open(OUT / "clips.txt", "w") as f:
    for i in range(1, IMAGE_COUNT + 1):
        f.write(f"file 'clip_{i:02}.mp4'\n")

run([
    "ffmpeg", "-hide_banner", "-loglevel", "error",
    "-y",
    "-f", "concat",
    "-safe", "0",
    "-i", str(OUT / "clips.txt"),
    "-c", "copy",
    str(OUT / "joined.mp4")
])

run([
    "ffmpeg", "-hide_banner", "-loglevel", "error",
    "-y",
    "-i", str(OUT / "joined.mp4"),
    "-i", str(OUT / "voice.mp3"),
    "-vf", "ass=output/subtitles.ass",
    "-map", "0:v:0",
    "-map", "1:a:0",
    "-c:v", "libx264",
    "-preset", "veryfast",
    "-crf", "24",
    "-pix_fmt", "yuv420p",
    "-c:a", "aac",
    "-b:a", "160k",
    "-t", str(audio_len),
    "-movflags", "+faststart",
    str(OUT / "short.mp4")
])

print("FACTSHOCK VIDEO READY", flush=True)
print("File: output/short.mp4", flush=True)
print(f"Duration: {audio_len:.1f}s", flush=True)
print("Resolution: 1080x1920", flush=True)
