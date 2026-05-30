from fastapi import FastAPI
from pydantic import BaseModel
import logging

app = FastAPI(title="Piper Voice Service")
logger = logging.getLogger(__name__)

class TTSRequest(BaseModel):
    text: str
    voice: str = "ja_jp_pt_multispeaker"

@app.post("/synthesize")
async def synthesize(request: TTSRequest):
    """テキストを音声に変換"""
    logger.info(f"音声合成: {request.text[:50]}")
    
    # 簡易実装 - 実際のPiper推論をここに実装
    # 音声データを返す
    audio_data = b"simulated_audio_data"
    
    return {"audio": "base64_encoded_audio", "length": len(audio_data)}

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "piper"}
