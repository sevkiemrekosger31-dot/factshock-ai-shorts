"""FactShock AI Shorts generator. Run: python generate_short.py"""
import base64
import json
import os
import random
import re
import subprocess
from pathlib import Path

from openai import OpenAI

OUT = Path('output')
OUT.mkdir(exist_ok=True)
HISTORY = Path('fact_history.json')
CLIENT = OpenAI(api_key=os.environ['OPENAI_API_KEY'])
MODEL = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
IMAGE_MODEL = os.getenv('IMAGE_MODEL', 'gpt-image-1-mini')
FPS = 25

# Carefully constrained starting facts. A cited URL is not automatic fact verification.
FACTS = [
    {'id':'ingenuity','topic':'First powered flight on Mars','fact':'NASA Ingenuity landed on Mars with Perseverance on February 18, 2021. On April 19, 2021 it completed the first powered, controlled flight on another planet. The thin atmosphere makes lift difficult.','source':'https://science.nasa.gov/mission/mars-2020-perseverance/'},
    {'id':'webb','topic':'Webb and infrared light','fact':'The James Webb Space Telescope observes primarily infrared light, helping astronomers study distant galaxies, stars forming in dusty clouds and some exoplanet atmospheres.','source':'https://science.nasa.gov/mission/webb/'},
    {'id':'venus','topic':'A rotation on Venus lasts longer than a year','fact':'Venus rotates once relative to distant stars in about 243 Earth days, but orbits the Sun in about 225 Earth days. This compares sidereal rotation, not the solar day.','source':'https://science.nasa.gov/venus/'},
    {'id':'blackholes','topic':'How black holes are detected','fact':'Light cannot escape from within a black hole event horizon. Astronomers infer black holes through effects on nearby matter and light. Glowing gas around black holes and their shadows can be imaged.','source':'https://science.nasa.gov/universe/black-holes/'},
    {'id':'marssunset','topic':'Blue sunsets on Mars','fact':'Near the setting Sun on Mars, the sky can look bluish because fine atmospheric dust scatters sunlight differently from Earth.','source':'https://science.nasa.gov/mars/'},
    {'id':'iss','topic':'International Space Station speed','fact':'The International Space Station travels about 28,000 kilometers per hour and circles Earth approximately every 90 minutes.','source':'https://www.nasa.gov/international-space-station/'},
    {'id':'exoplanets','topic':'Worlds around other stars','fact':'Astronomers have confirmed thousands of exoplanets. They include rocky planets, gas giants and planets orbiting binary stars.','source':'https://science.nasa.gov/exoplanets/'},
    {'id':'neutronstars','topic':'Dense neutron stars','fact':'Neutron stars are extremely dense stellar remnants. Some contain more mass than the Sun in an object roughly the size of a city.','source':'https://science.nasa.gov/universe/stars/'},
    {'id':'oceandepth','topic':'The deepest ocean location','fact':'Challenger Deep in the Mariana Trench is the deepest known part of the ocean, approximately 11 kilometers below sea level.','source':'https://oceanservice.noaa.gov/facts/oceandepth.html'},
    {'id':'earthwater','topic':'How little water is fresh','fact':'About 97 percent of Earth water is saline. Much of the remaining freshwater is stored as ice or underground.','source':'https://www.usgs.gov/special-topics/water-science-school'},
]


def command(args):
    subprocess.run(args, check=True)


def seconds(path):
    return float(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(path)
    ], text=True).strip())


def parse_json(value):
    value = re.sub(r'^```(?:json)?\s*|\s*```$', '', value.strip())
    return json.loads(value)


def choose_fact():
    try:
        history = json.loads(HISTORY.read_text(encoding='utf-8')) if HISTORY.exists() else []
        if not isinstance(history, list):
            history = []
    except (OSError, ValueError):
        history = []
    unused = [fact for fact in FACTS if fact['id'] not in history]
    if not unused:
        history, unused = [], FACTS[:]
    return random.choice(unused), history


def create_story(fact, adjustment='', old_script=''):
    prompt = (
        'Return ONLY a valid JSON object with keys: script, title, description, hashtags, visual_prompts. '
        'Write a compelling American-English YouTube Short with one main fact. '
        'The first sentence must be a strong curiosity hook, not a generic introduction. '
        'Use 80 to 105 spoken words, simple natural sentences, an exciting reveal, '
        'and one short comment-provoking question at the end. '
        'Do not invent ANY factual detail, numerical comparison, date, quote or scientific claim '
        'beyond the FACT NOTES below. No sensationalized falsehoods. '
        'Title: accurate, under 65 characters. Description: two short sentences. '
        'Hashtags: array of 3 to 5 strings beginning with #. '
        'visual_prompts: array of exactly five DIFFERENT cinematic photorealistic image descriptions '
        'in story order, vertical 9:16, no words, logos or watermarks. '
        'All five visual_prompts MUST be plain strings, not objects. '
        f'FACT TOPIC: {fact["topic"]}\nFACT NOTES: {fact["fact"]}\n'
        f'REVISION REQUEST: {adjustment}\nPREVIOUS SCRIPT: {old_script}'
    )
    result = CLIENT.responses.create(model=MODEL, input=prompt)
    data = parse_json(result.output_text)
    if not isinstance(data, dict):
        raise ValueError('Story response is not an object')
    for key in ('script', 'title', 'description'):
        if not isinstance(data.get(key), str) or not data[key].strip():
            raise ValueError(f'Missing text field: {key}')
    prompts = data.get('visual_prompts')
    if not isinstance(prompts, list) or len(prompts) != 5:
        raise ValueError('Expected five image prompts')
    normalized = []
    for prompt_item in prompts:
        if isinstance(prompt_item, dict):
            prompt_item = prompt_item.get('prompt') or prompt_item.get('description')
        if not isinstance(prompt_item, str) or not prompt_item.strip():
            raise ValueError('Image prompt must be text')
        normalized.append(prompt_item.strip())
    data['visual_prompts'] = normalized
    if not isinstance(data.get('hashtags'), list):
        data['hashtags'] = ['#Science', '#Facts', '#Shorts']
    return data


def make_voice(script):
    path = OUT / 'voice.mp3'
    with CLIENT.audio.speech.with_streaming_response.create(
        model=os.getenv('TTS_MODEL', 'tts-1'),
        voice='onyx', input=script, speed=1.05
    ) as response:
        response.stream_to_file(path)
    return seconds(path)


def ass_time(value):
    ticks = max(0, round(float(value) * 100))
    hours, remainder = divmod(ticks, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, centis = divmod(remainder, 100)
    return f'{hours}:{minutes:02}:{secs:02}.{centis:02}'


def captions():
    with (OUT / 'voice.mp3').open('rb') as audio:
        transcript = CLIENT.audio.transcriptions.create(
            model='whisper-1', file=audio,
            response_format='verbose_json',
            timestamp_granularities=['segment']
        )
    segments = getattr(transcript, 'segments', None) or []
    if not segments:
        raise ValueError('Transcription returned no timed segments')
    header = '''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,64,&H00FFFFFF,&H000000FF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,5,2,2,95,95,360,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    with (OUT / 'subtitles.ass').open('w', encoding='utf-8') as output:
        output.write(header)
        for segment in segments:
            if isinstance(segment, dict):
                start, end, content = segment['start'], segment['end'], segment['text']
            else:
                start, end, content = segment.start, segment.end, segment.text
            words = str(content).strip().split()
            if not words or float(end) <= float(start):
                continue
            pos = float(start)
            for index in range(0, len(words), 5):
                chunk = words[index:index + 5]
                finish = pos + (float(end) - float(start)) * len(chunk) / len(words)
                safe = ' '.join(chunk).replace('\\', '').replace('{', '').replace('}', '')
                output.write(f'Dialogue: 0,{ass_time(pos)},{ass_time(finish)},Default,,0,0,0,,{safe}\n')
                pos = finish


def images(prompts):
    for index, prompt in enumerate(prompts, start=1):
        print(f'Generating image {index}/5', flush=True)
        result = CLIENT.images.generate(
            model=IMAGE_MODEL, prompt=str(prompt),
            size='1024x1536', quality='medium', n=1
        )
        encoded = result.data[0].b64_json
        if not encoded:
            raise ValueError('Image API did not return base64 data')
        (OUT / f'scene_{index:02}.png').write_bytes(base64.b64decode(encoded))


def render(audio_duration):
    clip_length = audio_duration / 5
    for index in range(1, 6):
        command([
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-loop', '1', '-framerate', str(FPS),
            '-i', str(OUT / f'scene_{index:02}.png'),
            '-vf', 'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=25',
            '-t', str(clip_length), '-an', '-c:v', 'libx264',
            '-preset', 'veryfast', '-crf', '25', '-pix_fmt', 'yuv420p',
            str(OUT / f'clip_{index:02}.mp4')
        ])
    with (OUT / 'clips.txt').open('w', encoding='utf-8') as listing:
        for index in range(1, 6):
            listing.write(f"file 'clip_{index:02}.mp4'\n")
    command([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
        '-f', 'concat', '-safe', '0', '-i', str(OUT / 'clips.txt'),
        '-c', 'copy', str(OUT / 'joined.mp4')
    ])
    command([
        'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
        '-i', str(OUT / 'joined.mp4'), '-i', str(OUT / 'voice.mp3'),
        '-vf', 'ass=output/subtitles.ass', '-map', '0:v:0', '-map', '1:a:0',
        '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '25',
        '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k',
        '-t', str(audio_duration), '-movflags', '+faststart',
        str(OUT / 'short.mp4')
    ])


def main():
    fact, history = choose_fact()
    print('Selected topic:', fact['topic'], flush=True)
    story = create_story(fact)
    for attempt in range(4):
        audio_duration = make_voice(story['script'])
        print(f'Voice duration: {audio_duration:.1f}s', flush=True)
        if 30 <= audio_duration <= 45:
            break
        if attempt == 3:
            raise ValueError('Could not obtain 30-45 second voiceover')
        adjustment = 'Make narration shorter by 15%.' if audio_duration > 45 else 'Make narration longer by 15%.'
        story = create_story(fact, adjustment, story['script'])
    (OUT / 'script.txt').write_text(story['script'], encoding='utf-8')
    (OUT / 'fact_check.json').write_text(json.dumps(fact, indent=2, ensure_ascii=False), encoding='utf-8')
    hashtags = ' '.join(str(tag) for tag in story['hashtags'][:5])
    metadata = {
        'title': story['title'][:95],
        'description': f"{story['description']}\n\n{hashtags}\n\nSource: {fact['source']}"
    }
    (OUT / 'youtube_metadata.json').write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding='utf-8')
    captions()
    images(story['visual_prompts'])
    render(audio_duration)
    if not (OUT / 'short.mp4').is_file() or (OUT / 'short.mp4').stat().st_size == 0:
        raise RuntimeError('Video missing after rendering')
    history.append(fact['id'])
    HISTORY.write_text(json.dumps(history, indent=2), encoding='utf-8')
    print('FACTSHOCK AI VIDEO READY', flush=True)


if __name__ == '__main__':
    main()
