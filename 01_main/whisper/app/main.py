from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
import logging
import os
import torch
import whisper
import io
import numpy as np

app = FastAPI(title="Whisper Voice Service")
logger = logging.getLogger(__name__)

# Whisperモデルのロード
MODEL_SIZE = os.getenv("WHISPER_MODEL_SIZE", "base")
model = None

@app.on_event("startup")
async def load_model():
    """Whisperモデルをロード"""
    global model
    try:
        logger.info(f"Whisperモデルをロード中: {MODEL_SIZE}")
        model = whisper.load_model(MODEL_SIZE, device="cpu")
        logger.info("Whisperモデルロード完了")
    except Exception as e:
        logger.error(f"Whisperモデルロード失敗: {e}")
        # モデルロード失敗時はフォールバック
        model = None

@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    """音声をテキストに変換"""
    if model is None:
        return {"text": "Whisperモデルがロードされていません", "error": "model_not_loaded"}
    
    try:
        # 音声データを読み込み
        content = await audio.read()
        logger.info(f"音声受信: {len(content)} bytes")
        
        # WAVファイルとして処理
        audio_file = io.BytesIO(content)
        
        # Whisperで音声認識
        result = model.transcribe(audio_file, language="ja", fp16=False)
        text = result["text"]
        
        logger.info(f"音声認識完了: {len(text)}文字")
        return {"text": text}
        
    except Exception as e:
        logger.error(f"音声認識失敗: {e}")
        return {"text": "", "error": str(e)}

@app.post("/transcribe/file")
async def transcribe_file(audio: UploadFile = File(...)):
    """音声ファイルをテキストに変換（ファイルパス経由）"""
    if model is None:
        return {"text": "Whisperモデルがロードされていません", "error": "model_not_loaded"}
    
    try:
        # 一時ファイルに保存
        temp_path = f"/tmp/{audio.filename}"
        with open(temp_path, "wb") as f:
            f.write(await audio.read())
        
        logger.info(f"音声ファイル受信: {audio.filename}")
        
        # Whisperで音声認識
        result = model.transcribe(temp_path, language="ja", fp16=False)
        text = result["text"]
        
        # 一時ファイルを削除
        os.remove(temp_path)
        
        logger.info(f"音声認識完了: {len(text)}文字")
        return {"text": text}
        
    except Exception as e:
        logger.error(f"音声認識失敗: {e}")
        return {"text": "", "error": str(e)}

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "whisper",
        "model_loaded": model is not None,
        "model_size": MODEL_SIZE
    }
