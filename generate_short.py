
import os
import json
import base64
import random
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

FPS = 25
IMAGE_COUNT = 5

FACTS = [
    {
        "id": "mars_helicopter",
        "topic": "The first powered flight on Mars",
        "fact": (
            "NASA's Ingenuity helicopter arrived on Mars with "
            "the Perseverance rover on February 18, 2021. "
            "On April 19, 2021, Ingenuity performed the first "
            "powered, controlled flight on another planet. "
            "Mars has a very thin atmosphere, making flight difficult."
        ),
        "source": "NASA",
        "url": "https://science.nasa.gov/mission/mars-2020-perseverance/"
    },
    {
        "id": "james_webb",
        "topic": "The James Webb Space Telescope",
        "fact": (
            "NASA's James Webb Space Telescope observes the "
            "universe primarily in infrared light. "
            "It can study distant galaxies, star formation, "
            "and the atmospheres of some exoplanets."
        ),
        "source": "NASA",
        "url": "https://science.nasa.gov/mission/webb/"
    },
    {
        "id": "venus_day",
        "topic": "A day on Venus is longer than its year",
        "fact": (
            "Venus takes approximately 243 Earth days to rotate "
            "once relative to the stars, but approximately "
            "225 Earth days to orbit the Sun. "
            "This compares its sidereal rotation period "
            "with its orbital period."
        ),
        "source": "NASA",
        "url": "https://science.nasa.gov/venus/"
    },
    {
        "id": "neutron_star",
        "topic": "The incredible density of neutron stars",
        "fact": (
            "Neutron stars are extremely dense remnants "
            "of massive stars. A neutron star can contain "
            "more mass than the Sun within a sphere "
            "roughly the size of a city."
        ),
        "source": "NASA",
        "url": "https://science.nasa.gov/universe/stars/"
    },
    {
        "id": "black_holes",
        "topic": "Why black holes are invisible",
        "fact": (
            "A black hole has an event horizon beyond which "
            "light cannot escape. Astronomers can detect "
            "black holes through their effects on nearby "
            "matter and light."
        ),
        "source": "NASA",
        "url": "https://science.nasa.gov/universe/black-holes/"
    },
    {
        "id": "mars_sunset",
        "topic": "Why sunsets on Mars can look blue",
        "fact": (
            "Near the Sun, Martian sunsets can appear bluish "
            "because fine dust in the atmosphere scatters "
            "sunlight differently than Earth's atmosphere."
        ),
        "source": "NASA",
        "url": "https://science.nasa.gov/mars/"
    },
    {
        "id": "earth_water",
        "topic": "How much of Earth's water is freshwater",
        "fact": (
            "About 97 percent of Earth's water is saline. "
            "Only a small fraction is freshwater, and much "
            "of that freshwater is stored in ice or underground."
        ),
        "source": "USGS",
        "url": "https://www.usgs.gov/special-topics/water-science-school"
    },
    {
        "id": "ocean_depth",
        "topic": "The deepest part of the ocean",
        "fact": (
            "Challenger Deep in the Mariana Trench is "
            "the deepest known part of Earth's ocean. "
            "It is approximately 11 kilometers below sea level."
        ),
        "source": "NOAA",
        "url": "https://oceanservice.noaa.gov/facts/oceandepth.html"
    },
    {
        "id": "exoplanets",
        "topic": "Planets beyond our solar system",
        "fact": (
            "Astronomers have confirmed thousands of "
            "exoplanets orbiting stars beyond our Sun. "
            "Some are rocky, some are gas giants, and "
            "some orbit multiple stars."
        ),
        "source": "NASA",
        "url": "https://science.nasa.gov/exoplanets/"
    },
    {
        "id": "space_station",
        "topic": "How fast the International Space Station travels",
        "fact": (
            "The International Space Station travels "
            "at approximately 28,000 kilometers per hour "
            "and completes an orbit around Earth "
            "roughly every 90 minutes."
        ),
        "source": "NASA",
        "url": "https://www.nasa.gov/international-space-station/"
    }
]


def run(command):
    subprocess.run(command, check=True)


def get_duration(path):
    result = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ])
    return float(result.decode().strip())


def parse_json(text):
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


def choose_fact():
    history_file = Path("fact_history.json")

    if history_file.exists():
        history = json.loads(
            history_file.read_text(encoding="utf-8")
        )
    else:
        history = []

    unused = [
        fact for fact in FACTS
        if fact["id"] not in history
    ]

    if not unused:
        history = []
        unused = FACTS.copy()

    selected = random.choice(unused)

    return selected, history


def generate_script(fact):
    message = claude.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=600,
        messages=[{
            "role": "user",
            "content": (
                "You are a professional American science "
                "documentary Shorts writer.\n"
                "Write a 30-45 second English voiceover.\n"
                "Target approximately 85-100 words.\n"
                "Use ONLY the factual information supplied.\n"
                "Do not add unsupported statistics, dates, "
                "comparisons or discoveries.\n"
                "Make the opening 2 seconds irresistible.\n"
                "Use natural American English.\n"
                "One central discovery per video.\n"
                "Explain why the fact is surprising.\n"
                "Finish with one short question "
                "that encourages comments.\n"
                "No headings or stage directions.\n\n"
                f"TOPIC: {fact['topic']}\n"
                f"VERIFIED INFORMATION: {fact['fact']}"
            )
        }]
    )

    return "".join(
        block.text for block in message.content
        if block.type == "text"
    ).strip()


def edit_script(script, fact):
    response = openai.responses.create(
        model=TEXT_MODEL,
        instructions=(
            "Return ONLY valid JSON with keys "
            "script, title, description, hashtags. "
            "Use natural American English. "
            "Keep the script between 80 and 105 words. "
            "Use ONLY facts supplied in the verified source notes. "
            "Do not invent statistics, dates, events or comparisons. "
            "Preserve scientific accuracy. "
            "Create a strong opening hook. "
            "End with a short comment question. "
            "Title must be accurate and under 65 characters. "
            "Description must be 2 short sentences. "
            "Hashtags must be an array of 3-5 relevant hashtags."
        ),
        input=(
            f"VERIFIED NOTES:\n{fact['fact']}\n\n"
            f"DRAFT:\n{script}"
        )
    )

    return parse_json(response.output_text)


def create_voice(script):
    with openai.audio.speech.with_streaming_response.create(
        model="tts-1",
        voice="onyx",
        input=script,
        speed=1.05
    ) as response:
        response.stream_to_file(OUT / "voice.mp3")

    return get_duration(OUT / "voice.mp3")


def generate_images(script):
    response = openai.responses.create(
        model=TEXT_MODEL,
        instructions=(
            "Return ONLY a JSON array containing exactly "
            "five detailed cinematic image prompts. "
            "Each prompt should illustrate a different "
            "moment in the supplied documentary narration. "
            "Vertical 9:16 composition. "
            "Photorealistic, high-quality documentary visuals. "
            "Strong lighting and depth. "
            "No text, logos, subtitles or watermarks. "
            "Avoid scientifically misleading imagery."
        ),
        input=script
    )

    prompts = parse_json(response.output_text)

    if not isinstance(prompts, list) or len(prompts) != IMAGE_COUNT:
        raise ValueError("Expected exactly five prompts")

    for i, prompt in enumerate(prompts, 1):
        print(f"Generating image {i}/{IMAGE_COUNT}", flush=True)

        result = openai.images.generate(
            model=IMAGE_MODEL,
            prompt=str(prompt) if isinstance(prompt, str) else json.dumps(prompt, ensure_ascii=False),
            size="1024x1536",
            quality="medium",
            n=1
        )

        image_data = result.data[0].b64_json

        if not image_data:
            raise RuntimeError("Image generation failed")

        (OUT / f"scene_{i:02}.png").write_bytes(
            base64.b64decode(image_data)
        )


def render_video(audio_len):
    scene_len = audio_len / IMAGE_COUNT

    for i in range(1, IMAGE_COUNT + 1):
        image_path = OUT / f"scene_{i:02}.png"
        clip_path = OUT / f"clip_{i:02}.mp4"

        vf = (
            "scale=1080:1920:"
            "force_original_aspect_ratio=increase,"
            "crop=1080:1920,"
            "setsar=1,"
            f"fps={FPS}"
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


def main():
    print("FACTSHOCK AI STARTED", flush=True)

    fact, history = choose_fact()

    print("Selected topic:", fact["topic"], flush=True)

    (OUT / "fact_check.json").write_text(
        json.dumps(fact, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    draft = generate_script(fact)

    data = edit_script(draft, fact)

    script = data["script"].strip()

    if not script:
        raise ValueError("Empty script")

    (OUT / "script.txt").write_text(
        script, encoding="utf-8"
    )

    metadata = {
        "title": str(data["title"])[:95],
        "description": (
            str(data["description"])
            + "\n\n"
            + " ".join(data["hashtags"])
            + "\n\nSource: "
            + fact["source"]
            + " - "
            + fact["url"]
        )
    }

    (OUT / "youtube_metadata.json").write_text(
        json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    audio_len = None

    for attempt in range(3):
        audio_len = create_voice(script)

        if 30 <= audio_len <= 45:
            break

        print(
            f"Duration {audio_len:.1f}s, retrying script...",
            flush=True
        )

        if audio_len > 45:
            instruction = "Shorten this script by about 15 percent."
        else:
            instruction = "Expand this script by about 10 percent."

        response = openai.responses.create(
            model=TEXT_MODEL,
            instructions=(
                "Return only the revised voiceover script. "
                "Keep every factual claim within the "
                "provided verified notes. "
                "Use natural American English. "
                "No headings or stage directions."
            ),
            input=(
                f"{instruction}\n\n"
                f"VERIFIED NOTES:\n{fact['fact']}\n\n"
                f"SCRIPT:\n{script}"
            )
        )

        script = response.output_text.strip()

        (OUT / "script.txt").write_text(
            script, encoding="utf-8"
        )

    if not 30 <= audio_len <= 45:
        raise ValueError("Could not achieve 30-45s narration")

    print("Audio duration:", audio_len, flush=True)

    with open(OUT / "voice.mp3", "rb") as f:
        transcription = openai.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["segment"]
        )

    write_subtitles(transcription.segments)

    generate_images(script)

    render_video(audio_len)

    history.append(fact["id"])

    Path("fact_history.json").write_text(
        json.dumps(history, indent=2),
        encoding="utf-8"
    )

    print("FACTSHOCK VIDEO READY", flush=True)
    print("File: output/short.mp4", flush=True)
    print("Duration:", round(audio_len, 1), flush=True)


if __name__ == "__main__":
    main()
