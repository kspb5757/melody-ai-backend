from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import asyncio
import os

app = FastAPI(
    title="Melody AI Backend",
    description="Generate music from prompts using Suno API",
    version="1.0.0"
)

# ✅ CORS for your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://melodyai.edgeone.app"],  # Replace with your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Suno API setup
API_KEY = os.getenv("SUNO_API_KEY")
SUNO_API_URL = "https://api.sunoapi.org/api/v1/generate"
HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}

class MusicRequest(BaseModel):
    prompt: str

@app.post("/generate_music")
async def generate_music(request: MusicRequest):
    if not request.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    payload = {
        "prompt": request.prompt,
        "title": "Melody AI Track",
        "customMode": True,
        "instrumental": True,
        "model": "V3_5",
        "callBackUrl": None  # ❌ No callback, we will poll manually
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(SUNO_API_URL, json=payload, headers=HEADERS)

        try:
            data = response.json()
        except Exception as e:
            print(f"❌ JSON decode error: {e}")
            raise HTTPException(status_code=500, detail="Failed to parse Suno response.")

    # ✅ Handle credit exhaustion
    if data.get("code") == 429:
        print("🚫 Suno credits exhausted.")
        return {
            "music_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
            "message": "🚫 Suno credits exhausted. Here's a sample melody instead!"
        }

    task_id = data.get("data", {}).get("id")
    if not task_id:
        raise HTTPException(status_code=500, detail="No task ID returned from Suno.")

    print(f"✅ Task ID received: {task_id}")

    # 🔄 Poll for result (wait until Suno returns audio_url)
    for _ in range(30):  # Try for up to ~30 seconds
        await asyncio.sleep(2)  # wait before polling
        poll_url = f"https://api.sunoapi.org/api/v1/status/{task_id}"
        poll_resp = await client.get(poll_url, headers=HEADERS)

        try:
            poll_data = poll_resp.json()
        except:
            continue

        audio_url = poll_data.get("data", {}).get("audio_url")
        if audio_url:
            print(f"🎶 Music ready: {audio_url}")
            return {"taskId": task_id, "music_url": audio_url}

    # ❌ Timeout – no music generated
    return {
        "taskId": task_id,
        "music_url": None,
        "message": "⏳ Music not ready yet. Try again later."
    }


@app.get("/")
def home():
    return {"message": "Backend is working!"}

@app.get("/health")
async def health_check():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(SUNO_API_URL, headers=HEADERS)
            status = "online" if response.status_code == 200 else "offline"
    except:
        status = "unreachable"
    print(f"🩺 Suno health check: {status}")
    return {"suno_status": status}
