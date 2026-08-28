# ============================================
# Qwen 生成AI サーバー（GPU動作）
# ============================================
# コード生成・長文生成など重い処理を担当
# llama-cpp-python で GGUF モデルを GPU (RTX3050 4GB) 上で実行
# ============================================

import os
import re
import logging
import asyncio
import json
import threading
from collections.abc import AsyncIterator
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from llama_cpp import Llama, llama_supports_gpu_offload


def clean_response(text: str) -> str:
    """
    Aggressively remove all instruction patterns and meta text
    """
    # First pass: remove entire lines with instruction keywords
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        # Skip lines containing instruction/step keywords
        if any(kw in line for kw in ['指示', 'instruction', 'step', 'ステップ', 'Instruction', 'Step', '発語詰、']):
            continue
        # Skip lines with only brackets/metadata
        if line.strip() and all(c in '[]{}()\[\]{}()\n' for c in line.strip()):
            continue
        cleaned_lines.append(line)
    
    text = '\n'.join(cleaned_lines)
    
    # Second pass: regex patterns for remaining cleanup
    meta_patterns = [
        r"\n\n+(?:この|その|上記の|以下の|以上の|下記の)[^\n]*$",
        r"\n\n+(?:Answer|Response|Note|注[:：]).*$",
        r"\n\n+-{3,}.*$",
        r"^\s*\[.*?\]\s*$",
        r"^\s*\{.*?\}\s*$",
        r"^\s*\(.*?\)\s*$",
    ]
    for pattern in meta_patterns:
        text = re.sub(pattern, "", text, flags=re.MULTILINE | re.DOTALL)
    
    # Remove excessive newlines
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()

# ============================================
# ログ設定
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [Qwen] %(message)s",
)
logger = logging.getLogger(__name__)

# ============================================
# 環境変数・設定
# ============================================
MODEL_PATH = os.getenv("MODEL_PATH", "/03_models/qwen/Qwen_Qwen3.5-4B-Q4_K_M.gguf")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "2048"))
N_GPU_LAYERS = int(os.getenv("N_GPU_LAYERS", "0"))  # 0 = CPU 優先 / GPU が無い環境でも起動
N_CTX = 8192  # Qwen2.5 のコンテキストウィンドウ
try:
    APP_TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Tokyo"))
except Exception:
    APP_TIMEZONE = timezone(timedelta(hours=9))

# ============================================
# FastAPI 初期化
# ============================================
app = FastAPI(title="Qwen 生成AI", version="1.0.0")

# ============================================
# モデル読み込み（起動時に1回だけ）
# ============================================
llm: Optional[Llama] = None
generation_lock = asyncio.Lock()


@app.on_event("startup")
async def load_model():
    global llm

    logger.info("=" * 40)
    logger.info("Qwen モデル読み込み開始...")
    logger.info(f"  モデルパス: {MODEL_PATH}")
    logger.info(f"  GPU レイヤー数: {N_GPU_LAYERS}")
    logger.info(f"  最大トークン: {MAX_TOKENS}")

    try:
        llm = await asyncio.to_thread(
            Llama,
            model_path=MODEL_PATH,
            n_ctx=N_CTX,
            n_gpu_layers=N_GPU_LAYERS,
            verbose=False,
        )
        logger.info("Qwen モデル読み込み完了 ✓")
    except Exception as e:
        logger.error(f"モデル読み込み失敗: {e}")
        logger.error("モデルファイルが存在するか確認してください")
        llm = None


# ============================================
# リクエスト・レスポンスモデル
# ============================================
class GenerateRequest(BaseModel):
    message: str = Field(..., description="ユーザーのメッセージ")
    context: list[dict] = Field(default_factory=list, description="過去の関連会話")
    current_datetime: Optional[str] = Field(
        default=None,
        description="システムが取得した現在日時（ISO 8601）",
    )
    request_datetime: Optional[str] = Field(
        default=None,
        description="FastAPIがリクエストを受け付けた日時（ISO 8601）",
    )


class GenerateResponse(BaseModel):
    response: str = Field(..., description="AIの応答")
    tokens_used: int = Field(default=0, description="使用トークン数")


# ============================================
# プロンプト構築
# ============================================
def build_prompt(
    message: str,
    context: list[dict],
    current_datetime: str | None = None,
    request_datetime: str | None = None,
) -> str:
    """
    Qwen 用のプロンプトを構築する

    過去の関連会話を「会話ターン」として埋め込む
    → モデルが自然に文脈を理解し、そのまま出力しなくなる
    """
    current_datetime = current_datetime or datetime.now(APP_TIMEZONE).isoformat()
    request_datetime = request_datetime or current_datetime
    system_content = (
        "あなたは高度な日本語AIアシスタントです。\n"
        "コード生成、文章作成、翻訳、分析など専門的なタスクが得意です。\n"
        "正確で詳細な回答を提供してください。\n"
        f"最新の現在日時（すべての回答の基準）: {current_datetime}\n"
        f"リクエスト受付日時: {request_datetime}\n"
        "ChromaDBから渡される情報はすべて過去の会話です。現在の会話や現在の情報と混同しないでください。\n"
        "過去の会話に含まれる日時や過去のAI回答を、現在日時として使用しないでください。\n"
        "日時を伝える場合は、必ず最新の現在日時を使用してください。\n"
    )

    # Qwen チャットテンプレート (ChatML形式) - system
    prompt = f"<|im_start|>system\n{system_content}<|im_end|>\n"

    # 過去の関連会話は、現在の会話と区別できるよう明示して追加する。
    if context:
        prompt += (
            "<|im_start|>system\n"
            "ここからはChromaDBが参照した過去の会話（参考情報）です。"
            "これらは現在の発言ではなく、含まれる日時や回答も過去のものです。"
            "<|im_end|>\n"
        )
        for conv in context:
            user_msg = conv.get("user_message", "")
            ai_resp = conv.get("ai_response", "")[:150]
            event_date = conv.get("date", "") or conv.get("timestamp", "")
            request_date = conv.get("request_datetime", "")
            date_prefix = (
                f"[過去の会話 / 出来事の日付: {event_date}]\n"
                if event_date
                else "[過去の会話]\n"
            )
            if request_date and request_date != event_date:
                date_prefix += f"[過去の会話の受付日時: {request_date}]\n"
            prompt += f"<|im_start|>user\n{date_prefix}{user_msg}<|im_end|>\n"
            prompt += f"<|im_start|>assistant\n{ai_resp}<|im_end|>\n"

    # 現在のユーザーメッセージ
    prompt += (
        "<|im_start|>user\n"
        f"[現在の会話 / 最新の現在日時（回答の基準）: {current_datetime}]\n"
        f"{message}<|im_end|>\n"
    )
    prompt += "<|im_start|>assistant\n"

    return prompt


# ============================================
# エンドポイント
# ============================================
@app.get("/health")
async def health():
    """ヘルスチェック"""
    return {
        "status": "ok" if llm is not None else "model_not_loaded",
        "model": "Qwen2.5-Coder-3B",
        "device": "gpu" if N_GPU_LAYERS != 0 and llama_supports_gpu_offload() else "cpu",
        "gpu_offload_supported": llama_supports_gpu_offload(),
        "gpu_layers": N_GPU_LAYERS,
    }


async def generate_chunks(request: GenerateRequest) -> AsyncIterator[str]:
    """モデルの同期イテレータを非同期のテキストストリームへ変換する。"""
    if llm is None:
        raise HTTPException(
            status_code=503,
            detail="モデルがまだ読み込まれていません。しばらくお待ちください。",
        )

    logger.info(f"生成リクエスト: {request.message[:50]}...")

    try:
        # プロンプト構築
        prompt = build_prompt(
            request.message,
            request.context,
            request.current_datetime,
            request.request_datetime,
        )

        queue: asyncio.Queue[object] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        end_marker = object()
        stop_event = threading.Event()
        worker: asyncio.Task[None] | None = None

        def enqueue(item: object) -> None:
            try:
                loop.call_soon_threadsafe(queue.put_nowait, item)
            except RuntimeError:
                # リクエスト切断後にイベントループが終了している場合は破棄する。
                pass

        def generate_in_thread() -> None:
            output_stream = None
            try:
                output_stream = llm(
                    prompt,
                    max_tokens=MAX_TOKENS,
                    temperature=0.7,
                    top_p=0.9,
                    stop=["<|im_end|>", "<|im_start|>"],
                    echo=False,
                    stream=True,
                )
                for output in output_stream:
                    if stop_event.is_set():
                        break
                    text = output["choices"][0].get("text", "")
                    if text:
                        enqueue(text)
            except Exception as error:
                if not stop_event.is_set():
                    enqueue(error)
            finally:
                if output_stream is not None:
                    close = getattr(output_stream, "close", None)
                    if close is not None:
                        close()
                enqueue(end_marker)

        try:
            async with generation_lock:
                worker = asyncio.create_task(asyncio.to_thread(generate_in_thread))
                while True:
                    item = await queue.get()
                    if item is end_marker:
                        break
                    if isinstance(item, Exception):
                        raise item
                    yield item
                await worker
            logger.info("生成ストリーム完了")
        finally:
            stop_event.set()
            if worker is not None and not worker.done():
                await asyncio.shield(worker)

    except Exception as e:
        logger.error(f"生成エラー: {e}")
        raise HTTPException(
            status_code=500,
            detail="申し訳ありません、応答の生成中にエラーが発生しました。",
        )


@app.post("/generate")
async def generate(request: GenerateRequest):
    """テキストをストリームで逐次生成する。"""
    async def event_stream() -> AsyncIterator[str]:
        async for chunk in generate_chunks(request):
            yield "data: " + json.dumps(
                {"text": chunk}, ensure_ascii=False
            ) + "\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
