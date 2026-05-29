# Phase1 詳細設計: 基礎記憶層の強化

## 概要

Phase1では、短期記憶（Redis）と記憶整理システム（Mem0）を導入し、会話要約機能を実装する。

**目的**:
- 現在の会話状態を保持する（短期記憶）
- 重要な情報だけを自動保存する（記憶整理）
- 会話を要約して記憶を整理する（会話要約）

---

## コンポーネント詳細

### 1. Redis（短期記憶）

#### 役割
- 現在の会話状態を保持
- 一時的な状態管理
- 高速なキー値ストア

#### データ構造

```python
# ユーザー状態
Key: user:{user_id}:state
Type: Hash
Fields:
  - current_topic: str        # 現在のトピック
  - emotion: str              # 現在の感情
  - recent_messages: list     # 直近のメッセージ（JSON）
  - active_task: str|None     # アクティブなタスクID
  - last_activity: timestamp  # 最終アクティビティ時刻

# セッション情報
Key: user:{user_id}:session
Type: Hash
Fields:
  - start_time: timestamp     # セッション開始時刻
  - message_count: int        # メッセージ数
  - topic_history: list       # トピック履歴

# 会話コンテキスト（一時）
Key: user:{user_id}:context
Type: String (JSON)
Value:
  {
    "last_n_messages": [...],  # 直近Nメッセージ
    "current_intent": "...",  # 現在のIntent
    "pending_queries": [...]   # 保留中のクエリ
  }

# キャッシュ
Key: cache:{hash}:response
Type: String
TTL: 3600 (1時間)
```

#### 実装

```python
# app/short_term_memory.py

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
```

#### Docker設定

```yaml
# docker-compose.ymlに追加

redis:
  image: redis:7-alpine
  container_name: ai-redis
  ports:
    - "6379:6379"
  volumes:
    - ../02_logs/redis_data:/data
  networks:
    - backend
  restart: unless-stopped
  command: redis-server --appendonly yes
```

---

### 2. Mem0（記憶整理システム）

#### 役割
- 重要情報の自動抽出
- 会話要約
- 優先順位付け
- 長期記憶の整理

#### データ構造

```python
# Mem0に保存する記憶構造
{
  "memory_id": "mem_001",
  "content": "ユーザーはUnityでAI開発中",
  "importance": 0.8,           # 重要度（0-1）
  "category": "project",       # カテゴリ
  "user_id": "player_123",
  "timestamp": "2026-05-27T20:00:00",
  "source": "conversation",    # ソース
  "related_memories": ["mem_002", "mem_003"],
  "access_count": 5,           # アクセス回数
  "last_accessed": "2026-05-27T21:00:00"
}
```

#### 実装

```python
# app/memory_organizer.py

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class MemoryOrganizer:
    """Mem0を用いた記憶整理システム"""
    
    def __init__(self, mem0_url: str = "http://mem0:8080"):
        self.mem0_url = mem0_url
        # Mem0クライアントの初期化
        # 注: 実際のMem0 APIに合わせて調整
        logger.info("MemoryOrganizer初期化完了")
    
    async def extract_important_info(
        self,
        conversation: str,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        会話から重要情報を抽出
        
        Args:
            conversation: 会話テキスト
            user_id: ユーザーID
        
        Returns:
            抽出された重要情報のリスト
        """
        # LLMを用いて重要情報を抽出
        # 実装はPhase2のLangGraphと統合
        important_points = []
        
        # 簡易実装（実際はLLMを使用）
        if "Unity" in conversation:
            important_points.append({
                "content": "ユーザーはUnityで開発中",
                "importance": 0.8,
                "category": "project"
            })
        
        return important_points
    
    async def save_memory(
        self,
        content: str,
        user_id: str,
        importance: float = 0.5,
        category: str = "general"
    ) -> str:
        """
        記憶を保存
        
        Returns:
            memory_id
        """
        memory_id = f"mem_{datetime.now().timestamp()}"
        
        memory = {
            "memory_id": memory_id,
            "content": content,
            "importance": importance,
            "category": category,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "source": "conversation",
            "access_count": 0,
            "last_accessed": datetime.now().isoformat()
        }
        
        # Mem0 APIに保存
        # 実装はMem0のAPI仕様に合わせて調整
        
        logger.info(f"記憶保存: {memory_id} - {content[:50]}")
        return memory_id
    
    async def search_memories(
        self,
        query: str,
        user_id: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        記憶を検索
        
        Returns:
            関連記憶のリスト
        """
        # Mem0 APIで検索
        # 実装はMem0のAPI仕様に合わせて調整
        
        # 簡易実装
        return []
    
    async def update_importance(
        self,
        memory_id: str,
        delta: float = 0.1
    ) -> bool:
        """
        重要度を更新
        """
        # Mem0 APIで更新
        return True
    
    async def get_user_memories(
        self,
        user_id: str,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        ユーザーの記憶を取得
        """
        # Mem0 APIで取得
        return []
```

#### Mem0サービス実装

```python
# mem0/app/main.py

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
import logging

app = FastAPI(title="Mem0 Memory Service")
logger = logging.getLogger(__name__)

class Memory(BaseModel):
    memory_id: str
    content: str
    importance: float
    category: str
    user_id: str
    timestamp: str
    source: str
    access_count: int
    last_accessed: str

# インメモリストレージ（実際はDBを使用）
memories: List[Memory] = []

@app.post("/memories")
async def create_memory(memory: Memory) -> dict:
    memories.append(memory)
    logger.info(f"記憶作成: {memory.memory_id}")
    return {"status": "created", "memory_id": memory.memory_id}

@app.get("/memories/{user_id}")
async def get_memories(user_id: str, category: Optional[str] = None) -> List[Memory]:
    user_memories = [m for m in memories if m.user_id == user_id]
    if category:
        user_memories = [m for m in user_memories if m.category == category]
    return user_memories

@app.get("/memories/search/{user_id}")
async def search_memories(user_id: str, query: str, top_k: int = 5) -> List[Memory]:
    # 簡易検索（実際はベクトル検索）
    user_memories = [m for m in memories if m.user_id == user_id]
    results = [m for m in user_memories if query.lower() in m.content.lower()]
    return results[:top_k]

@app.put("/memories/{memory_id}/importance")
async def update_importance(memory_id: str, delta: float = 0.1) -> dict:
    for memory in memories:
        if memory.memory_id == memory_id:
            memory.importance = min(1.0, max(0.0, memory.importance + delta))
            memory.access_count += 1
            return {"status": "updated", "importance": memory.importance}
    return {"status": "not_found"}
```

#### Mem0 Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

#### Mem0 requirements.txt

```
fastapi==0.115.0
uvicorn==0.30.0
pydantic==2.9.0
```

---

### 3. 会話要約

#### 役割
- 長い会話を要約
- 重要ポイントの抽出
- 記憶の整理

#### 実装

```python
# app/conversation_summarizer.py

import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ConversationSummarizer:
    """会話要約機能"""
    
    def __init__(self, ai_router):
        self.ai_router = ai_router
    
    async def summarize_conversation(
        self,
        messages: list[dict],
        user_id: str,
        max_length: int = 500
    ) -> str:
        """
        会話を要約
        
        Args:
            messages: メッセージリスト [{user_message, ai_response}, ...]
            user_id: ユーザーID
            max_length: 要約の最大長
        
        Returns:
            要約テキスト
        """
        if not messages:
            return ""
        
        # 会話テキストを構築
        conversation_text = "\n".join([
            f"User: {m['user_message']}\nAI: {m['ai_response']}"
            for m in messages
        ])
        
        # LLMで要約
        summary_prompt = (
            "以下の会話を日本語で要約してください。"
            f"重要なポイントを箇条書きでまとめてください。"
            f"最大{max_length}文字以内で。\n\n"
            f"{conversation_text}"
        )
        
        try:
            summary = await self.ai_router.send_to_ai(
                model="qwen",
                message=summary_prompt,
                context=[]
            )
            logger.info(f"会話要約完了: {user_id}")
            return summary
        except Exception as e:
            logger.error(f"会話要約失敗: {e}")
            return ""
    
    async def extract_key_points(
        self,
        messages: list[dict],
        user_id: str
    ) -> list[str]:
        """
        重要ポイントを抽出
        """
        if not messages:
            return []
        
        conversation_text = "\n".join([
            f"User: {m['user_message']}\nAI: {m['ai_response']}"
            for m in messages
        ])
        
        extract_prompt = (
            "以下の会話から重要なポイントを3-5個抽出してください。"
            "それぞれ1行で簡潔に記述してください。\n\n"
            f"{conversation_text}"
        )
        
        try:
            response = await self.ai_router.send_to_ai(
                model="qwen",
                message=extract_prompt,
                context=[]
            )
            
            # 箇条書きをパース
            key_points = [
                line.strip().lstrip("-•*").strip()
                for line in response.split("\n")
                if line.strip()
            ]
            
            logger.info(f"重要ポイント抽出: {user_id} - {len(key_points)}件")
            return key_points
        except Exception as e:
            logger.error(f"重要ポイント抽出失敗: {e}")
            return []
    
    async def should_summarize(
        self,
        message_count: int,
        last_summary_time: Optional[datetime] = None
    ) -> bool:
        """
        要約が必要か判断
        
        条件:
        - メッセージ数が10件以上
        - 前回の要約から1時間以上経過
        """
        if message_count >= 10:
            return True
        
        if last_summary_time:
            elapsed = (datetime.now() - last_summary_time).total_seconds()
            if elapsed >= 3600:  # 1時間
                return True
        
        return False
```

---

## FastAPIへの統合

### main.pyの更新

```python
# app/main.pyに追加

from app.short_term_memory import ShortTermMemory
from app.memory_organizer import MemoryOrganizer
from app.conversation_summarizer import ConversationSummarizer

# 環境変数追加
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
MEM0_URL = os.getenv("MEM0_URL", "http://mem0:8080")

# 初期化
short_term_memory = ShortTermMemory(redis_url=REDIS_URL)
memory_organizer = MemoryOrganizer(mem0_url=MEM0_URL)
conversation_summarizer = ConversationSummarizer(ai_router=ai_router)

# startupイベントで初期化確認
@app.on_event("startup")
async def startup_event():
    # 既存の初期化...
    
    # Redis接続確認
    if short_term_memory.redis_client:
        logger.info("  Redis: 接続済み")
    else:
        logger.warning("  Redis: 未接続")
    
    # Mem0接続確認
    logger.info("  Mem0: 初期化完了")
```

### chatエンドポイントの更新

```python
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    start_time = time.time()
    user_id = request.user_id
    
    # =========================================
    # Step 0: 短期記憶の更新
    # =========================================
    short_term_memory.add_recent_message(user_id, request.message)
    short_term_memory.update_session(user_id, increment_count=True)
    
    # 現在の状態を取得
    current_state = short_term_memory.get_state(user_id)
    logger.info(f"[{user_id}] 現在の状態: {current_state}")
    
    # =========================================
    # Step 1: 会話要約判定
    # =========================================
    session = short_term_memory.get_session(user_id)
    message_count = int(session.get("message_count", 0))
    
    if await conversation_summarizer.should_summarize(message_count):
        logger.info(f"[{user_id}] 会話要約を実行")
        history = conversation_history.get_recent(user_id, limit=20)
        summary = await conversation_summarizer.summarize_conversation(
            history, user_id
        )
        
        # 要約をMem0に保存
        if summary:
            await memory_organizer.save_memory(
                content=summary,
                user_id=user_id,
                importance=0.7,
                category="summary"
            )
        
        # 重要ポイントを抽出して保存
        key_points = await conversation_summarizer.extract_key_points(
            history, user_id
        )
        for point in key_points:
            await memory_organizer.save_memory(
                content=point,
                user_id=user_id,
                importance=0.8,
                category="key_point"
            )
    
    # =========================================
    # Step 2: 重要情報の抽出と保存
    # =========================================
    important_info = await memory_organizer.extract_important_info(
        request.message, user_id
    )
    for info in important_info:
        await memory_organizer.save_memory(
            content=info["content"],
            user_id=user_id,
            importance=info["importance"],
            category=info["category"]
        )
    
    # =========================================
    # Step 3: 既存のフロー（Web検索、Intent分類など）
    # =========================================
    # ... 既存のコード ...
    
    # =========================================
    # Step 4: 応答後に状態更新
    # =========================================
    # トピックを推定（簡易）
    if "Unity" in request.message:
        topic = "Unity"
    elif "コード" in request.message or "プログラム" in request.message:
        topic = "プログラミング"
    else:
        topic = current_state.get("current_topic", "general")
    
    short_term_memory.update_state(
        user_id,
        current_topic=topic,
        emotion="thinking"  # 簡易設定
    )
    
    # ... 既存のレスポンス返送 ...
```

---

## 新規APIエンドポイント

```python
# 短期記憶関連
@app.get("/api/memory/state")
async def get_memory_state(user_id: str = "default_user"):
    """短期記憶の状態を取得"""
    state = short_term_memory.get_state(user_id)
    return {"user_id": user_id, "state": state}

@app.post("/api/memory/state")
async def update_memory_state(
    user_id: str = "default_user",
    current_topic: Optional[str] = None,
    emotion: Optional[str] = None,
    active_task: Optional[str] = None
):
    """短期記憶の状態を更新"""
    success = short_term_memory.update_state(
        user_id,
        current_topic=current_topic,
        emotion=emotion,
        active_task=active_task
    )
    return {"status": "updated" if success else "failed"}

@app.delete("/api/memory/state")
async def clear_memory_state(user_id: str = "default_user"):
    """短期記憶をクリア"""
    success = short_term_memory.clear_user_data(user_id)
    return {"status": "cleared" if success else "failed"}

# Mem0関連
@app.get("/api/memory/important")
async def get_important_memories(
    user_id: str = "default_user",
    category: Optional[str] = None
):
    """重要記憶を取得"""
    memories = await memory_organizer.get_user_memories(user_id, category)
    return {"user_id": user_id, "memories": memories}

@app.post("/api/memory/summarize")
async def trigger_summarization(user_id: str = "default_user"):
    """会話要約を手動実行"""
    history = conversation_history.get_recent(user_id, limit=20)
    summary = await conversation_summarizer.summarize_conversation(history, user_id)
    
    if summary:
        await memory_organizer.save_memory(
            content=summary,
            user_id=user_id,
            importance=0.7,
            category="summary"
        )
    
    return {"status": "summarized", "summary": summary}
```

---

## テスト計画

### ユニットテスト

```python
# tests/test_short_term_memory.py

import pytest
from app.short_term_memory import ShortTermMemory

def test_update_state():
    memory = ShortTermMemory("redis://localhost:6379")
    success = memory.update_state(
        "test_user",
        current_topic="test",
        emotion="happy"
    )
    assert success == True
    
    state = memory.get_state("test_user")
    assert state["current_topic"] == "test"
    assert state["emotion"] == "happy"

def test_add_recent_message():
    memory = ShortTermMemory("redis://localhost:6379")
    memory.add_recent_message("test_user", "message1")
    memory.add_recent_message("test_user", "message2")
    
    state = memory.get_state("test_user")
    assert len(state["recent_messages"]) == 2
    assert state["recent_messages"][-1] == "message2"
```

### 統合テスト

```python
# tests/test_phase1_integration.py

import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_chat_with_memory():
    async with AsyncClient(base_url="http://localhost:8000") as client:
        # チャット送信
        response = await client.post(
            "/api/chat",
            json={"message": "Unityでゲームを作っています", "user_id": "test_user"},
            headers={"X-API-Key": "test-key"}
        )
        
        assert response.status_code == 200
        
        # 状態確認
        state_response = await client.get(
            "/api/memory/state?user_id=test_user",
            headers={"X-API-Key": "test-key"}
        )
        
        state = state_response.json()["state"]
        assert state["current_topic"] == "Unity"
```

---

## デプロイ手順

### 1. Redisコンテナ追加

```bash
cd 01_main
# docker-compose.ymlにredisサービスを追加
docker-compose up -d redis
```

### 2. Mem0サービス構築

```bash
mkdir -p mem0/app
# Dockerfile, requirements.txt, main.pyを作成
docker-compose build mem0
docker-compose up -d mem0
```

### 3. FastAPI更新

```bash
cd fastapi
# requirements.txtにredis, mem0aiを追加
pip install -r requirements.txt

# 新規モジュールを作成
# app/short_term_memory.py
# app/memory_organizer.py
# app/conversation_summarizer.py

# main.pyを更新
```

### 4. 環境変数設定

```bash
# .envに追加
REDIS_URL=redis://redis:6379
MEM0_URL=http://mem0:8080
```

### 5. 再起動

```bash
docker-compose up -d fastapi
```

---

## 依存関係

```
Phase1コンポーネントの依存関係:

Redis (独立)
  └─ ShortTermMemory

Mem0 (独立)
  └─ MemoryOrganizer

ConversationSummarizer
  └─ AIRouter (既存)

FastAPI main.py
  ├─ ShortTermMemory
  ├─ MemoryOrganizer
  └─ ConversationSummarizer
```

---

## 次のステップ

Phase1完了後、以下を確認:
- Redisが正常に動作しているか
- Mem0が記憶を保存できているか
- 会話要約が正しく機能しているか
- FastAPIとの統合が完了しているか

確認後、Phase2（LangGraph, Emotion System）へ進む。
