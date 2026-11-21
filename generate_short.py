import base64
import json
import math
import os
import random
import re
import subprocess
import textwrap
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
SCENES = 6

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
]


def run(args):
    subprocess.run(args, check=True)


def duration(path):
    return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','default=noprint_wrappers=1:nokey=1',str(path)],text=True).strip())


def load_history():
    try:
        data=json.loads(HISTORY.read_text(encoding='utf-8')) if HISTORY.exists() else []
        return data if isinstance(data,list) else []
    except (ValueError,OSError):
        return []


def choose_fact(history):
    remaining=[f for f in FACTS if f['id'] not in history]
    if not remaining:
        raise RuntimeError('All verified topics used. Add reviewed FACTS before publishing more; history will NOT reset.')
    # Favor US-specific facts while keeping topic diversity.
    weights=[2.2 if f['category']=='america' else 1.0 for f in remaining]
    return random.choices(remaining,weights=weights,k=1)[0]


def story(fact, revision=''):
    prompt=f'''Write an American-English, accurate, compelling "Did You Know?" vertical short.
Return ONLY valid JSON with keys: script, title, description, hashtags, visual_prompts.
Use ONLY the factual statements in FACT NOTES; never invent numbers, historical details, comparisons, quotes, causation, or scientific claims. You may add rhetorical questions, suspense and vivid NONFACTUAL imagery, but no unsupported facts. Avoid clickbait that misrepresents the fact.
Narration: 115-135 spoken words, natural conversational US English, 45-55 seconds at a normal lively delivery; a powerful first sentence, a curiosity-building middle, satisfying specific answer, and a memorable final line. No repeated 'Did you know' openings, no unnecessary subscribe requests.
Title under 65 characters, accurate and intriguing. Description two engaging sentences. hashtags array of 3-5 relevant hashtags. visual_prompts exactly {SCENES} distinct strings for photorealistic vertical 9:16 documentary scenes, no captions/text/logos/watermarks, visually connected to story in order. Do not show imaginary historical scenes as documentary photographs; use cinematic reconstructions where necessary. For scientific visuals request accurate educational visualizations.
TOPIC: {fact['topic']}
FACT NOTES: {fact['fact']}
SOURCE: {fact['source']}
REVISION: {revision}'''
    response=CLIENT.responses.create(model=MODEL,input=prompt)
    raw=re.sub(r'^```(?:json)?\s*|\s*```$','',response.output_text.strip())
    data=json.loads(raw)
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
        item=story(fact,last)
        length=voice(item['script'])
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


def make_captions():
    with (OUT/'voice.mp3').open('rb') as f:
        transcript=CLIENT.audio.transcriptions.create(model='whisper-1',file=f,response_format='verbose_json',timestamp_granularities=['word'])
    words=getattr(transcript,'words',None) or []
    if not words:
        raise RuntimeError('Word-level timestamps unavailable; refusing to make inaccurate subtitles.')
    header='''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,DejaVu Sans,61,&H00FFFFFF,&H0000FFFF,&H00000000,&H90000000,-1,0,0,0,100,100,0,0,1,4,1,2,130,130,420,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    parsed=[]
    for w in words:
        start=float(w['start'] if isinstance(w,dict) else w.start)
        end=float(w['end'] if isinstance(w,dict) else w.end)
        content=str(w['word'] if isinstance(w,dict) else w.word).strip()
        if content and end>start:
            parsed.append((start,end,content))
    if not parsed:
        raise RuntimeError('Empty timed transcript')
    lines=[]
    chunk=[]
    def flush():
        if not chunk:
            return
        start,end=chunk[0][0],chunk[-1][1]
        text=' '.join(x[2] for x in chunk)
        # Conservative character cap + short chunks to stay inside the frame.
        text=text.replace('\\','').replace('{','').replace('}','')
        if len(text)>31:
            raise RuntimeError('Caption chunk exceeded safe width')
        # Highlight final word in yellow (ASS BGR color).
        tokens=text.split(' ')
        if len(tokens)>1:
            text=' '.join(tokens[:-1])+' '+r'{\c&H0000FFFF&}'+tokens[-1]+r'{\c&H00FFFFFF&}'
        lines.append(f'Dialogue: 0,{ass_time(start)},{ass_time(end)},Default,,0,0,0,,{text}')
    for w in parsed:
        candidate=' '.join([x[2] for x in chunk]+[w[2]])
        if chunk and (len(chunk)>=3 or len(candidate)>31 or w[1]-chunk[0][0]>2.2):
            flush()
            chunk=[]
        if len(w[2])>31:
            raise RuntimeError('Single subtitle word too long')
        chunk.append(w)
    flush()
    (OUT/'subtitles.ass').write_text(header+'\n'.join(lines)+'\n',encoding='utf-8')


def make_images(prompts):
    for i,prompt in enumerate(prompts,1):
        print(f'Image {i}/{SCENES}',flush=True)
        result=CLIENT.images.generate(model=IMAGE_MODEL,prompt=prompt,size='1024x1536',quality='medium',n=1)
        encoded=result.data[0].b64_json
        if not encoded:
            raise RuntimeError('Image API returned no data')
        (OUT/f'scene_{i:02}.png').write_bytes(base64.b64decode(encoded))


def make_video(audio_length):
    # Fixed output resolution; zoompan uses 1080x1920, smooth motion without paid video models.
    for i in range(1,SCENES+1):
        frames=math.ceil(audio_length*FPS/SCENES)+2
        # Alternate slow zoom-in and zoom-out for a less repetitive slideshow.
        if i%2:
            z='min(zoom+0.00035,1.10)'
        else:
            z='if(eq(on,0),1.10,max(zoom-0.00035,1.0))'
        vf=(f'scale=1200:2134:force_original_aspect_ratio=increase,crop=1200:2134,'
            f'zoompan=z=\'{z}\':x=\'(iw-iw/zoom)/2\':y=\'(ih-ih/zoom)/2\':'
            f'd={frames}:s=1080x1920:fps={FPS},setsar=1,format=yuv420p')
        run(['ffmpeg','-hide_banner','-loglevel','error','-y','-loop','1','-framerate',str(FPS),'-i',str(OUT/f'scene_{i:02}.png'),'-vf',vf,'-frames:v',str(frames),'-an','-c:v','libx264','-preset','veryfast','-crf','25','-pix_fmt','yuv420p',str(OUT/f'clip_{i:02}.mp4')])
    with (OUT/'clips.txt').open('w',encoding='utf-8') as f:
        for i in range(1,SCENES+1):
            f.write(f"file 'clip_{i:02}.mp4'\n")
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(OUT/'clips.txt'),'-c','copy',str(OUT/'joined.mp4')])
    # Optional royalty-cleared user-supplied soundtrack. Never download random copyrighted music.
    music=Path('assets/background.mp3')
    filters='[0:v]ass=output/subtitles.ass[v]'
    args=['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(OUT/'joined.mp4'),'-i',str(OUT/'voice.mp3')]
    if music.is_file():
        args+=['-stream_loop','-1','-i',str(music)]
        filters+=';[2:a]volume=0.10[bg];[1:a][bg]amix=inputs=2:duration=first:dropout_transition=0[a]'
        audio_map='[a]'
    else:
        audio_map='1:a:0'
    args+=['-filter_complex',filters,'-map','[v]','-map',audio_map,'-c:v','libx264','-preset','veryfast','-crf','24','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-t',f'{audio_length:.3f}','-movflags','+faststart',str(OUT/'short.mp4')]
    run(args)


def main():
    history=load_history()
    fact=choose_fact(history)
    print('Selected:',fact['topic'],flush=True)
    item,audio_length=generate_story_and_voice(fact)
    (OUT/'script.txt').write_text(item['script'],encoding='utf-8')
    (OUT/'fact_check.json').write_text(json.dumps(fact,indent=2,ensure_ascii=False),encoding='utf-8')
    tags=[x for x in item['hashtags'] if isinstance(x,str) and x.startswith('#')][:5]
    meta={'title':item['title'][:95],'description':item['description']+'\n\n'+' '.join(tags)+'\n\nSource: '+fact['source'],'tags':['FactShock AI','Did You Know','Amazing Facts','Interesting Facts','American Trivia',fact['category']]}
    (OUT/'youtube_metadata.json').write_text(json.dumps(meta,indent=2,ensure_ascii=False),encoding='utf-8')
    make_captions()
    make_images(item['visual_prompts'])
    make_video(audio_length)
    final_length=duration(OUT/'short.mp4')
    if not 45<=final_length<=55:
        raise RuntimeError(f'Video length invalid: {final_length:.2f}')
    history.append(fact['id'])
    HISTORY.write_text(json.dumps(history,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(f'FACTSHOCK VIDEO READY: {final_length:.2f}s',flush=True)

if __name__=='__main__':
    main()
