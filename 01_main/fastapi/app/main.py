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
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

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
PHI3_URL = os.getenv("PHI3_URL", "http://phi3:8001")
QWEN_URL = os.getenv("QWEN_URL", "http://qwen:8002")

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
    skip_paths = ["/api/health", "/docs", "/openapi.json", "/redoc"]
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
        },
    }


@app.post("/api/chat", response_model=ChatResponse)
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
    # Step 4: 会話を保存
    # =========================================
    conversation_history.save(
        user_id=user_id,
        user_message=request.message,
        ai_response=ai_response,
        model_used=selected_model,
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
# 起動時の初期化
# ============================================
@app.on_event("startup")
async def startup_event():
    logger.info("=" * 50)
    logger.info("ローカルAI 制御サーバー起動")
    logger.info(f"  Phi3 URL: {PHI3_URL}")
    logger.info(f"  Qwen URL: {QWEN_URL}")
    logger.info("=" * 50)
