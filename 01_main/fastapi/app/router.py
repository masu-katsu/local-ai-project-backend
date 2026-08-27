# ============================================
# AI ルーター（Qwen 直結ルーティング）
# ============================================
# FastAPI から直接 Qwen に送信
# ============================================

import logging

import httpx

logger = logging.getLogger(__name__)


class AIRouter:
    def __init__(self, qwen_url: str):
        self.qwen_url = qwen_url
        self.client = httpx.AsyncClient(timeout=120.0)
        logger.info("AIRouter 初期化完了（実行: Qwen）")

    def build_task_prompt(self, message: str) -> str:
        """Qwen へ直接送るためのシンプルなプロンプトを組み立てる。"""
        task_header = (
            "[MODE: CHAT]\n"
            "あなたは自然な会話アシスタントです。"
            "日本語で分かりやすく回答してください。"
        )
        return f"{task_header}\n\nユーザー入力:\n{message}"

    async def send_to_ai(self, model: str, message: str, context: list[dict]) -> str:
        """指定モデルにリクエスト送信する共通メソッド。"""
        url = self._get_url(model)
        payload = {
            "message": message,
            "context": context,
        }
        try:
            response = await self.client.post(
                f"{url}/generate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "応答を取得できませんでした")
        except httpx.ConnectError:
            logger.error(f"{model} に接続できません: {url}")
            raise ConnectionError(f"{model} サービスに接続できません")
        except httpx.TimeoutException:
            logger.error(f"{model} がタイムアウトしました")
            raise TimeoutError(f"{model} の応答がタイムアウトしました")
        except Exception as e:
            logger.error(f"{model} 通信エラー: {e}")
            raise

    async def check_health(self, model: str) -> str:
        """AIサービスのヘルスチェック"""
        url = self._get_url(model)
        try:
            response = await self.client.get(f"{url}/health", timeout=5.0)
            if response.status_code == 200:
                return "ok"
            return f"error (status: {response.status_code})"
        except Exception:
            return "offline"

    def _get_url(self, model: str) -> str:
        if model == "qwen":
            return self.qwen_url
        raise ValueError(f"不明なモデル: {model}")
