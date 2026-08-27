# ============================================
# FastAPI メインサーバー（司令塔）
# ============================================
# すべてのリクエストはここを通る
# Unity → FastAPI → Qwen → FastAPI → Unity
# ============================================

import os
import time
import logging
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.router import AIRouter
from app.history import ConversationHistory

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
QWEN_URL = os.getenv("QWEN_URL", "http://qwen:8002")
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost,http://127.0.0.1"
    ).split(",")
    if origin.strip()
]

if API_KEY in {"", "your-secret-key", "your-secret-key-here"}:
    raise RuntimeError("API_KEY must be configured with a non-default value")

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
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ルーターと会話履歴の初期化
ai_router = AIRouter(qwen_url=QWEN_URL)
conversation_history = ConversationHistory()


# ============================================
# リクエスト・レスポンスモデル
# ============================================
class ChatRequest(BaseModel):
    """ユーザーからのチャットリクエスト"""
    message: str = Field(..., description="ユーザーのメッセージ", min_length=1)
    user_id: str = Field(
        default="default_user",
        description="ユーザーID",
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
    )


class ChatResponse(BaseModel):
    """AIからのレスポンス"""
    model_config = ConfigDict(protected_namespaces=())

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
    skip_paths = ["/health", "/api/health", "/docs", "/openapi.json", "/redoc"]
    if request.url.path in skip_paths:
        return await call_next(request)

    # APIキーの検証
    api_key = request.headers.get("X-API-Key")
    if api_key != API_KEY:
        logger.warning(f"不正なAPIキー from {request.client.host}")
        return JSONResponse(status_code=401, content={"detail": "無効なAPIキーです"})

    return await call_next(request)


# ============================================
# エンドポイント
# ============================================
@app.get("/health")
@app.get("/api/health")
async def health_check():
    """ヘルスチェック - 各サービスの状態を確認"""
    qwen_status = await ai_router.check_health("qwen")

    return {
        "status": "running" if qwen_status == "ok" else "degraded",
        "services": {
            "fastapi": "ok",
            "qwen": qwen_status,
        },
    }


@app.post("/api/chat", response_model=ChatResponse)
@app.post("/unity/predict", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    メインのチャットエンドポイント
    1. 過去の会話を検索
    2. AIを振り分け
    3. 応答を生成
    4. 会話を保存
    """
    start_time = time.time()
    user_id = request.user_id
    
    logger.info(f"[{user_id}] リクエスト受信")
    
    # =========================================
    # Step 1: 過去の会話を検索
    # =========================================
    related_context = conversation_history.search_related(
        user_id=user_id,
        query=request.message,
        top_k=3,
    )
    
    # =========================================
    # Step 2: 直接 Qwen に送信
    # =========================================
    selected_model = "qwen"
    routed_message = ai_router.build_task_prompt(request.message)
    logger.info(f"[{user_id}]   → executor: {selected_model}")
    
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
    # Step 4: 会話を保存
    # =========================================
    conversation_history.save(
        user_id=user_id,
        user_message=request.message,
        ai_response=ai_response,
        model_used=selected_model,
    )
    
    processing_time = round(time.time() - start_time, 3)
    logger.info(f"[{user_id}]   → 応答完了 ({processing_time}秒, {selected_model})")
    
    return ChatResponse(
        response=ai_response,
        model_used=f"{selected_model}:chat",
        processing_time=processing_time,
        context_used=len(related_context) > 0,
    )


@app.get("/api/history")
async def get_history(
    user_id: str = Query(
        default="default_user",
        min_length=1,
        max_length=64,
        pattern=r"^[A-Za-z0-9_-]+$",
    ),
    limit: int = Query(default=20, ge=1, le=100),
):
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
            conversation_history.clear_backup_files()
            logger.info("会話履歴をリセットしました")
            return {"status": "ok", "message": "会話履歴をリセットしました"}
        else:
            return {"status": "error", "message": "ChromaDB未接続"}
    except Exception as e:
        logger.error(f"履歴リセット失敗: {e}")
        raise HTTPException(status_code=500, detail=f"リセット失敗: {str(e)}")


# ============================================
# 起動時の初期化
# ============================================
@app.on_event("startup")
async def startup_event():
    logger.info("=" * 50)
    logger.info("ローカルAI 制御サーバー起動")
    logger.info(f"  Qwen URL: {QWEN_URL}")
    logger.info("=" * 50)
