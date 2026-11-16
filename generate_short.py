"""FactShock AI: produce one narrated, captioned vertical science Short.

Requires ANTHROPIC_API_KEY, OPENAI_API_KEY, ffmpeg and ffprobe.
Output: output/short.mp4, output/youtube_metadata.json, output/script.txt,
output/fact_check.json, fact_history.json.
"""
import base64
import json
import os
import random
import re
import subprocess
from pathlib import Path

from anthropic import Anthropic
from openai import OpenAI

OUT = Path('output')
OUT.mkdir(exist_ok=True)
HISTORY = Path('fact_history.json')
FPS = 25
FACTS = [
    {'id':'ingenuity','topic':'First powered flight on Mars','fact':'NASA Ingenuity arrived on Mars with Perseverance on February 18, 2021. On April 19, 2021, it completed the first powered, controlled flight on another planet. The thin Martian atmosphere makes generating lift difficult.','source':'https://science.nasa.gov/mission/mars-2020-perseverance/'},
    {'id':'webb','topic':'How Webb sees the invisible universe','fact':'The James Webb Space Telescope observes mainly infrared light, allowing astronomers to study distant galaxies, stars forming inside dusty clouds, and some exoplanet atmospheres.','source':'https://science.nasa.gov/mission/webb/'},
    {'id':'venus','topic':'A day on Venus outlasts its year','fact':'Venus takes about 243 Earth days to rotate once relative to distant stars, and about 225 Earth days to orbit the Sun. The comparison uses the sidereal rotation period, not its solar day.','source':'https://science.nasa.gov/venus/'},
    {'id':'blackholes','topic':'How we detect black holes','fact':'A black hole has an event horizon from inside which light cannot escape. Astronomers detect black holes through their effects on nearby matter, stellar orbits, and light. Glowing gas and a black hole shadow can be imaged.','source':'https://science.nasa.gov/universe/black-holes/'},
    {'id':'marssunset','topic':'Why Martian sunsets can look blue','fact':'Near the setting Sun on Mars, the sky can appear bluish because fine atmospheric dust scatters sunlight differently than Earth’s atmosphere.','source':'https://science.nasa.gov/mars/'},
    {'id':'iss','topic':'The speed of the International Space Station','fact':'The International Space Station travels at roughly 28,000 kilometers per hour and completes an orbit of Earth about every 90 minutes.','source':'https://www.nasa.gov/international-space-station/'},
    {'id':'exoplanets','topic':'Planets beyond our solar system','fact':'Astronomers have confirmed thousands of exoplanets around other stars. Exoplanets include rocky worlds, gas giants, and planets orbiting binary star systems.','source':'https://science.nasa.gov/exoplanets/'},
    {'id':'neutronstars','topic':'The density of neutron stars','fact':'Neutron stars are extraordinarily dense stellar remnants. A neutron star can pack more mass than the Sun into an object roughly the size of a city.','source':'https://science.nasa.gov/universe/stars/'},
    {'id':'oceandepth','topic':'The deepest known part of the ocean','fact':'Challenger Deep in the Mariana Trench is the deepest known part of the ocean, approximately 11 kilometers below sea level.','source':'https://oceanservice.noaa.gov/facts/oceandepth.html'},
    {'id':'earthwater','topic':'How little of Earth’s water is fresh','fact':'About 97 percent of Earth’s water is saline. Most freshwater is stored in ice or underground, and only a small amount is readily accessible surface water.','source':'https://www.usgs.gov/special-topics/water-science-school'},
]



def run(args):
    subprocess.run(args, check=True)


def duration(path):
    return float(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(path)
    ], text=True).strip())


def json_from_model(value):
    value = re.sub(r'^```(?:json)?\s*', '', value.strip())
    value = re.sub(r'\s*```$', '', value)
    return json.loads(value)


def choose_fact():
    try:
        history = json.loads(HISTORY.read_text(encoding='utf-8')) if HISTORY.exists() else []
        if not isinstance(history, list):
            history = []
    except (OSError, json.JSONDecodeError):
        history = []
    remaining = [fact for fact in FACTS if fact['id'] not in history]
    if not remaining:
        history = []
        remaining = FACTS[:]
    return random.choice(remaining), history


def write_story(client, fact, direction='normal', previous=''):
    directions = {
        'normal': 'Write a fresh script of approximately 85-100 spoken words.',
        'shorter': 'Rewrite the previous script approximately 15 percent shorter.',
        'longer': 'Rewrite the previous script approximately 15 percent longer.'
    }
    instructions = (
        'Create a compelling factual American-English YouTube Short. '
        'Return ONLY a JSON object with keys: script, title, description, hashtags, visual_prompts. '
        'Use one central fact. Begin with a specific, surprising hook in the first sentence. '
        'Avoid generic textbook introductions. Finish with a brief natural question. '
        'Do not invent facts, comparisons, numerical claims, dates or quotations. '
        'Only use the supplied factual notes. No stage directions in the script. '
        'Title under 65 characters. Description two concise sentences. '
        'Hashtags must be an array of 3-5 strings starting with #. '
        'visual_prompts must be exactly five detailed, different, plain STRING prompts '
        'for photorealistic 9:16 documentary-style still images in narrative order. '
        'No lettering, watermarks or logos in images. Avoid misleading visuals.'
    )
    response = client.responses.create(
        model=os.getenv('OPENAI_MODEL', 'gpt-4.1-mini'),
        instructions=instructions,
        input=(f"TOPIC: {fact['topic']}\nFACT NOTES: {fact['fact']}\n"
               f"TASK: {directions[direction]}\nPREVIOUS: {previous}")
    )
    data = json_from_model(response.output_text)
    if not isinstance(data, dict) or not isinstance(data.get('script'), str):
        raise ValueError('Story JSON must include a script string')
    prompts = data.get('visual_prompts')
    if not isinstance(prompts, list) or len(prompts) != 5 or any(
        not isinstance(prompt, str) or not prompt.strip() for prompt in prompts
    ):
        raise ValueError('visual_prompts must be exactly five nonempty strings')
    if not isinstance(data.get('hashtags'), list):
        raise ValueError('hashtags must be a list')
    return data


def make_voice(client, script):
    path = OUT / 'voice.mp3'
    with client.audio.speech.with_streaming_response.create(
        model=os.getenv('TTS_MODEL', 'tts-1'),
        voice='onyx', input=script, speed=1.05
    ) as response:
        response.stream_to_file(path)
    return duration(path)


def ass_timestamp(seconds):
    cs = max(0, round(float(seconds) * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f'{h}:{m:02}:{s:02}.{c:02}'


def write_captions(client):
    with (OUT / 'voice.mp3').open('rb') as audio:
        transcript = client.audio.transcriptions.create(
            model='whisper-1', file=audio, response_format='verbose_json',
            timestamp_granularities=['segment']
