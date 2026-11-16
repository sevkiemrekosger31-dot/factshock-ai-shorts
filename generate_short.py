    cs=max(0,round(seconds*100)); h,rem=divmod(cs,360000); m,rem=divmod(rem,6000); s,c=divmod(rem,100)
    return f'{h}:{m:02}:{s:02}.{c:02}'
def write_subtitles(segments):
    header='''[Script Info]
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
    with (OUT/'subtitles.ass').open('w',encoding='utf-8') as f:
        f.write(header)
        for seg in segments:
            start,end=float(seg.start),float(seg.end)
            words=seg.text.strip().split()
            if not words or end<=start: continue
            pos=start
            for i in range(0,len(words),5):
                chunk=words[i:i+5]; nxt=pos+(end-start)*len(chunk)/len(words)
                txt=' '.join(chunk).replace('\\','').replace('{','').replace('}','')
                f.write(f'Dialogue: 0,{ass_time(pos)},{ass_time(nxt)},Default,,0,0,0,,{txt}\n'); pos=nxt

def choose_fact():
    history_file=Path('fact_history.json')
    history=json.loads(history_file.read_text(encoding='utf-8')) if history_file.exists() else []
    unused=[f for f in FACTS if f['id'] not in history]
    if not unused: history=[]; unused=FACTS[:]
    return random.choice(unused),history

def draft_script(fact):
    response=claude.messages.create(model=CLAUDE_MODEL,max_tokens=650,messages=[{'role':'user','content':(
        'You write highly engaging, original 30-45 second American English science Shorts. '
        'Write approximately 85-100 spoken words. Hook immediately with a surprising, accurate fact or question; '
        'avoid generic intros such as “Did you know” or “Scientists say”. '
        'Build suspense with short, conversational sentences, then reveal one clear wow moment. '
        'Finish with one specific, easy-to-answer comment question. '
        'Use ONLY the factual notes below. Never invent a comparison, date, statistic, discovery, consequence, or certainty. '
        'Do not imply a black hole itself emits light. No headings, stage directions, hashtags or claims about what viewers think.\n'
        f'TOPIC: {fact["topic"]}\nFACT NOTES: {fact["fact"]}') }])
    return ''.join(b.text for b in response.content if b.type=='text').strip()

def edit_script(draft,fact,adjustment=''):
    response=openai.responses.create(model=TEXT_MODEL,instructions=(
        'Return ONLY valid JSON with keys script, title, description, hashtags. '
        'Rewrite into natural, vivid American English for a 30-45 second YouTube Short, targeting 85-100 words. '
        'First sentence must be a strong, factually defensible hook; use short sentences and one surprising reveal. '
        'End with a specific question that invites comments. Avoid filler, repetitive hooks and overhype. '
        'Use ONLY the supplied factual notes. Never add unsupported claims, dates, statistics or comparisons. '
        'Title accurate and under 65 characters. Description 2 concise sentences. '
        'Hashtags array of 3-5 strings beginning with #. No headings in script.'),
        input=f'FACT NOTES:\n{fact["fact"]}\n\nDRAFT:\n{draft}\n\nADJUSTMENT: {adjustment}')
    data=parse_json(response.output_text)
    if not isinstance(data,dict) or not isinstance(data.get('script'),str) or not data['script'].strip(): raise ValueError('Invalid script JSON')
    return data

def review_script(script,fact):
    response=openai.responses.create(model=TEXT_MODEL,instructions=(
        'You are a conservative scientific claim auditor. Compare every factual claim in the SCRIPT to the FACT NOTES. '
        'Return ONLY valid JSON with keys approved (boolean) and reason (string). '
        'Approve only when all factual assertions are directly supported by the notes or are simple non-factual rhetoric. '
        'Reject invented statistics, analogies that imply unsupported facts, false dates, misleading absolutes and extra discoveries. '
        'A question at the end does not need a factual answer. If uncertain, reject.'),
        input=f'FACT NOTES:\n{fact["fact"]}\n\nSCRIPT:\n{script}')
    data=parse_json(response.output_text)
    if data.get('approved') is not True: raise ValueError('Fact audit rejected: '+str(data.get('reason','Unknown')))

def create_voice(script):
    with openai.audio.speech.with_streaming_response.create(model='tts-1',voice='onyx',input=script,speed=1.05) as response:
        response.stream_to_file(OUT/'voice.mp3')
    return duration(OUT/'voice.mp3')

def generate_images(script):
    response=openai.responses.create(model=TEXT_MODEL,instructions=(
        'Return ONLY a JSON array of exactly five STRINGS, not objects. '
        'Each string is a distinct cinematic documentary still image prompt for the supplied script. '
        'Vertical 9:16, photorealistic, dramatic, visually clear. No text, logo, captions or watermarks. '
        'Do not visually imply unsupported scientific facts.'),input=script)
    prompts=parse_json(response.output_text)
    if not isinstance(prompts,list) or len(prompts)!=IMAGE_COUNT or not all(isinstance(p,str) and p.strip() for p in prompts):
        raise ValueError('Image prompts must be exactly five nonempty strings')
    for i,prompt in enumerate(prompts,1):
        print(f'Generating image {i}/{IMAGE_COUNT}',flush=True)
        result=openai.images.generate(model=IMAGE_MODEL,prompt=prompt,size='1024x1536',quality='medium',n=1)
        image_data=result.data[0].b64_json
        if not image_data: raise RuntimeError(f'Image {i} returned no base64 data')
        (OUT/f'scene_{i:02}.png').write_bytes(base64.b64decode(image_data))

def render_video(audio_len):
    scene_len=audio_len/IMAGE_COUNT
    for i in range(1,IMAGE_COUNT+1):
        vf=f'scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps={FPS}'
        run(['ffmpeg','-hide_banner','-loglevel','error','-y','-loop','1','-framerate',str(FPS),'-i',str(OUT/f'scene_{i:02}.png'),'-vf',vf,'-t',str(scene_len),'-an','-c:v','libx264','-preset','veryfast','-crf','24','-pix_fmt','yuv420p',str(OUT/f'clip_{i:02}.mp4')])
    with (OUT/'clips.txt').open('w',encoding='utf-8') as f:
        for i in range(1,IMAGE_COUNT+1): f.write(f"file 'clip_{i:02}.mp4'\n")
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-f','concat','-safe','0','-i',str(OUT/'clips.txt'),'-c','copy',str(OUT/'joined.mp4')])
    run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(OUT/'joined.mp4'),'-i',str(OUT/'voice.mp3'),'-vf','ass=output/subtitles.ass','-map','0:v:0','-map','1:a:0','-c:v','libx264','-preset','veryfast','-crf','24','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-t',str(audio_len),'-movflags','+faststart',str(OUT/'short.mp4')])

def main():
    print('FACTSHOCK AI STARTED',flush=True)
    fact,history=choose_fact()
    print('Selected topic:',fact['topic'],flush=True)
    (OUT/'fact_check.json').write_text(json.dumps(fact,indent=2,ensure_ascii=False),encoding='utf-8')
    draft=draft_script(fact)
    data=None; audio_len=0
    for attempt in range(3):
        adjustment='' if attempt==0 else ('Make this shorter, while retaining all facts.' if audio_len>45 else 'Make this slightly longer, using only supported facts.')
        data=edit_script(draft,fact,adjustment)
        script=data['script'].strip()
        review_script(script,fact)
        audio_len=create_voice(script)
        print(f'Attempt {attempt+1}: audio {audio_len:.1f}s',flush=True)
        if 30<=audio_len<=45: break
        draft=script
    if not 30<=audio_len<=45: raise ValueError('Could not achieve 30-45s narration')
    # Metadata is written only after the final script passes audit and duration checks.
    hashtags=data.get('hashtags',[])
    if not isinstance(hashtags,list): hashtags=[]
    hashtags=[str(h) for h in hashtags if isinstance(h,str) and h.startswith('#')][:5]
    metadata={'title':str(data.get('title','FactShock Science Fact')).strip()[:95],
              'description':str(data.get('description','')).strip()+'\n\n'+' '.join(hashtags)+'\n\nSource: '+fact['source']+' - '+fact['url']}
    (OUT/'script.txt').write_text(script,encoding='utf-8')
    (OUT/'youtube_metadata.json').write_text(json.dumps(metadata,indent=2,ensure_ascii=False),encoding='utf-8')
    with (OUT/'voice.mp3').open('rb') as f:
        transcription=openai.audio.transcriptions.create(model='whisper-1',file=f,response_format='verbose_json',timestamp_granularities=['segment'])
    write_subtitles(transcription.segments)
    generate_images(script)
    render_video(audio_len)
    if not (OUT/'short.mp4').is_file() or (OUT/'short.mp4').stat().st_size==0: raise RuntimeError('Video not generated')
    history.append(fact['id'])
    Path('fact_history.json').write_text(json.dumps(history,indent=2),encoding='utf-8')
    print('FACTSHOCK VIDEO READY',round(audio_len,1),'seconds',flush=True)

if __name__=='__main__': main()
