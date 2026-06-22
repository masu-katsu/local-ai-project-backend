import logging
from typing import Dict, Any, Optional
from datetime import datetime
import json
import httpx
import os
import re

logger = logging.getLogger(__name__)

class EmotionManager:
    """感情管理システム"""
    
    def __init__(self, phi3_url: str = None):
        self.emotion_history: Dict[str, list] = {}
        self.phi3_url = phi3_url or os.getenv("PHI3_URL", "http://phi3:8001")
        self.client = httpx.AsyncClient(timeout=30.0)
        logger.info(f"EmotionManager初期化: LLMベース感情検出有効 ({self.phi3_url})")
    
    async def detect_emotion(
        self,
        message: str,
        current_emotion: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        メッセージから感情を検出（LLMベース）
        
        Returns:
            emotion: {"mood": str, "energy": int, "confidence": float}
        """
        try:
            # LLMを使用して感情を分析
            prompt = f"""
以下のメッセージから感情を分析してください。JSON形式で出力してください。

メッセージ: {message}

出力形式:
{{
  "mood": "happy|sad|excited|curious|neutral|angry|anxious",
  "energy": 0-100の整数,
  "confidence": 0.0-1.0の小数,
  "reason": "感情判断の理由"
}}

感情カテゴリ:
- happy: 喜び、感謝、満足
- sad: 悲しみ、失望、後悔
- excited: 興奮、期待、興味
- curious: 好奇心、疑問、探求
- neutral: 中立、平穏
- angry: 怒り、不満
- anxious: 不安、心配
"""
            
            response = await self.client.post(
                f"{self.phi3_url}/generate",
                json={
                    "prompt": prompt,
                    "max_tokens": 256,
                    "temperature": 0.3
                }
            )
            response.raise_for_status()
            data = response.json()
            llm_response = data.get("response", "")
            
            # JSONをパース
            emotion_data = self._parse_emotion_response(llm_response)
            
            if emotion_data:
                logger.info(f"LLM感情検出: {emotion_data['mood']} (energy={emotion_data['energy']}, confidence={emotion_data['confidence']})")
                return {
                    "mood": emotion_data["mood"],
                    "energy": emotion_data["energy"],
                    "confidence": emotion_data["confidence"],
                    "reason": emotion_data.get("reason", ""),
                    "timestamp": datetime.now().isoformat()
                }
            
        except Exception as e:
            logger.warning(f"LLM感情検出失敗、フォールバック使用: {e}")
        
        # フォールバック: キーワードベース
        return self._fallback_emotion_detection(message)
    
    def _parse_emotion_response(self, llm_response: str) -> Optional[Dict[str, Any]]:
        """LLMレスポンスから感情データをパース"""
        try:
            # JSON部分を抽出
            json_match = re.search(r'\{[\s\S]*\}', llm_response)
            if json_match:
                data = json.loads(json_match.group())
                
                # バリデーション
                valid_moods = ["happy", "sad", "excited", "curious", "neutral", "angry", "anxious"]
                mood = data.get("mood", "neutral")
                if mood not in valid_moods:
                    mood = "neutral"
                
                energy = int(data.get("energy", 50))
                energy = max(0, min(100, energy))  # 0-100の範囲に制限
                
                confidence = float(data.get("confidence", 0.7))
                confidence = max(0.0, min(1.0, confidence))  # 0.0-1.0の範囲に制限
                
                return {
                    "mood": mood,
                    "energy": energy,
                    "confidence": confidence,
                    "reason": data.get("reason", "")
                }
        except Exception as e:
            logger.warning(f"感情レスポンスパース失敗: {e}")
        
        return None
    
    def _fallback_emotion_detection(self, message: str) -> Dict[str, Any]:
        """フォールバック: キーワードベース感情検出"""
        message_lower = message.lower()
        
        mood = "neutral"
        energy = 50
        confidence = 0.5
        
        # ポジティブキーワード
        positive_words = ["ありがとう", "すごい", "嬉しい", "楽しい", "良い", "よかった"]
        if any(word in message for word in positive_words):
            mood = "happy"
            energy = 70
            confidence = 0.6
        
        # ネガティブキーワード
        negative_words = ["残念", "悲しい", "怒り", "嫌", "ダメ", "失敗"]
        if any(word in message for word in negative_words):
            mood = "sad"
            energy = 30
            confidence = 0.6
        
        # 興味・興奮
        excited_words = ["面白い", "ワクワク", "興味", "知りたい"]
        if any(word in message for word in excited_words):
            mood = "excited"
            energy = 85
            confidence = 0.6
        
        # 疑問・思考
        question_words = ["?", "？", "どうして", "なぜ", "教えて"]
        if any(word in message for word in question_words):
            mood = "curious"
            energy = 60
            confidence = 0.5
        
        logger.info(f"フォールバック感情検出: {mood} (energy={energy}, confidence={confidence})")
        
        return {
            "mood": mood,
            "energy": energy,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat()
        }
    
    def update_emotion(
        self,
        user_id: str,
        new_emotion: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        感情を更新（履歴を考慮）
        """
        if user_id not in self.emotion_history:
            self.emotion_history[user_id] = []
        
        # 履歴に追加
        self.emotion_history[user_id].append(new_emotion)
        
        # 履歴を最大100件に制限
        if len(self.emotion_history[user_id]) > 100:
            self.emotion_history[user_id] = self.emotion_history[user_id][-100:]
        
        # 平均感情を計算
        avg_mood = self._calculate_average_mood(user_id)
        avg_energy = self._calculate_average_energy(user_id)
        
        return {
            "current_mood": new_emotion["mood"],
            "current_energy": new_emotion["energy"],
            "average_mood": avg_mood,
            "average_energy": avg_energy,
            "history_count": len(self.emotion_history[user_id])
        }
    
    def _calculate_average_mood(self, user_id: str) -> str:
        """平均ムードを計算"""
        if not self.emotion_history.get(user_id):
            return "neutral"
        
        mood_counts = {}
        for emotion in self.emotion_history[user_id]:
            mood = emotion["mood"]
            mood_counts[mood] = mood_counts.get(mood, 0) + 1
        
        # 最頻ムードを返す
        return max(mood_counts, key=mood_counts.get)
    
    def _calculate_average_energy(self, user_id: str) -> int:
        """平均エネルギーを計算"""
        if not self.emotion_history.get(user_id):
            return 50
        
        energies = [e["energy"] for e in self.emotion_history[user_id]]
        return sum(energies) // len(energies)
    
    def get_unity_animation_params(
        self,
        emotion: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        感情に対応するUnityアニメーションパラメータを生成
        
        Returns:
            {"animation": str, "speed": float, "intensity": float}
        """
        mood = emotion.get("mood", "neutral")
        energy = emotion.get("energy", 50)
        
        animation_map = {
            "happy": {"animation": "smile", "speed": 1.0, "intensity": 0.8},
            "sad": {"animation": "sad", "speed": 0.7, "intensity": 0.6},
            "excited": {"animation": "excited", "speed": 1.5, "intensity": 0.9},
            "curious": {"animation": "thinking", "speed": 1.0, "intensity": 0.5},
            "neutral": {"animation": "idle", "speed": 0.5, "intensity": 0.3},
        }
        
        params = animation_map.get(mood, animation_map["neutral"])
        
        # エネルギーに応じて調整
        params["speed"] *= (energy / 50.0)
        params["intensity"] *= (energy / 50.0)
        
        return params
    
    def get_emotion_history(
        self,
        user_id: str,
        limit: int = 10
    ) -> list:
        """感情履歴を取得"""
        if user_id not in self.emotion_history:
            return []
        
        return self.emotion_history[user_id][-limit:]
