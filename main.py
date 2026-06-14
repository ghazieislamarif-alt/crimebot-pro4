import os
import time
import random
import logging
import requests
import json
import subprocess
import asyncio
import re
import base64
from pathlib import Path
from datetime import datetime
import google.generativeai as genai

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ─── CONFIG ───────────────────────────────────────────────────────────────────
GEMINI_API_KEY     = os.getenv("GEMINI_API_KEY")
PEXELS_API_KEY     = os.getenv("PEXELS_API_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")
VIDEOS_PER_DAY     = int(os.getenv("VIDEOS_PER_DAY", "1"))

WORK_DIR = Path("/tmp/crime_bot")
WORK_DIR.mkdir(exist_ok=True)

# ─── TELEGRAM ─────────────────────────────────────────────────────────────────
def send_telegram(message: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        }, timeout=15)
    except Exception as e:
        logger.error(f"Telegram message error: {e}")

def send_telegram_video(video_path: str, caption: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendVideo"
        with open(video_path, "rb") as f:
            requests.post(url, data={
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": caption[:1024],
                "parse_mode": "HTML"
            }, files={"video": f}, timeout=300)
        logger.info("Video sent to Telegram")
    except Exception as e:
        logger.error(f"Telegram video error: {e}")
        send_telegram(f"❌ Video send failed: {e}")

def send_telegram_document(file_path: str, caption: str):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
        with open(file_path, "rb") as f:
            requests.post(url, data={
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": caption[:1024],
                "parse_mode": "HTML"
            }, files={"document": f}, timeout=300)
    except Exception as e:
        logger.error(f"Telegram document error: {e}")

# ─── GEMINI HELPERS ───────────────────────────────────────────────────────────
def get_gemini_model():
    if not GEMINI_API_KEY:
        raise Exception("GEMINI_API_KEY not set in Railway variables!")
    genai.configure(api_key=GEMINI_API_KEY)
    for model_name in [
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-1.5-pro",
    ]:
        try:
            model = genai.GenerativeModel(model_name)
            test = model.generate_content("say ok")
            logger.info(f"✅ Gemini working: {model_name}")
            return model
        except Exception as e:
            logger.warning(f"Model {model_name} failed: {e}")
            time.sleep(2)
            continue
    raise Exception("All Gemini models failed — check API key in Railway!")

# ─── STEP 1: GENERATE SCRIPT ──────────────────────────────────────────────────
def generate_script() -> dict:
    logger.info("Generating script...")
    model = get_gemini_model()

    themes = [
        "a serial killer who targeted hikers in national parks",
        "a woman who discovered her husband had a secret family",
        "a neighborhood stalker who left cryptic messages",
        "a college student who vanished after a late-night study session",
        "an Airbnb guest who found hidden cameras",
        "a family terrorized by an unknown person watching their home",
        "a missing persons case that turned into something darker",
        "a true crime cold case finally solved after 20 years",
        "a killer who mimicked famous serial killers",
        "a small town with a dark secret nobody talked about",
        "a woman who survived a kidnapping and identified her captor",
        "a man who discovered his neighbor was a wanted fugitive",
        "a babysitter who received threatening calls from inside the house",
        "a hiker who found a body in a remote mountain trail",
        "a journalist who uncovered a local politician's dark crimes",
    ]
    theme = random.choice(themes)
    logger.info(f"Selected theme: {theme}")

    prompt = f"""You are a top true crime YouTube narrator writing in the style of Mr. Nightmare — creepy, suspenseful, slow-building dread, first or second person perspective, very detailed.

Write a FULL scary true crime story about: {theme}

STRICT REQUIREMENTS:
- Total word count: 2800 to 3200 words (this is critical for 15-20 min video)
- Structure it in exactly 6 chapters as shown below
- Make it feel REAL, like it actually happened
- Use second-person "you" or first-person "I" for immersion
- Build tension slowly, don't rush the scary parts
- Add creepy specific details (sounds, smells, exact times, exact locations)
- End with a chilling conclusion

CHAPTERS:
1. HOOK (200 words) — Start with the most terrifying moment, then say "but let me take you back to the beginning"
2. NORMAL LIFE (400 words) — Establish the victim's normal routine before everything changed
3. FIRST WARNING SIGNS (500 words) — Subtle creepy things start happening, easy to dismiss
4. ESCALATION (600 words) — Things get worse, victim starts to realize something is very wrong
5. THE TERRIFYING TRUTH (700 words) — The full horror is revealed, most intense chapter
6. AFTERMATH (400 words) — What happened after, lasting trauma, chilling conclusion

Return ONLY this JSON format (no markdown, no backticks):
{{
  "title": "scary clickbait YouTube title",
  "description": "YouTube description 150 words with keywords for USA/Europe audience",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5", "tag6", "tag7", "tag8", "tag9", "tag10"],
  "chapters": [
    {{"name": "HOOK", "search_keyword": "dark forest night scary", "text": "full chapter text here..."}},
    {{"name": "NORMAL LIFE", "search_keyword": "suburban neighborhood house", "text": "full chapter text here..."}},
    {{"name": "FIRST WARNING SIGNS", "search_keyword": "shadow dark window night", "text": "full chapter text here..."}},
    {{"name": "ESCALATION", "search_keyword": "crime scene police lights", "text": "full chapter text here..."}},
    {{"name": "THE TERRIFYING TRUTH", "search_keyword": "dark room horror scary", "text": "full chapter text here..."}},
    {{"name": "AFTERMATH", "search_keyword": "empty road fog night", "text": "full chapter text here..."}}
  ]
}}"""

    for attempt in range(3):
        try:
            logger.info(f"Script attempt {attempt+1}/3...")
            response = model.generate_content(prompt)
            text = response.text.strip()
            logger.info(f"Raw response preview: {text[:100]}")
            text = text.replace("```json", "").replace("```", "").strip()
            # Find JSON boundaries safely
            start = text.find("{")
            end = text.rfind("}") + 1
            if start == -1 or end == 0:
                raise Exception(f"No JSON found in response. Got: {text[:200]}")
            text = text[start:end]
            data = json.loads(text)
            total_words = sum(len(c["text"].split()) for c in data["chapters"])
            logger.info(f"✅ Script generated: {total_words} words | {data['title'][:50]}")
            return data
        except Exception as e:
            logger.warning(f"Script attempt {attempt+1} failed: {e}")
            time.sleep(8)

    raise Exception("Failed to generate script after 3 attempts — check Railway logs for details")

# ─── STEP 2A: GEMINI TTS ──────────────────────────────────────────────────────
def generate_audio_gemini(text: str, output_path: str) -> bool:
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-preview-tts:generateContent?key={GEMINI_API_KEY}"

        clean_text = re.sub(r'[*#\[\]()]', '', text)
        clean_text = clean_text.replace('\n\n', ' ').replace('\n', ' ').strip()

        # Gemini TTS limit ~4800 chars
        if len(clean_text) > 4800:
            clean_text = clean_text[:4800]

        payload = {
            "contents": [{"parts": [{"text": clean_text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": "Charon"
                        }
                    }
                }
            }
        }

        response = requests.post(url, json=payload, timeout=120)

        if response.status_code == 200:
            data = response.json()
            audio_data = data["candidates"][0]["content"]["parts"][0]["inlineData"]["data"]
            audio_bytes = base64.b64decode(audio_data)
            with open(output_path, "wb") as f:
                f.write(audio_bytes)
            size_kb = len(audio_bytes) / 1024
            logger.info(f"Gemini TTS success: {size_kb:.0f} KB")
            return True
        else:
            logger.warning(f"Gemini TTS HTTP {response.status_code}: {response.text[:300]}")
            return False

    except Exception as e:
        logger.error(f"Gemini TTS exception: {e}")
        return False

# ─── STEP 2B: EDGE TTS FALLBACK ──────────────────────────────────────────────
async def _edge_tts_async(text: str, output_path: str, voice: str):
    import edge_tts
    communicate = edge_tts.Communicate(text, voice=voice, rate="-5%", pitch="-8Hz")
    await communicate.save(output_path)

def generate_audio_edge_tts(text: str, output_path: str) -> bool:
    try:
        import edge_tts  # confirm installed

        clean_text = re.sub(r'[*#\[\]()]', '', text)
        clean_text = clean_text.replace('\n\n', ' ').replace('\n', ' ').strip()

        voices = [
            "en-US-GuyNeural",
            "en-US-DavisNeural",
            "en-GB-RyanNeural",
            "en-AU-WilliamNeural",
        ]
        voice = random.choice(voices)
        logger.info(f"Edge TTS voice: {voice}")

        # Always create fresh event loop — fixes Railway asyncio issues
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_edge_tts_async(clean_text, output_path, voice))
        finally:
            loop.close()

        if Path(output_path).exists() and Path(output_path).stat().st_size > 1000:
            logger.info(f"Edge TTS success: {output_path}")
            return True
        else:
            logger.warning("Edge TTS produced empty file")
            return False

    except Exception as e:
        logger.error(f"Edge TTS exception: {e}")
        return False

# ─── STEP 2C: AUDIO ORCHESTRATOR ─────────────────────────────────────────────
def generate_chapter_audio(chapter_text: str, chapter_index: int) -> str:
    wav_path = str(WORK_DIR / f"audio_chapter_{chapter_index}.wav")
    mp3_path = str(WORK_DIR / f"audio_chapter_{chapter_index}.mp3")

    logger.info(f"Chapter {chapter_index+1}: Trying Gemini TTS (Charon)...")
    if generate_audio_gemini(chapter_text, wav_path):
        if Path(wav_path).exists() and Path(wav_path).stat().st_size > 1000:
            return wav_path

    logger.warning(f"Chapter {chapter_index+1}: Falling back to Edge TTS...")
    if generate_audio_edge_tts(chapter_text, mp3_path):
        if Path(mp3_path).exists() and Path(mp3_path).stat().st_size > 1000:
            return mp3_path

    raise Exception(f"All TTS methods failed for chapter {chapter_index+1}")

# ─── STEP 3: FETCH PEXELS VIDEOS ─────────────────────────────────────────────
def fetch_pexels_video(keyword: str, used_ids: set) -> str | None:
    dark_keywords = [
        keyword,
        f"dark {keyword}",
        f"night {keyword}",
        "dark forest night",
        "crime scene dark",
        "shadow mystery night"
    ]

    for query in dark_keywords:
        try:
            headers = {"Authorization": PEXELS_API_KEY}
            params = {"query": query, "per_page": 15, "orientation": "landscape", "size": "medium"}
            res = requests.get("https://api.pexels.com/videos/search", headers=headers, params=params, timeout=20)

            if res.status_code != 200:
                continue

            videos = res.json().get("videos", [])
            random.shuffle(videos)

            for video in videos:
                vid_id = video["id"]
                if vid_id in used_ids:
                    continue

                files = sorted(video.get("video_files", []), key=lambda x: x.get("width", 0), reverse=True)

                for vf in files:
                    if vf.get("width", 0) >= 1280 and vf.get("file_type") == "video/mp4":
                        output = str(WORK_DIR / f"video_{vid_id}.mp4")

                        if Path(output).exists():
                            used_ids.add(vid_id)
                            return output

                        r = requests.get(vf["link"], timeout=60, stream=True)
                        if r.status_code == 200:
                            with open(output, "wb") as fp:
                                for chunk in r.iter_content(chunk_size=8192):
                                    fp.write(chunk)
                            used_ids.add(vid_id)
                            logger.info(f"Pexels downloaded: {query}")
                            return output

        except Exception as e:
            logger.warning(f"Pexels error '{query}': {e}")
            continue

    return None

# ─── STEP 4: AUDIO DURATION ───────────────────────────────────────────────────
def get_audio_duration(audio_path: str) -> float:
    try:
        result = subprocess.run([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "json", audio_path
        ], capture_output=True, text=True, timeout=30)
        data = json.loads(result.stdout)
        duration = float(data["format"]["duration"])
        logger.info(f"Audio duration: {duration:.1f}s")
        return duration
    except Exception as e:
        logger.warning(f"ffprobe failed: {e}, using 60s default")
        return 60.0

# ─── STEP 5: ASSEMBLE CHAPTER VIDEO ──────────────────────────────────────────
def assemble_chapter_video(video_path: str, audio_path: str, chapter_index: int, duration: float) -> str:
    output = str(WORK_DIR / f"chapter_{chapter_index}.mp4")

    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1",
        "-i", video_path,
        "-i", audio_path,
        "-t", str(duration),
        "-vf", (
            "scale=1920:1080:force_original_aspect_ratio=increase,"
            "crop=1920:1080,"
            "eq=brightness=-0.05:saturation=0.7:contrast=1.1,"
            "vignette=PI/4"
        ),
        "-af", "volume=1.0,aecho=0.3:0.1:40:0.3",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-r", "24",
        "-shortest",
        output
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise Exception(f"FFmpeg chapter {chapter_index} error: {result.stderr[-300:]}")
    logger.info(f"Chapter {chapter_index+1} assembled ✅")
    return output

# ─── STEP 6: BACKGROUND MUSIC ────────────────────────────────────────────────
def add_background_music(video_path: str, output_path: str) -> str:
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-f", "lavfi",
            "-i", "aevalsrc=0.03*sin(2*PI*60*t)+0.02*sin(2*PI*80*t)+0.01*sin(2*PI*40*t):s=44100",
            "-filter_complex",
            "[1:a]volume=0.12[music];[0:a][music]amix=inputs=2:duration=first:dropout_transition=3[aout]",
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            logger.warning("Music add failed, skipping")
            return video_path
        logger.info("Dark ambient music added ✅")
        return output_path
    except Exception as e:
        logger.warning(f"Music skip: {e}")
        return video_path

# ─── STEP 7: MERGE CHAPTERS ───────────────────────────────────────────────────
def merge_all_chapters(chapter_videos: list, output_path: str) -> str:
    concat_file = str(WORK_DIR / "concat.txt")
    with open(concat_file, "w") as f:
        for v in chapter_videos:
            f.write(f"file '{v}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", concat_file,
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        output_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        raise Exception(f"FFmpeg merge error: {result.stderr[-300:]}")
    logger.info("All chapters merged ✅")
    return output_path

# ─── MAIN PIPELINE ────────────────────────────────────────────────────────────
def produce_video():
    send_telegram("🎬 <b>Crime Bot PRO Started!</b>\nGenerating Mr. Nightmare story... 🔪")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    try:
        send_telegram("📝 Step 1/5: Writing scary script...")
        script = generate_script()
        total_words = sum(len(c["text"].split()) for c in script["chapters"])
        send_telegram(
            f"✅ Script ready!\n"
            f"📖 <b>{script['title']}</b>\n"
            f"📊 {total_words} words (~{total_words//150} min)"
        )

        used_video_ids = set()
        chapter_videos = []

        for i, chapter in enumerate(script["chapters"]):
            send_telegram(f"🎙 Chapter {i+1}/6: <b>{chapter['name']}</b>")
            audio_path = generate_chapter_audio(chapter["text"], i)
            audio_duration = get_audio_duration(audio_path)

            video_path = fetch_pexels_video(chapter["search_keyword"], used_video_ids)
            if not video_path:
                video_path = fetch_pexels_video("dark night mystery", used_video_ids)
            if not video_path:
                raise Exception(f"No video found for chapter {i+1}")

            chapter_video = assemble_chapter_video(video_path, audio_path, i, audio_duration)
            chapter_videos.append(chapter_video)

        send_telegram("✂️ Step 3/5: Merging chapters...")
        merged_path = str(WORK_DIR / f"merged_{timestamp}.mp4")
        merge_all_chapters(chapter_videos, merged_path)

        send_telegram("🎵 Step 4/5: Adding dark ambient music...")
        final_path = str(WORK_DIR / f"final_{timestamp}.mp4")
        add_background_music(merged_path, final_path)

        send_telegram("📤 Step 5/5: Uploading to Telegram...")
        file_size_mb = Path(final_path).stat().st_size / (1024 * 1024)

        caption = (
            f"🎬 <b>{script['title']}</b>\n\n"
            f"📊 {total_words} words | ~{total_words//150} min\n"
            f"🏷 {', '.join(script['tags'][:5])}\n\n"
            f"📝 <b>Description:</b>\n{script['description']}"
        )

        if file_size_mb < 50:
            send_telegram_video(final_path, caption)
        else:
            send_telegram(f"⚠️ {file_size_mb:.0f}MB — sending as document...")
            send_telegram_document(final_path, caption)

        send_telegram(f"✅ <b>Done!</b> 🎬\n📁 {file_size_mb:.1f}MB | Ready for YouTube!")

        # Cleanup
        for f in WORK_DIR.glob("audio_chapter_*"):
            f.unlink(missing_ok=True)
        for f in WORK_DIR.glob("chapter_*.mp4"):
            f.unlink(missing_ok=True)
        Path(merged_path).unlink(missing_ok=True)

    except Exception as e:
        logger.error(f"Pipeline error: {e}")
        send_telegram(f"❌ <b>Error:</b>\n{str(e)[:300]}\n\nCheck Railway logs.")

# ─── SCHEDULER ────────────────────────────────────────────────────────────────
def main():
    import schedule

    send_telegram(
        "🚀 <b>Crime Bot PRO Online!</b>\n"
        "🎙 Gemini Charon + Edge TTS fallback\n"
        "🎬 Mr. Nightmare | 15-20 min videos\n"
        f"📅 {VIDEOS_PER_DAY} video(s)/day"
    )

    produce_video()  # Run immediately on start

    schedule.every().day.at("09:00").do(produce_video)   # 2PM PKT
    if VIDEOS_PER_DAY >= 2:
        schedule.every().day.at("15:00").do(produce_video)  # 8PM PKT
    if VIDEOS_PER_DAY >= 3:
        schedule.every().day.at("21:00").do(produce_video)  # 2AM PKT

    logger.info(f"Scheduler active: {VIDEOS_PER_DAY} video(s)/day")
    while True:
        schedule.run_pending()
        time.sleep(60)

if __name__ == "__main__":
    main()
