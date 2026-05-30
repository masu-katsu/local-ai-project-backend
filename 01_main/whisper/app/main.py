from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
import logging

app = FastAPI(title="Whisper Voice Service")
logger = logging.getLogger(__name__)

@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """音声をテキストに変換"""
    # 簡易実装（実際はWhisperモデルを使用）
    content = await audio.read()
    logger.info(f"音声受信: {len(content)} bytes")
    
    # 簡易実装 - 実際のWhisper推論をここに実装
    text = "音声認識結果（簡易実装）"
    
    return {"text": text}

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "whisper"}
