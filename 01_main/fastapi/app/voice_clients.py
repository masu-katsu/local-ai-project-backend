import logging
from typing import Optional
import httpx
import io
import wave
import struct

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
        音声をテキストに変換（音声データ処理改善）
        
        Args:
            audio_data: 音声データ（bytes）
            filename: ファイル名
        
        Returns:
            変換されたテキスト
        """
        try:
            # 音声データの検証と前処理
            processed_audio = self._validate_and_preprocess_audio(audio_data)
            
            files = {
                "audio": (filename, processed_audio, "audio/wav")
            }
            
            response = await self.client.post(
                f"{self.whisper_url}/transcribe",
                files=files
            )
            response.raise_for_status()
            
            data = response.json()
            text = data.get("text", "")
            
            # テキストの後処理
            text = self._postprocess_text(text)
            
            logger.info(f"音声認識完了: {len(text)}文字")
            return text
            
        except Exception as e:
            logger.error(f"音声認識失敗: {e}")
            return None
    
    def _validate_and_preprocess_audio(self, audio_data: bytes) -> bytes:
        """音声データの検証と前処理"""
        try:
            # WAVヘッダーの検証
            if len(audio_data) < 44:
                logger.warning("音声データが短すぎます")
                return audio_data
            
            # WAVファイルか確認
            if audio_data[:4] != b'RIFF':
                logger.warning("WAVフォーマットではありません")
                return audio_data
            
            return audio_data
        except Exception as e:
            logger.warning(f"音声データ検証失敗: {e}")
            return audio_data
    
    def _postprocess_text(self, text: str) -> str:
        """テキストの後処理"""
        if not text:
            return text
        
        # 余分な空白を削除
        text = ' '.join(text.split())
        
        # 先頭・末尾の空白を削除
        text = text.strip()
        
        return text
    
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
        テキストを音声に変換（音声データ処理改善）
        
        Args:
            text: テキスト
            voice: 音声モデル名
        
        Returns:
            音声データ（bytes）
        """
        try:
            # テキストの前処理
            processed_text = self._preprocess_text(text)
            
            response = await self.client.post(
                f"{self.piper_url}/synthesize",
                json={"text": processed_text, "voice": voice}
            )
            response.raise_for_status()
            
            data = response.json()
            # base64デコード
            audio_base64 = data.get("audio", "")
            if audio_base64:
                import base64
                audio_data = base64.b64decode(audio_base64)
                
                # 音声データの検証
                if self._validate_audio_data(audio_data):
                    logger.info(f"音声合成完了: {len(text)}文字, {len(audio_data)} bytes")
                    return audio_data
                else:
                    logger.warning("音声データが無効です")
                    return None
            else:
                logger.warning("音声データが空です")
                return None
            
        except Exception as e:
            logger.error(f"音声合成失敗: {e}")
            return None
    
    def _preprocess_text(self, text: str) -> str:
        """テキストの前処理"""
        if not text:
            return text
        
        # テキスト長の制限（Piperの制限に合わせる）
        max_length = 500
        if len(text) > max_length:
            text = text[:max_length]
            logger.warning(f"テキストを{max_length}文字に切り詰めました")
        
        # 特殊文字の処理
        text = text.replace('\n', ' ')
        text = text.replace('\r', ' ')
        
        return text.strip()
    
    def _validate_audio_data(self, audio_data: bytes) -> bool:
        """音声データの検証"""
        if not audio_data:
            return False
        
        # 最小サイズチェック
        if len(audio_data) < 100:
            return False
        
        # WAVヘッダーチェック（簡易）
        if audio_data[:4] == b'RIFF':
            return True
        
        return True
    
    async def close(self):
        """クライアントをクローズ"""
        await self.client.aclose()
