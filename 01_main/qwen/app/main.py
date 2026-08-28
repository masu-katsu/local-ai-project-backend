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
from fastapi import FastAPI, HTTPException
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
        f"現在日時: {current_datetime}\n"
        f"リクエスト受付日時: {request_datetime}\n"
        "過去の会話に含まれる日付を尊重し、現在日時と混同しないでください。\n"
    )

    # Qwen チャットテンプレート (ChatML形式) - system
    prompt = f"<|im_start|>system\n{system_content}<|im_end|>\n"

    # 過去の関連会話を「会話ターン」として追加
    if context:
        for conv in context:
            user_msg = conv.get("user_message", "")
            ai_resp = conv.get("ai_response", "")[:150]
            event_date = conv.get("date", "") or conv.get("timestamp", "")
            date_prefix = f"[出来事の日付: {event_date}]\n" if event_date else ""
            prompt += f"<|im_start|>user\n{date_prefix}{user_msg}<|im_end|>\n"
            prompt += f"<|im_start|>assistant\n{ai_resp}<|im_end|>\n"

    # 現在のユーザーメッセージ
    prompt += f"<|im_start|>user\n{message}<|im_end|>\n"
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


@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    """テキスト生成"""
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

        # 生成実行
        async with generation_lock:
            output = await asyncio.to_thread(
                llm,
                prompt,
                max_tokens=MAX_TOKENS,
                temperature=0.7,
                top_p=0.9,
                stop=["<|im_end|>", "<|im_start|>"],
                echo=False,
            )

        raw_text = output["choices"][0]["text"].strip()
        response_text = clean_response(raw_text)
        tokens_used = output.get("usage", {}).get("total_tokens", 0)

        if raw_text != response_text:
            logger.info(f"メタ解説を除去: {len(raw_text)} → {len(response_text)}文字")
        logger.info(f"生成完了: {tokens_used}トークン使用")

        return GenerateResponse(
            response=response_text,
            tokens_used=tokens_used,
        )

    except Exception as e:
        logger.error(f"生成エラー: {e}")
        return GenerateResponse(
            response="申し訳ありません、応答の生成中にエラーが発生しました。",
            tokens_used=0,
        )
