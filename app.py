from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import asyncio
import os

music_store = {}

app = FastAPI(
    title="Melody AI Backend",
    description="Generate music from prompts using Suno API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://melodyai.edgeone.app"],  # ✅ Your frontend domain
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
        "callBackUrl": "https://melody-ai-backend.onrender.com/callback"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(SUNO_API_URL, json=payload, headers=HEADERS)

        # ✅ Validate response type
        if response.status_code != 200 or "application/json" not in response.headers.get("content-type", ""):
            print(f"❌ Invalid response from Suno: {response.status_code}")
            raise HTTPException(status_code=502, detail="Invalid response from Suno API.")

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
        print("❌ No task ID found in Suno response.")
        raise HTTPException(status_code=500, detail="No task ID returned from Suno.")

    print(f"✅ Task ID received: {task_id}")
    return {"taskId": task_id}

@app.post("/callback")
async def receive_music(data: dict):
    print("🎧 Callback received:", data)
    task_id = data.get("data", {}).get("id")
    music_url = data.get("data", {}).get("audio_url")
    if task_id and music_url:
        music_store[task_id] = music_url
        print(f"✅ Stored music for task {task_id}: {music_url}")
        return {"status": "stored", "taskId": task_id}
    print(f"⚠️ Missing taskId or music_url in callback.")
    return {"status": "error", "message": "Missing taskId or music_url"}

@app.get("/music/{task_id}")
def get_music(task_id: str):
    music_url = music_store.get(task_id)
    if music_url:
        return {"taskId": task_id, "music_url": music_url}
    else:
        return {"taskId": task_id, "music_url": None, "message": "Music not ready, try again later."}

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