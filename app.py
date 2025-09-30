from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx
import asyncio
import os

app = FastAPI()

# ✅ Allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with your frontend domain for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Suno API setup
API_KEY = os.getenv("SUNO_API_KEY")
SUNO_API_URL = "https://api.suno.ai/v1/generate_music"
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

    payload = {"prompt": request.prompt}
    timeout = httpx.Timeout(10.0, connect=5.0)
    retries = 3

    print(f"🎯 Prompt received: {request.prompt}")

    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(SUNO_API_URL, json=payload, headers=HEADERS)
                print(f"🔍 Status Code: {response.status_code}")
                print(f"🔍 Headers: {response.headers}")
                print("🔍 Raw Suno response:", response.text)

                if "text/html" in response.headers.get("content-type", "") or response.status_code != 200:
                    print(f"⚠️ Attempt {attempt+1}: Invalid response from Suno")
                    await asyncio.sleep(2)
                    continue

                try:
                    data = response.json()
                except Exception as e:
                    print(f"❌ JSON decode error: {e}")
                    await asyncio.sleep(2)
                    continue

                print("🧾 Parsed JSON:", data)
                music_url = data.get("audio_url")
                print(f"✅ Attempt {attempt+1}: Music URL → {music_url}")

                if not music_url:
                    return {
                        "music_url": None,
                        "error": "No audio URL returned. Try a different prompt or check API status."
                    }

                return {"music_url": music_url}
        except Exception as e:
            print(f"❌ Attempt {attempt+1}: Exception → {e}")
            await asyncio.sleep(2)

    # 🔁 Fallback response
    print("🔁 Suno unreachable. Returning fallback melody.")
    return {
        "music_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
        "message": "🎵 Suno is unreachable. Here's a sample melody instead!"
    }

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