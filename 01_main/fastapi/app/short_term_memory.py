import json
import redis
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class ShortTermMemory:
    """Redisを用いた短期記憶管理"""
    
    def __init__(self, redis_url: str = "redis://redis:6379"):
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        try:
            self.redis_client.ping()
            logger.info("Redis接続成功")
        except Exception as e:
            logger.error(f"Redis接続失敗: {e}")
            self.redis_client = None
    
    def update_state(
        self,
        user_id: str,
        current_topic: Optional[str] = None,
        emotion: Optional[str] = None,
        recent_messages: Optional[List[str]] = None,
        active_task: Optional[str] = None
    ) -> bool:
        """ユーザー状態を更新"""
        if not self.redis_client:
            return False
        
        key = f"user:{user_id}:state"
        
        # 既存の状態を取得
        existing = self.redis_client.hgetall(key) or {}
        
        # 更新
        if current_topic is not None:
            self.redis_client.hset(key, "current_topic", current_topic)
        if emotion is not None:
            self.redis_client.hset(key, "emotion", emotion)
        if recent_messages is not None:
            self.redis_client.hset(key, "recent_messages", json.dumps(recent_messages))
        if active_task is not None:
            self.redis_client.hset(key, "active_task", active_task)
        
        # 最終アクティビティ更新
        self.redis_client.hset(key, "last_activity", datetime.now().isoformat())
        
        # TTL設定（24時間）
        self.redis_client.expire(key, 86400)
        
        logger.info(f"状態更新: {user_id}")
        return True
    
    def get_state(self, user_id: str) -> Dict[str, Any]:
        """ユーザー状態を取得"""
        if not self.redis_client:
            return {}
        
        key = f"user:{user_id}:state"
        data = self.redis_client.hgetall(key)
        
        if not data:
            return {}
        
        # JSONフィールドをパース
        if "recent_messages" in data:
            data["recent_messages"] = json.loads(data["recent_messages"])
        
        return data
    
    def add_recent_message(self, user_id: str, message: str, max_count: int = 10) -> bool:
        """直近メッセージを追加"""
        state = self.get_state(user_id)
        recent = state.get("recent_messages", [])
        
        recent.append(message)
        if len(recent) > max_count:
            recent = recent[-max_count:]
        
        return self.update_state(user_id, recent_messages=recent)
    
    def update_session(self, user_id: str, increment_count: bool = True) -> bool:
        """セッション情報を更新"""
        if not self.redis_client:
            return False
        
        key = f"user:{user_id}:session"
        
        # 初回のみ開始時刻を設定
        if not self.redis_client.exists(key):
            self.redis_client.hset(key, "start_time", datetime.now().isoformat())
            self.redis_client.hset(key, "message_count", "0")
        
        # メッセージ数増加
        if increment_count:
            count = int(self.redis_client.hget(key, "message_count") or "0")
            self.redis_client.hset(key, "message_count", str(count + 1))
        
        self.redis_client.expire(key, 86400)
        return True
    
    def get_session(self, user_id: str) -> Dict[str, Any]:
        """セッション情報を取得"""
        if not self.redis_client:
            return {}
        
        key = f"user:{user_id}:session"
        return self.redis_client.hgetall(key)
    
    def set_cache(self, key: str, value: str, ttl: int = 3600) -> bool:
        """キャッシュを設定"""
        if not self.redis_client:
            return False
        
        cache_key = f"cache:{key}:response"
        self.redis_client.setex(cache_key, ttl, value)
        return True
    
    def get_cache(self, key: str) -> Optional[str]:
        """キャッシュを取得"""
        if not self.redis_client:
            return None
        
        cache_key = f"cache:{key}:response"
        return self.redis_client.get(cache_key)
    
    def clear_user_data(self, user_id: str) -> bool:
        """ユーザーデータを削除"""
        if not self.redis_client:
            return False
        
        pattern = f"user:{user_id}:*"
        keys = self.redis_client.keys(pattern)
        
        if keys:
            self.redis_client.delete(*keys)
            logger.info(f"ユーザーデータ削除: {user_id} ({len(keys)} keys)")
        
        return True
