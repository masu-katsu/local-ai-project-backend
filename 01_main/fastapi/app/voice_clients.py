import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)

class VoiceInputClient:
    """Whisperクライアント"""
    
    def __init__(self, whisper_url: str = "http://whisper:8000"):
        self.whisper_url = whisper_url
        self.client = httpx.AsyncClient(timeout=60.0)
        logger.info(f"VoiceInputClient初期化: {whisper_url}")
    
    async def transcribe(
        self,
        audio_data: bytes,
        filename: str = "audio.wav"
    ) -> Optional[str]:
        """
        音声をテキストに変換
        
        Args:
            audio_data: 音声データ（bytes）
            filename: ファイル名
        
        Returns:
            変換されたテキスト
        """
        files = {
            "audio": (filename, audio_data, "audio/wav")
        }
        
        try:
            response = await self.client.post(
                f"{self.whisper_url}/transcribe",
                files=files
            )
            response.raise_for_status()
            
            data = response.json()
            text = data.get("text", "")
            
            logger.info(f"音声認識完了: {len(text)}文字")
            return text
            
        except Exception as e:
            logger.error(f"音声認識失敗: {e}")
            return None
    
    async def close(self):
        """クライアントをクローズ"""
        await self.client.aclose()

class VoiceOutputClient:
    """Piperクライアント"""
    
    def __init__(self, piper_url: str = "http://piper:8000"):
        self.piper_url = piper_url
        self.client = httpx.AsyncClient(timeout=60.0)
        logger.info(f"VoiceOutputClient初期化: {piper_url}")
    
    async def synthesize(
        self,
        text: str,
        voice: str = "ja_jp_pt_multispeaker"
    ) -> Optional[bytes]:
        """
        テキストを音声に変換
        
        Args:
            text: テキスト
            voice: 音声モデル名
        
        Returns:
            音声データ（bytes）
        """
        try:
            response = await self.client.post(
                f"{self.piper_url}/synthesize",
                json={"text": text, "voice": voice}
            )
            response.raise_for_status()
            
            data = response.json()
            # 実際の実装ではbase64デコードが必要
            audio_data = data.get("audio", "")
            
            logger.info(f"音声合成完了: {len(text)}文字")
            return audio_data.encode() if audio_data else None
            
        except Exception as e:
            logger.error(f"音声合成失敗: {e}")
            return None
    
    async def close(self):
        """クライアントをクローズ"""
        await self.client.aclose()
