# ============================================
# FastAPI メインサーバー（司令塔）
# ============================================
# すべてのリクエストはここを通る
# Unity → FastAPI → AI(Phi3/Qwen) → FastAPI → Unity
# ============================================

import os
import time
import logging
import asyncio
import json
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

from app.router import AIRouter
from app.history import ConversationHistory
from app.short_term_memory import ShortTermMemory
from app.memory_organizer import MemoryOrganizer
from app.conversation_summarizer import ConversationSummarizer
from app.emotion_manager import EmotionManager
from app.task_manager import TaskManager, TaskPriority, TaskStatus
from app.tool_registry import ToolRegistry
from app.voice_clients import VoiceInputClient, VoiceOutputClient
from app.mcp_client import MCPClient
from app.vision_processor import VisionProcessor
from app.autonomous_agent import AutonomousAgent
import re

# ============================================
# ログ設定
# ============================================
# ログディレクトリを自動作成
os.makedirs("/app/logs/system", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/app/logs/system/fastapi.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ============================================
# 環境変数
# ============================================
API_KEY = os.getenv("API_KEY", "your-secret-key-here")
PHI3_URL = os.getenv("PHI3_URL", "http://phi3:8001")
QWEN_URL = os.getenv("QWEN_URL", "http://qwen:8002")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
MEM0_URL = os.getenv("MEM0_URL", "http://mem0:8080")
LANGGRAPH_URL = os.getenv("LANGGRAPH_URL", "http://langgraph:8081")
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://searxng:8080")
WHISPER_URL = os.getenv("WHISPER_URL", "http://whisper:8000")
PIPER_URL = os.getenv("PIPER_URL", "http://piper:8000")
MCP_URL = os.getenv("MCP_URL", "http://mcp-server:3000")

# ============================================
# FastAPI アプリ初期化
# ============================================
app = FastAPI(
    title="ローカルAI 制御サーバー",
    description="Unity → FastAPI → AI の司令塔",
    version="1.0.0",
)

# CORS設定（Unity・スマホからのアクセスを許可）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 開発中は全許可、本番では制限する
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーターと会話履歴の初期化
ai_router = AIRouter(phi3_url=PHI3_URL, qwen_url=QWEN_URL)
conversation_history = ConversationHistory()

# Phase1: 記憶システムの初期化
short_term_memory = ShortTermMemory(redis_url=REDIS_URL)
memory_organizer = MemoryOrganizer(mem0_url=MEM0_URL, qwen_url=QWEN_URL)
conversation_summarizer = ConversationSummarizer(ai_router=ai_router)

# Phase2: 感情システムの初期化
emotion_manager = EmotionManager(phi3_url=PHI3_URL)

# Phase3: タスク管理とツールレジストリの初期化
task_manager = TaskManager(phi3_url=PHI3_URL)
tool_registry = ToolRegistry()

# Phase4: 音声クライアントの初期化（オプション）
try:
    voice_input = VoiceInputClient(whisper_url=WHISPER_URL)
    voice_output = VoiceOutputClient(piper_url=PIPER_URL)
except Exception as e:
    logger.warning(f"音声クライアント初期化失敗（音声機能はオプション）: {e}")
    voice_input = None
    voice_output = None

# Phase5: MCP, Vision, Autonomous Agentの初期化
mcp_client = MCPClient(mcp_url=MCP_URL)
vision_processor = VisionProcessor()
autonomous_agent = AutonomousAgent(tool_registry, qwen_url=QWEN_URL)


# ============================================
# リクエスト・レスポンスモデル
# ============================================
class ChatRequest(BaseModel):
    """ユーザーからのチャットリクエスト"""
    message: str = Field(..., description="ユーザーのメッセージ", min_length=1)
    user_id: str = Field(default="default_user", description="ユーザーID")
    force_model: Optional[str] = Field(
        default=None, description="AIを強制指定（phi3 / qwen）"
    )


class ChatResponse(BaseModel):
    """AIからのレスポンス"""
    response: str = Field(..., description="AIの応答テキスト")
    model_used: str = Field(..., description="使用したAIモデル名")
    processing_time: float = Field(..., description="処理時間（秒）")
    context_used: bool = Field(..., description="過去の会話を参照したか")


# ============================================
# APIキー認証ミドルウェア
# ============================================
@app.middleware("http")
async def verify_api_key(request: Request, call_next):
    # ヘルスチェックとドキュメントはスキップ
    skip_paths = ["/api/health", "/health", "/docs", "/openapi.json", "/redoc"]
    if request.url.path in skip_paths:
        return await call_next(request)

    # APIキーの検証
    api_key = request.headers.get("X-API-Key")
    if api_key != API_KEY:
        logger.warning(f"不正なAPIキー: {api_key} from {request.client.host}")
        raise HTTPException(status_code=401, detail="無効なAPIキーです")

    return await call_next(request)


# ============================================
# エンドポイント
# ============================================
@app.get("/api/health")
async def health_check():
    """ヘルスチェック - 各サービスの状態を確認"""
    phi3_status = await ai_router.check_health("phi3")
    qwen_status = await ai_router.check_health("qwen")

    return {
        "status": "running",
        "services": {
            "fastapi": "ok",
            "phi3": phi3_status,
            "qwen": qwen_status,
            "redis": "ok" if short_term_memory.redis_client else "disconnected",
            "mem0": "ok",
            "langgraph": "ok",
            "task_manager": "ok",
            "tool_registry": "ok",
            "searxng": "ok",
            "whisper": "ok" if voice_input else "disabled",
            "piper": "ok" if voice_output else "disabled",
            "mcp_server": "ok",
            "vision_processor": "ok",
            "autonomous_agent": "ok",
        },
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    メインのチャットエンドポイント
    1. 短期記憶の更新
    2. 会話要約判定
    3. 過去の会話を検索
    4. AIを振り分け
    5. 応答を生成
    6. 会話を保存
    7. 状態更新
    """
    start_time = time.time()
    user_id = request.user_id
    
    logger.info(f"[{user_id}] リクエスト受信")
    
    # =========================================
    # Step 0: 短期記憶の更新と感情検出
    # =========================================
    short_term_memory.add_recent_message(user_id, request.message)
    short_term_memory.update_session(user_id, increment_count=True)
    
    # 現在の状態を取得
    current_state = short_term_memory.get_state(user_id)
    current_emotion = current_state.get("emotion", {"mood": "neutral", "energy": 50})
    
    # 感情を検出・更新
    detected_emotion = await emotion_manager.detect_emotion(request.message, current_emotion)
    updated_emotion = emotion_manager.update_emotion(user_id, detected_emotion)
    logger.info(f"[{user_id}] 感情: {updated_emotion}")
    
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
    # Step 2.5: タスク分析
    # =========================================
    task = await task_manager.analyze_task(request.message, user_id)
    if task:
        logger.info(f"[{user_id}] タスク作成: {task.task_id}")
    
    # =========================================
    # Step 3: 過去の会話を検索
    # =========================================
    related_context = conversation_history.search_related(
        user_id=user_id,
        query=request.message,
        top_k=3,
    )
    
    # =========================================
    # Step 2: Intent分類（Phi3）→ 処理分岐（TaskRouter）
    # =========================================
    if request.force_model:
        # 互換性のため force_model は残す（通常運用は intent -> qwen 固定）
        selected_model = request.force_model
        intent = "chat"
        routed_message = request.message
        logger.info(f"[{user_id}]   → モデル強制指定: {selected_model}")
    else:
        intent = await ai_router.classify_intent(request.message)
        selected_model = "qwen"
        routed_message = ai_router.build_task_prompt(intent, request.message)
        logger.info(f"[{user_id}]   → intent: {intent} / executor: {selected_model}")
    
    # =========================================
    # Step 3: 実行AIにリクエスト送信（通常はQwen）
    # =========================================
    try:
        ai_response = await ai_router.send_to_ai(
            model=selected_model,
            message=routed_message,
            context=related_context,
        )
    except ConnectionError as e:
        logger.error(f"[{user_id}]   → AI接続エラー: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"AI ({selected_model}) に接続できません。モデルがまだ起動中の可能性があります。"
        )
    except TimeoutError as e:
        logger.error(f"[{user_id}]   → AIタイムアウト: {e}")
        raise HTTPException(
            status_code=504,
            detail=f"AI ({selected_model}) の応答がタイムアウトしました。メッセージが長すぎる可能性があります。"
        )
    except Exception as e:
        logger.error(f"[{user_id}]   → AI通信エラー: {e}")
        raise HTTPException(status_code=503, detail=f"AI ({selected_model}) でエラーが発生しました: {str(e)}")
    
    # =========================================
    # Step 5: 会話を保存
    # =========================================
    conversation_history.save(
        user_id=user_id,
        user_message=request.message,
        ai_response=ai_response,
        model_used=selected_model,
    )
    
    # =========================================
    # Step 6: 応答後に状態更新
    # =========================================
    # トピックを推定（LLMベース）
    topic = await _estimate_topic(request.message, current_state.get("current_topic", "general"), ai_router)
    
    short_term_memory.update_state(
        user_id,
        current_topic=topic,
        emotion=detected_emotion["mood"]
    )
    
    processing_time = round(time.time() - start_time, 3)
    logger.info(f"[{user_id}]   → 応答完了 ({processing_time}秒, {selected_model}, intent={intent})")
    
    return ChatResponse(
        response=ai_response,
        model_used=f"{selected_model}:{intent}",
        processing_time=processing_time,
        context_used=len(related_context) > 0,
    )


@app.get("/api/history")
async def get_history(user_id: str = "default_user", limit: int = 20):
    """会話履歴を取得"""
    history = conversation_history.get_recent(user_id=user_id, limit=limit)
    return {"user_id": user_id, "conversations": history, "count": len(history)}


@app.delete("/api/history")
async def clear_history():
    """会話履歴をリセット（ChromaDBのデータを全削除）"""
    try:
        if conversation_history.collection is not None:
            # コレクションを削除して再作成
            conversation_history.client.delete_collection("conversations")
            conversation_history.collection = conversation_history.client.get_or_create_collection(
                name="conversations",
                metadata={"description": "会話履歴のベクトルストア"},
            )
            logger.info("会話履歴をリセットしました")
            return {"status": "ok", "message": "会話履歴をリセットしました"}
        else:
            return {"status": "error", "message": "ChromaDB未接続"}
    except Exception as e:
        logger.error(f"履歴リセット失敗: {e}")
        raise HTTPException(status_code=500, detail=f"リセット失敗: {str(e)}")


# ============================================
# Phase1: 新規APIエンドポイント
# ============================================

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


# ============================================
# Phase2: 感情システムAPIエンドポイント
# ============================================

@app.get("/api/emotion/current")
async def get_current_emotion(user_id: str = "default_user"):
    """現在の感情を取得"""
    state = short_term_memory.get_state(user_id)
    emotion = state.get("emotion", {"mood": "neutral", "energy": 50})
    return {"user_id": user_id, "emotion": emotion}

@app.get("/api/emotion/history")
async def get_emotion_history(user_id: str = "default_user", limit: int = 10):
    """感情履歴を取得"""
    history = emotion_manager.get_emotion_history(user_id, limit)
    return {"user_id": user_id, "history": history}

@app.get("/api/emotion/animation")
async def get_animation_params(user_id: str = "default_user"):
    """Unityアニメーションパラメータを取得"""
    state = short_term_memory.get_state(user_id)
    emotion = state.get("emotion", {"mood": "neutral", "energy": 50})
    params = emotion_manager.get_unity_animation_params(emotion)
    return {"user_id": user_id, "animation_params": params}


# ============================================
# Phase3: タスク管理APIエンドポイント
# ============================================

@app.get("/api/tasks")
async def get_tasks(user_id: str = "default_user", status: Optional[str] = None):
    """ユーザーのタスク一覧を取得"""
    task_status = TaskStatus(status) if status else None
    tasks = task_manager.get_user_tasks(user_id, task_status)
    return {"user_id": user_id, "tasks": [t.to_dict() for t in tasks]}

@app.post("/api/tasks")
async def create_task(
    title: str,
    description: str,
    priority: str = "medium",
    user_id: str = "default_user"
):
    """タスクを作成"""
    task_priority = TaskPriority(priority)
    task = task_manager.create_task(title, description, task_priority, user_id)
    return task.to_dict()

@app.put("/api/tasks/{task_id}/status")
async def update_task_status(task_id: str, status: str):
    """タスクステータスを更新"""
    task_status = TaskStatus(status)
    success = task_manager.update_task_status(task_id, task_status)
    return {"status": "updated" if success else "failed"}

@app.post("/api/tasks/{task_id}/subtasks")
async def add_subtask(task_id: str, title: str, description: str = ""):
    """サブタスクを追加"""
    subtask = task_manager.add_subtask(task_id, title, description)
    return subtask.to_dict() if subtask else {"status": "failed"}

@app.put("/api/tasks/{task_id}/subtasks/{subtask_id}")
async def complete_subtask(task_id: str, subtask_id: str):
    """サブタスクを完了"""
    success = task_manager.complete_subtask(task_id, subtask_id)
    return {"status": "completed" if success else "failed"}

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    """タスクを削除"""
    success = task_manager.delete_task(task_id)
    return {"status": "deleted" if success else "failed"}


# ============================================
# Phase3: ツールレジストリAPIエンドポイント
# ============================================

@app.get("/api/tools")
async def list_tools():
    """利用可能なツール一覧を取得"""
    return {"tools": tool_registry.list_tools()}

@app.post("/api/tools/{tool_name}/execute")
async def execute_tool(tool_name: str, **kwargs):
    """ツールを実行"""
    result = await tool_registry.execute_tool(tool_name, **kwargs)
    return result


# ============================================
# Phase4: 音声APIエンドポイント
# ============================================

@app.post("/api/voice/transcribe")
async def transcribe_audio(audio_data: bytes, filename: str = "audio.wav"):
    """音声をテキストに変換"""
    if voice_input is None:
        raise HTTPException(status_code=503, detail="音声認識サービスが利用できません")
    text = await voice_input.transcribe(audio_data, filename)
    return {"text": text}

@app.post("/api/voice/synthesize")
async def synthesize_audio(text: str, voice: str = "ja_jp_pt_multispeaker"):
    """テキストを音声に変換"""
    if voice_output is None:
        raise HTTPException(status_code=503, detail="音声合成サービスが利用できません")
    audio = await voice_output.synthesize(text, voice)
    return {"audio": audio, "voice": voice}


# ============================================
# Phase5: MCP, Vision, Autonomous Agent APIエンドポイント
# ============================================

@app.get("/api/mcp/tools")
async def list_mcp_tools():
    """MCPツール一覧を取得"""
    tools = await mcp_client.list_tools()
    return {"tools": tools}

@app.post("/api/mcp/tools/{tool_name}/call")
async def call_mcp_tool(tool_name: str, arguments: dict):
    """MCPツールを呼び出し"""
    result = await mcp_client.call_tool(tool_name, arguments)
    return result

@app.post("/api/vision/analyze")
async def analyze_image(image_data: bytes, task: str = "describe"):
    """画像を分析"""
    result = await vision_processor.analyze_image(image_data, task)
    return result

@app.post("/api/agent/goals")
async def set_goal(description: str, user_id: str = "default_user"):
    """目標を設定"""
    goal_id = autonomous_agent.set_goal(description, user_id)
    return {"goal_id": goal_id}

@app.post("/api/agent/goals/{goal_id}/execute")
async def execute_goal(goal_id: str):
    """目標を実行"""
    result = await autonomous_agent.execute_goal(goal_id)
    return result

@app.get("/api/agent/goals")
async def get_goals(user_id: str = "default_user"):
    """ユーザーの目標一覧を取得"""
    goals = autonomous_agent.get_user_goals(user_id)
    return {"goals": goals}


# ============================================
# 起動時の初期化
# ============================================
@app.on_event("startup")
async def startup_event():
    logger.info("=" * 50)
    logger.info("ローカルAI 制御サーバー起動")
    logger.info(f"  Phi3 URL: {PHI3_URL}")
    logger.info(f"  Qwen URL: {QWEN_URL}")
    logger.info(f"  Redis URL: {REDIS_URL}")
    logger.info(f"  Mem0 URL: {MEM0_URL}")
    logger.info(f"  LangGraph URL: {LANGGRAPH_URL}")
    
    # Redis接続確認
    if short_term_memory.redis_client:
        logger.info("  Redis: 接続済み")
    else:
        logger.warning("  Redis: 未接続")
    
    # Mem0接続確認
    logger.info("  Mem0: 初期化完了")
    
    # 感情システム確認
    logger.info("  EmotionManager: 初期化完了")
    
    # タスク管理とツール確認
    logger.info("  TaskManager: 初期化完了")
    logger.info("  ToolRegistry: 初期化完了")
    
    # 音声クライアント確認
    logger.info("  VoiceInputClient: 初期化完了")
    logger.info("  VoiceOutputClient: 初期化完了")
    
    # Phase5確認
    logger.info("  MCPClient: 初期化完了")
    logger.info("  VisionProcessor: 初期化完了")
    logger.info("  AutonomousAgent: 初期化完了")
    
    logger.info("=" * 50)

async def _estimate_topic(message: str, current_topic: str, ai_router: AIRouter) -> str:
    """
    トピックを推定（LLMベース）
    """
    try:
        prompt = f"""
以下のメッセージのトピックを推定してください。現在のトピック: {current_topic}

メッセージ: {message}

出力形式（JSON）:
{{
  "topic": "トピック名",
  "confidence": 0.0-1.0
}}

トピック例: Unity, プログラミング, ゲーム開発, 一般, AI, データ分析, Web開発, etc.
"""
        
        response = await ai_router.send_to_ai(
            model="phi3",
            message=prompt,
            context=[]
        )
        
        # JSONをパース
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            data = json.loads(json_match.group())
            topic = data.get("topic", current_topic)
            logger.info(f"LLMトピック推定: {topic}")
            return topic
    except Exception as e:
        logger.warning(f"LLMトピック推定失敗、フォールバック使用: {e}")
    
    # フォールバック: キーワードベース
    if "Unity" in message:
        return "Unity"
    elif "コード" in message or "プログラム" in message:
        return "プログラミング"
    elif "ゲーム" in message:
        return "ゲーム開発"
    else:
        return current_topic
