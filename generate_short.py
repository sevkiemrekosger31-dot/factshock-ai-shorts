import base64
import json
import math
import os
import random
import re
import subprocess
import textwrap
import shutil
import time
from pathlib import Path

from openai import OpenAI

OUT = Path('output')
OUT.mkdir(exist_ok=True)
HISTORY = Path('fact_history.json')
CLIENT = OpenAI(api_key=os.environ['OPENAI_API_KEY'], timeout=180, max_retries=2)
MODEL = os.getenv('OPENAI_MODEL', 'gpt-4.1-mini')
IMAGE_MODEL = os.getenv('IMAGE_MODEL', 'gpt-image-1-mini')
TTS_MODEL = os.getenv('TTS_MODEL', 'gpt-4o-mini-tts')
VOICE = os.getenv('TTS_VOICE', 'onyx')
FPS = 25
SCENES = 6  # Six paid images, twelve shorter visual cuts

# Each fact is deliberately bounded to a verifiable statement; the model must not add unsupported claims.
FACTS = [
 {'id':'ny-name','topic':'Why New York has its name','fact':'The Dutch colonial settlement was called New Amsterdam. After the English took control in 1664, it was renamed New York in honor of the Duke of York.','source':'https://www.nyc.gov/site/records/about/history.page','category':'america'},
 {'id':'liberty-green','topic':'Why the Statue of Liberty is green','fact':'The Statue of Liberty has a copper exterior. Weathering over time created a green patina; the statue was originally copper colored.','source':'https://www.nps.gov/stli/learn/historyculture/index.htm','category':'america'},
 {'id':'yellowstone-colors','topic':'Yellowstone hot spring colors','fact':'The bright colors around many Yellowstone hot springs come from heat-loving microorganisms; different temperatures favor different communities.','source':'https://www.nps.gov/yell/learn/nature/hot-springs.htm','category':'america'},
 {'id':'las-vegas-name','topic':'The meaning of Las Vegas','fact':'Las Vegas is Spanish for the meadows. The name refers to the oasis and grassy areas found by travelers in the desert valley.','source':'https://www.britannica.com/place/Las-Vegas-Nevada','category':'america'},
 {'id':'schoolbus-yellow','topic':'Why American school buses are yellow','fact':'In 1939, a US conference on school transportation established a standardized yellow-orange color for school buses. Visibility was an important reason.','source':'https://americanhistory.si.edu/collections/object/nmah_1192256','category':'america'},
 {'id':'octopus-hearts','topic':'Three hearts of an octopus','fact':'Octopuses have three hearts: two pump blood to the gills and one pumps it to the rest of the body. Their blood uses copper-containing hemocyanin, which makes it blue.','source':'https://www.smithsonianmag.com/smart-news/why-do-octopuses-have-three-hearts-180981113/','category':'nature'},
 {'id':'dolphin-sleep','topic':'How dolphins sleep','fact':'Dolphins can rest one hemisphere of the brain at a time, helping them keep breathing and remain aware of their surroundings.','source':'https://oceanservice.noaa.gov/facts/dolphin_sleep.html','category':'nature'},
 {'id':'deep-ocean','topic':'The deepest known ocean location','fact':'Challenger Deep in the Mariana Trench is the deepest known part of the ocean, about 11 kilometers below sea level.','source':'https://oceanservice.noaa.gov/facts/oceandepth.html','category':'nature'},
 {'id':'ocean-glow','topic':'Why ocean water can glow','fact':'Some marine organisms produce light through bioluminescence. In certain conditions, blooms of microscopic plankton can make disturbed seawater glow at night.','source':'https://oceanservice.noaa.gov/facts/biolum.html','category':'nature'},
 {'id':'venus-day','topic':'Venus rotation and year','fact':'Venus takes about 243 Earth days to rotate once relative to the stars, while it takes about 225 Earth days to orbit the Sun. These figures describe sidereal rotation and orbital period.','source':'https://science.nasa.gov/venus/','category':'world'},
 {'id':'mars-blue','topic':'Blue sunsets on Mars','fact':'Near the setting Sun on Mars, fine atmospheric dust can make the sky appear bluish.','source':'https://science.nasa.gov/mars/','category':'world'},
 {'id':'iss-speed','topic':'Speed of the International Space Station','fact':'The International Space Station travels at roughly 28,000 kilometers per hour and orbits Earth approximately every 90 minutes.','source':'https://www.nasa.gov/international-space-station/','category':'world'},
 {'id':'earth-water','topic':'How much Earth water is salty','fact':'About 97 percent of Earth water is saline. Much of the freshwater is frozen or stored underground.','source':'https://www.usgs.gov/special-topics/water-science-school','category':'nature'},
 {'id':'webb-infrared','topic':'Why Webb observes infrared','fact':'The James Webb Space Telescope primarily observes infrared light to study distant galaxies, star formation in dusty regions and some exoplanet atmospheres.','source':'https://science.nasa.gov/mission/webb/','category':'world'},
 {'id':'grand-canyon','topic':'Grand Canyon formation','fact':'The Colorado River and erosion helped carve the Grand Canyon over millions of years.','source':'https://www.nps.gov/grca/learn/nature/geologicformations.htm','category':'america'},
 {'id':'death-valley','topic':'Death Valley extreme heat','fact':'Death Valley is known for extreme summer heat and includes Badwater Basin, the lowest point in North America.','source':'https://www.nps.gov/deva/learn/nature/index.htm','category':'america'},
 {'id':'sequoia','topic':'Giant sequoia trees','fact':'Giant sequoias are among the largest trees by volume, and some live for thousands of years.','source':'https://www.nps.gov/seki/learn/nature/giant-sequoias.htm','category':'america'},
 {'id':'old-faithful','topic':'Yellowstone geysers','fact':'Old Faithful erupts repeatedly because underground water is heated and pressurized in a natural plumbing system.','source':'https://www.nps.gov/yell/learn/nature/geysers.htm','category':'america'},
 {'id':'niagara','topic':'Niagara Falls geography','fact':'Niagara Falls consists of three waterfalls on the border of the United States and Canada.','source':'https://www.nps.gov/niag/index.htm','category':'america'},
 {'id':'moon-tides','topic':'Why ocean tides happen','fact':'The Moon’s gravity is the main driver of ocean tides, with the Sun also contributing.','source':'https://oceanservice.noaa.gov/education/tutorial_tides/','category':'nature'},
 {'id':'coral-animal','topic':'Corals are animals','fact':'Corals are animals made of tiny polyps, and many reef-building corals live with photosynthetic algae.','source':'https://oceanservice.noaa.gov/facts/coral.html','category':'nature'},
 {'id':'ocean-salt','topic':'Why the ocean is salty','fact':'Ocean salt comes largely from minerals carried by rivers and from geological processes on the seafloor.','source':'https://oceanservice.noaa.gov/facts/whysalty.html','category':'nature'},
 {'id':'ocean-currents','topic':'Ocean currents move heat','fact':'Ocean currents move water and redistribute heat around Earth.','source':'https://oceanservice.noaa.gov/education/tutorial_currents/','category':'nature'},
 {'id':'whale-mammal','topic':'Whales breathe air','fact':'Whales are mammals: they breathe air through lungs and nurse their young with milk.','source':'https://www.fisheries.noaa.gov/whales','category':'nature'},
 {'id':'shark-cartilage','topic':'Sharks have cartilage skeletons','fact':'Sharks have skeletons made primarily of cartilage rather than bone.','source':'https://oceanservice.noaa.gov/facts/shark.html','category':'nature'},
 {'id':'mantis-shrimp','topic':'Mantis shrimp punch','fact':'Some mantis shrimp use extremely fast club-like strikes to break the shells of prey.','source':'https://ocean.si.edu/ocean-life/invertebrates/mantis-shrimp','category':'nature'},
 {'id':'aurora','topic':'What causes northern lights','fact':'Auroras occur when energetic charged particles interact with gases in Earth’s upper atmosphere.','source':'https://www.swpc.noaa.gov/phenomena/aurora','category':'world'},
 {'id':'lightning','topic':'How lightning forms','fact':'Lightning is a powerful electrical discharge caused by charge separation in storms.','source':'https://www.weather.gov/safety/lightning-science-overview','category':'nature'},
 {'id':'rainbow','topic':'Why rainbows form','fact':'Rainbows form when sunlight is refracted, reflected and dispersed by water droplets.','source':'https://www.weather.gov/jetstream/rainbows','category':'nature'},
 {'id':'snowflakes','topic':'Snowflakes and temperature','fact':'Snow crystal shapes depend on temperature and humidity as they grow in clouds.','source':'https://www.noaa.gov/jetstream/clouds/snowflakes','category':'nature'},
 {'id':'moon-footprints','topic':'Footprints on the Moon','fact':'Without weather like Earth’s wind and rain, footprints on the Moon can remain for a very long time.','source':'https://science.nasa.gov/moon/','category':'world'},
 {'id':'moon-far-side','topic':'Far side of the Moon','fact':'The Moon rotates once per orbit, so nearly the same hemisphere faces Earth. The far side is not permanently dark.','source':'https://science.nasa.gov/moon/','category':'world'},
 {'id':'mars-olympus','topic':'Olympus Mons on Mars','fact':'Olympus Mons on Mars is the largest known volcano in the solar system.','source':'https://science.nasa.gov/mars/','category':'world'},
 {'id':'jupiter-storm','topic':'Jupiter Great Red Spot','fact':'Jupiter’s Great Red Spot is a giant long-lived storm in its atmosphere.','source':'https://science.nasa.gov/jupiter/','category':'world'},
 {'id':'saturn-rings','topic':'Saturn rings material','fact':'Saturn’s rings are made mostly of countless pieces of ice, with some rock and dust.','source':'https://science.nasa.gov/saturn/','category':'world'},
 {'id':'sunlight-earth','topic':'Sunlight travel time','fact':'Light from the Sun takes about eight minutes to reach Earth.','source':'https://science.nasa.gov/sun/','category':'world'},
 {'id':'sun-star','topic':'The Sun is a star','fact':'The Sun is a star powered by nuclear fusion in its core.','source':'https://science.nasa.gov/sun/','category':'world'},
 {'id':'earth-rotation','topic':'Why we have day and night','fact':'Earth’s rotation causes the cycle of day and night.','source':'https://science.nasa.gov/earth/','category':'world'},
 {'id':'seasons','topic':'Why Earth has seasons','fact':'Earth’s seasons are mainly caused by the tilt of its axis, not its changing distance from the Sun.','source':'https://science.nasa.gov/earth/','category':'world'},
 {'id':'plate-tectonics','topic':'Earth moving plates','fact':'Earth’s outer shell is divided into tectonic plates that move slowly over time.','source':'https://www.usgs.gov/programs/earthquake-hazards/science/tectonic-plates','category':'nature'},
 {'id':'earthquakes','topic':'What causes earthquakes','fact':'Many earthquakes occur when stress is suddenly released along faults in Earth’s crust.','source':'https://www.usgs.gov/programs/earthquake-hazards/science/earthquake-facts','category':'nature'},
 {'id':'volcanic-islands','topic':'How volcanic islands form','fact':'Some ocean islands form as lava erupts from underwater volcanoes and builds up above sea level.','source':'https://www.usgs.gov/programs/VHP','category':'nature'},
 {'id':'redwood','topic':'Coast redwood height','fact':'Coast redwoods are among the tallest living trees on Earth.','source':'https://www.nps.gov/redw/learn/nature/trees.htm','category':'america'},
 {'id':'everglades','topic':'Everglades slow-moving water','fact':'The Everglades is a vast subtropical wetland with water that flows slowly through the landscape.','source':'https://www.nps.gov/ever/learn/nature/index.htm','category':'america'},
]


def run(args):
    subprocess.run(args, check=True)


def duration(path):
    return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(path)],text=True).strip())


def load_history():
    try:
        data=json.loads(HISTORY.read_text(encoding='utf-8')) if HISTORY.exists() else []
        if isinstance(data, dict):
            data = data.get('used_topics', data.get('history', data.get('used', [])))
        if not isinstance(data, list):
            raise ValueError('Unexpected history format')
        return [str(x.get('id', x.get('topic', ''))) if isinstance(x, dict) else str(x) for x in data]
    except (ValueError,OSError) as exc:
        if HISTORY.exists():
            raise RuntimeError('History unreadable; refusing to reset and repeat topics') from exc
        return []


def choose_fact(history):
    remaining=[f for f in FACTS if f['id'] not in history]
    if not remaining:
        # Rotate verified facts rather than halt scheduled publication.
        # Avoid the last five published topics when the pool cycles.
        recent=set(history[-5:])
        remaining=[f for f in FACTS if f['id'] not in recent]
        if not remaining:
            raise RuntimeError('No eligible verified topics available')
    # Favor US-specific facts while keeping topic diversity.
    weights=[2.2 if f['category']=='america' else 1.0 for f in remaining]
    return random.choices(remaining,weights=weights,k=1)[0]


def story(fact, revision=''):
    prompt=f'''Write an American-English, accurate, compelling "Did You Know?" vertical short.
Return ONLY valid JSON with keys: script, title, description, hashtags, visual_prompts.
Use ONLY the factual statements in FACT NOTES; never invent numbers, historical details, comparisons, quotes, causation, or scientific claims. You may add rhetorical questions, suspense and vivid NONFACTUAL imagery, but no unsupported facts. Avoid clickbait that misrepresents the fact.
Narration: approximately 110-130 spoken words, natural conversational US English, 45-55 seconds at a normal lively delivery; an irresistible truthful hook in the first sentence, a specific question, escalating reveal, satisfying factual answer, and a memorable final line. Every sentence must contribute new information or suspense. No filler, false claims, or generic introductions. No repeated 'Did you know' openings, no unnecessary subscribe requests.
Title under 65 characters, accurate and intriguing. Description two engaging sentences. hashtags array of 3-5 relevant hashtags. visual_prompts exactly {SCENES} distinct strings for photorealistic vertical 9:16 documentary scenes, strong foreground subject, depth and contrast, no captions/text/logos/watermarks, visually connected to story in order. Alternate wide establishing shots, macro details, explanatory scenes, and dramatic reveal. Keep central subject inside middle 70 percent of frame for mobile cropping. Do not show imaginary historical scenes as documentary photographs; use cinematic reconstructions where necessary. For scientific visuals request accurate educational visualizations.
TOPIC: {fact['topic']}
FACT NOTES: {fact['fact']}
SOURCE: {fact['source']}
REVISION: {revision}'''
    response=CLIENT.responses.create(model=MODEL,input=prompt,
        text={'format': {'type': 'json_object'}})
    raw=re.sub(r'^```(?:json)?\s*|\s*```$','',response.output_text.strip())
    data=json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError('Story JSON is not an object')
    for key in ('script','title','description'):
        if not isinstance(data.get(key),str) or not data[key].strip():
            raise ValueError('Missing story field '+key)
    if not isinstance(data.get('visual_prompts'),list) or len(data['visual_prompts'])!=SCENES or not all(isinstance(x,str) and x.strip() for x in data['visual_prompts']):
        raise ValueError('Invalid visual_prompts')
    if not isinstance(data.get('hashtags'),list):
        data['hashtags']=['#DidYouKnow','#AmazingFacts','#Shorts']
    return data


def voice(script):
    p=OUT/'voice.mp3'
    # gpt-4o-mini-tts supports delivery instructions, unlike legacy tts-1.
    kwargs=dict(model=TTS_MODEL,voice=VOICE,input=script,response_format='mp3')
    if TTS_MODEL=='gpt-4o-mini-tts':
        kwargs['instructions']='Speak in natural American English, clear, curious and expressive, like a confident documentary storyteller. Medium-brisk pace. Brief natural pauses. Never sound robotic or shout.'
    with CLIENT.audio.speech.with_streaming_response.create(**kwargs) as response:
        response.stream_to_file(p)
    return duration(p)


def generate_story_and_voice(fact):
    last=''
    for attempt in range(5):
        try:
            item=story(fact,last)
            length=voice(item['script'])
        except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            print(f'Story validation failed on attempt {attempt+1}: {exc}',flush=True)
            last='Previous response was invalid JSON or missing fields. Return a complete valid JSON object.'
            time.sleep(min(attempt+1, 4))
            continue
        print(f'Attempt {attempt+1}: {length:.2f} seconds',flush=True)
        if 45 <= length <= 55:
            return item,length
        word_count=len(item['script'].split())
        target=max(85,min(165,round(word_count*50/length)))
        last=f'Previous voice was {length:.1f}s for {word_count} words. Rewrite to about {target} words for 50 seconds. Keep all facts and visual prompts aligned.'
    raise RuntimeError('Narration failed 45-55 second requirement; no upload will occur.')


def ass_time(value):
    ticks=max(0,round(float(value)*100))
    h,r=divmod(ticks,360000)
    m,r=divmod(r,6000)
    s,cs=divmod(r,100)
    return f'{h}:{m:02}:{s:02}.{cs:02}'


def caption_groups(words):
    # Group words at punctuation and pauses.
    groups = []
    current = []
    for item in words:
        if current:
            text = ' '.join(x[2] for x in current + [item])
            gap = item[0] - current[-1][1]
            if (len(current) >= 4 or len(text) > 29 or
                    item[1] - current[0][0] > 2.1 or gap > 0.38):
                groups.append(current)
                current = []
        current.append(item)
        if re.search(r'[.!?;:]$', item[2]) or (re.search(r',$', item[2]) and len(current) >= 2):
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    return groups


def make_captions():
    with (OUT/'voice.mp3').open('rb') as f:
        transcript = CLIENT.audio.transcriptions.create(
            model='whisper-1', file=f, response_format='verbose_json',
            timestamp_granularities=['word'])
    raw = getattr(transcript, 'words', None) or []
    if not raw:
        raise RuntimeError('No word timestamps; stopping before upload')
    parsed = []
    for w in raw:
        start = float(w['start'] if isinstance(w, dict) else w.start)
        end = float(w['end'] if isinstance(w, dict) else w.end)
        content = str(w['word'] if isinstance(w, dict) else w.word).strip()
        if content and end > start:
            if len(content) > 28:
                raise RuntimeError('Caption contains a word too long for safe rendering')
            parsed.append((start, end, content))
    # Whisper word timestamps sometimes omit punctuation; recover it from the
    # full transcript when its word sequence aligns exactly.
    full_text = getattr(transcript, 'text', '') or ''
    tokens = re.findall(r"[\w]+(?:['’][\w]+)*[.,!?;:]*", full_text, re.UNICODE)
    norm = lambda x: re.sub(r'[^\w]', '', x, flags=re.UNICODE).lower()
    if len(tokens) == len(parsed) and all(norm(a[2]) == norm(b) for a,b in zip(parsed,tokens)):
        parsed = [(a,b,tok) for (a,b,_),tok in zip(parsed,tokens)]
    if not parsed:
        raise RuntimeError('Empty caption transcript')
    # Wide margins and a higher bottom safe area for YouTube UI.
    header = r'''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,58,&H0000FFFF,&H00FFFFFF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,4,1,2,150,150,450,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    lines = []
    for group in caption_groups(parsed):
        start, end = group[0][0], group[-1][1]
        text = ' '.join(x[2] for x in group)
        if len(text) > 35:
            raise RuntimeError('Subtitle exceeds safe width')
        # ASS karaoke uses measured word timings and includes inter-word pauses.
        pieces = []
        for i, (ws, we, word) in enumerate(group):
            safe = word.replace('\\', '').replace('{', '').replace('}', '')
            # ASS \k progresses through a single continuous timeline: include pauses
            # in the preceding word duration rather than inserting invisible karaoke tags.
            next_start = group[i+1][0] if i+1 < len(group) else we
            ticks = max(1, round((max(we, next_start) - ws) * 100))
            pieces.append(r'{\k' + str(ticks) + '}' + safe + (' ' if i < len(group)-1 else ''))
        caption = ''.join(pieces)
        lines.append(f'Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{caption}')
    (OUT/'subtitles.ass').write_text(header + '\n'.join(lines) + '\n', encoding='utf-8')
    (OUT/'caption_qc.json').write_text(json.dumps({
        'words': len(parsed), 'groups': len(lines),
        'max_group_chars': max(len(' '.join(w[2] for w in g)) for g in caption_groups(parsed)),
        'safe_margins_px': {'left': 150, 'right': 150, 'bottom': 450}
    }, indent=2), encoding='utf-8')


def make_images(prompts):
    for i,prompt in enumerate(prompts,1):
        print(f'Image {i}/{SCENES}',flush=True)
        result=CLIENT.images.generate(model=IMAGE_MODEL,prompt=prompt,size='1024x1536',quality='medium',n=1)
        encoded=result.data[0].b64_json
        if not encoded:
            raise RuntimeError('Image API returned no data')
        (OUT/f'scene_{i:02}.png').write_bytes(base64.b64decode(encoded))


def make_video(audio_length):
    # Fixed output resolution; upscale source before zoompan to reduce rounding jitter.
    for i in range(1,SCENES*2+1):
        frames=math.ceil(audio_length*FPS/(SCENES*2))+2
        # Alternate slow zoom-in and zoom-out for a less repetitive slideshow.
        if i%2:
            z='min(zoom+0.00035,1.10)'
        else:
            z='if(eq(on,0),1.10,max(zoom-0.00035,1.0))'
        vf=(f'scale=2400:4268:force_original_aspect_ratio=increase,crop=2400:4268,'
            f'zoompan=z=\'{z}\':x=\'(iw-iw/zoom)/2\':y=\'(ih-ih/zoom)/2\':'
            f'd={frames}:s=1080x1920:fps={FPS},setsar=1,format=yuv420p')
        run(['ffmpeg','-hide_banner','-loglevel','error','-y','-loop','1','-framerate',str(FPS),'-i',str(OUT/f'scene_{((i-1)//2)+1:02}.png'),'-vf',vf,'-frames:v',str(frames),'-an','-c:v','libx264','-preset','veryfast','-crf','25','-pix_fmt','yuv420p',str(OUT/f'clip_{i:02}.mp4')])
    with (OUT/'clips.txt').open('w',encoding='utf-8') as f:
        for i in range(1,SCENES*2+1):
            f.write(f"file 'clip_{i:02}.mp4'\n")
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(OUT/'clips.txt'),'-c','copy',str(OUT/'joined.mp4')])
    # Optional royalty-cleared user-supplied soundtrack. Never download random copyrighted music.
    music=Path('assets/background.mp3')
    filters='[0:v]ass=output/subtitles.ass[v]'
    args=['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(OUT/'joined.mp4'),'-i',str(OUT/'voice.mp3')]
    if music.is_file():
        args+=['-stream_loop','-1','-i',str(music)]
        filters+=';[2:a]volume=0.10[bg];[1:a][bg]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]'
        audio_map='[a]'
    else:
        audio_map='1:a:0'
    args+=['-filter_complex',filters,'-map','[v]','-map',audio_map,'-c:v','libx264','-preset','veryfast','-crf','24','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-t',f'{audio_length:.3f}','-movflags','+faststart',str(OUT/'short.mp4')]
    run(args)


def quality_check(final_length):
    # Hard-fail objective checks.
    if not 45 <= final_length <= 55:
        raise RuntimeError(f'Video length invalid: {final_length:.2f}')
    probe = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_streams', '-of', 'json',
        str(OUT/'short.mp4')], text=True))
    video = next((x for x in probe['streams'] if x['codec_type'] == 'video'), None)
    audio = next((x for x in probe['streams'] if x['codec_type'] == 'audio'), None)
    if not video or (video['width'], video['height']) != (1080, 1920):
        raise RuntimeError('Invalid Shorts video resolution')
    if not audio:
        raise RuntimeError('Missing audio track')
    if (OUT/'short.mp4').stat().st_size < 100_000:
        raise RuntimeError('Video file unexpectedly small')
    qc = {'passed': True, 'duration_seconds': round(final_length, 2),
          'resolution': '1080x1920', 'audio_present': True,
          'visual_review_required': True}
    (OUT/'quality_report.json').write_text(json.dumps(qc, indent=2), encoding='utf-8')


def main():
    history=load_history()
    fact=choose_fact(history)
    print('Selected:',fact['topic'],flush=True)
    item,audio_length=generate_story_and_voice(fact)
    (OUT/'script.txt').write_text(item['script'],encoding='utf-8')
    (OUT/'fact_check.json').write_text(json.dumps(fact,indent=2,ensure_ascii=False),encoding='utf-8')
    tags=[x for x in item['hashtags'] if isinstance(x,str) and x.startswith('#')][:5]
    clean=lambda value: re.sub(r'[<>]', '', str(value)).strip()
    meta={'title':clean(item['title'])[:95],'description':clean(item['description'])+'\n\n'+' '.join(tags)+'\n\nSource: '+fact['source'],'tags':['FactShock AI','Did You Know','Amazing Facts','Interesting Facts','American Trivia',fact['category']]}
    (OUT/'youtube_metadata.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding='utf-8')
    make_captions()
    make_images(item['visual_prompts'])
    make_video(audio_length)
    final_length=duration(OUT/'short.mp4')
    quality_check(final_length)

    # History is committed only after a successful upload, in the workflow.
    history.append(fact['id'])
    history = history[-200:]
    (OUT/'next_fact_history.json').write_text(json.dumps(history,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f'FACTSHOCK VIDEO READY: {final_length:.2f}s',flush=True)

if __name__=='__main__':
    main()
