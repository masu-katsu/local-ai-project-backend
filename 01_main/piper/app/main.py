from fastapi import FastAPI
from pydantic import BaseModel
import logging
import os
import base64
import io
import subprocess
import tempfile

app = FastAPI(title="Piper Voice Service")
logger = logging.getLogger(__name__)

class TTSRequest(BaseModel):
    text: str
    voice: str = "ja_jp_pt_multispeaker"
    speed: float = 1.0

# Piperモデルパス
MODEL_PATH = os.getenv("PIPER_MODEL_PATH", "/models/piper")
VOICE_MODEL = os.getenv("PIPER_VOICE_MODEL", "ja_jp_pt_multispeaker.onnx")

@app.post("/synthesize")
async def synthesize(request: TTSRequest):
    """テキストを音声に変換"""
    logger.info(f"音声合成: {request.text[:50]}...")
    
    try:
        # 一時ファイルを作成
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as text_file:
            text_file.write(request.text)
            text_path = text_file.name
        
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as audio_file:
            audio_path = audio_file.name
        
        # Piperコマンドを実行
        model_path = os.path.join(MODEL_PATH, VOICE_MODEL)
        config_path = model_path.replace('.onnx', '.onnx.json')
        
        cmd = [
            'piper',
            '--model', model_path,
            '--config', config_path,
            '--output_file', audio_path,
            '--text', request.text
        ]
        
        if request.speed != 1.0:
            cmd.extend(['--length_scale', str(1.0 / request.speed)])
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            logger.error(f"Piper実行失敗: {result.stderr}")
            return {"audio": "", "error": result.stderr}
        
        # 音声ファイルを読み込んでbase64エンコード
        with open(audio_path, 'rb') as f:
            audio_data = f.read()
        
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        # 一時ファイルを削除
        os.remove(text_path)
        os.remove(audio_path)
        
        logger.info(f"音声合成完了: {len(audio_data)} bytes")
        return {
            "audio": audio_base64,
            "length": len(audio_data),
            "format": "wav"
        }
        
    except subprocess.TimeoutExpired:
        logger.error("音声合成タイムアウト")
        return {"audio": "", "error": "timeout"}
    except Exception as e:
        logger.error(f"音声合成失敗: {e}")
        return {"audio": "", "error": str(e)}

@app.get("/voices")
async def list_voices():
    """利用可能な音声モデル一覧を取得"""
    try:
        voices = []
        if os.path.exists(MODEL_PATH):
            for file in os.listdir(MODEL_PATH):
                if file.endswith('.onnx'):
                    voices.append({
                        "name": file.replace('.onnx', ''),
                        "model": file
                    })
        return {"voices": voices}
    except Exception as e:
        logger.error(f"音声一覧取得失敗: {e}")
        return {"voices": [], "error": str(e)}

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "piper",
        "model_path": MODEL_PATH,
        "voice_model": VOICE_MODEL,
        "model_exists": os.path.exists(os.path.join(MODEL_PATH, VOICE_MODEL))
    }
