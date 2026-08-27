# ============================================
# 会話履歴管理（ChromaDB ベクトル検索）
# ============================================
# 会話を保存し、関連する過去会話を検索する
# ChromaDB で「意味の近さ」による検索を実現
# ============================================

import os
import json
import logging
import math
import re
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import chromadb

logger = logging.getLogger(__name__)

CHROMA_HOST = os.getenv("CHROMA_HOST", "chromadb")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8003"))
TIME_DECAY_HALF_LIFE_DAYS = max(
    0.1, float(os.getenv("TIME_DECAY_HALF_LIFE_DAYS", "30"))
)
try:
    APP_TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "Asia/Tokyo"))
except Exception:
    APP_TIMEZONE = timezone(timedelta(hours=9))


def extract_time_range(
    query: str,
    reference_time: datetime | None = None,
) -> tuple[float, float] | None:
    """質問に含まれる日本語の期間表現をUnix秒の範囲へ変換する。"""
    now = reference_time or datetime.now(APP_TIMEZONE)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if re.search(r"一昨日", query):
        start = today - timedelta(days=2)
        end = start + timedelta(days=1)
    elif re.search(r"昨日", query):
        start = today - timedelta(days=1)
        end = today
    elif re.search(r"今日|本日", query):
        start = today
        end = today + timedelta(days=1)
    elif re.search(r"先週|前週", query):
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=7)
    elif re.search(r"先月|前月", query):
        first_of_this_month = today.replace(day=1)
        end = first_of_this_month
        start = (first_of_this_month - timedelta(days=1)).replace(day=1)
    elif re.search(r"去年|昨年", query):
        start = today.replace(year=today.year - 1, month=1, day=1)
        end = today.replace(year=today.year, month=1, day=1)
        if re.search(r"夏", query):
            start = start.replace(month=6)
            end = start.replace(month=9)
    elif re.search(r"今年の夏|今年夏", query):
        start = today.replace(month=6, day=1)
        end = today.replace(month=9, day=1)
    else:
        date_match = re.search(r"(20\d{2})[年/-](\d{1,2})[月/-](\d{1,2})日?", query)
        if not date_match:
            return None
        try:
            start = datetime(
                int(date_match.group(1)),
                int(date_match.group(2)),
                int(date_match.group(3)),
                tzinfo=now.tzinfo,
            )
        except ValueError:
            return None
        end = start + timedelta(days=1)

    return start.timestamp(), end.timestamp()


class ConversationHistory:
    def __init__(self):
        """ChromaDB に接続し、コレクションを初期化"""
        self.client = None
        self.collection = None

        for attempt in range(10):
            try:
                self.client = chromadb.HttpClient(
                    host=CHROMA_HOST,
                    port=CHROMA_PORT,
                )
                self.collection = self.client.get_or_create_collection(
                    name="conversations",
                    metadata={"description": "会話履歴のベクトルストア"},
                )
                logger.info(
                    f"ChromaDB 接続成功 ({CHROMA_HOST}:{CHROMA_PORT})"
                    f" - 既存レコード数: {self.collection.count()}"
                )
                break
            except Exception as e:
                self.client = None
                self.collection = None
                if attempt == 9:
                    logger.error(f"ChromaDB 接続失敗: {e}")
                    logger.warning("会話履歴機能は無効化されます")
                else:
                    logger.warning(
                        f"ChromaDB 接続待機中 ({attempt + 1}/10): {e}"
                    )
                    time.sleep(2)

    def save(
        self,
        user_id: str,
        user_message: str,
        ai_response: str,
        model_used: str,
        request_time: datetime | None = None,
    ) -> None:
        """
        会話を保存する

        ChromaDB には以下の形で保存:
        - document: ユーザーメッセージ（ベクトル検索対象）
        - metadata: 応答・モデル名・タイムスタンプなど
        """
        if self.collection is None:
            return

        occurred_at = request_time or datetime.now(APP_TIMEZONE)
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=APP_TIMEZONE)
        timestamp = occurred_at.isoformat()
        timestamp_unix = occurred_at.timestamp()
        date_str = occurred_at.strftime("%Y-%m-%d")
        doc_id = f"{user_id}_{timestamp}"

        try:
            # Q&Aペアを検索対象にすることで、文脈の類似度を向上
            search_document = (
                f"リクエスト受付日時: {timestamp}\n"
                f"出来事の日付: {date_str}\n"
                f"Q: {user_message} A: {ai_response[:200]}"
            )
            self.collection.add(
                documents=[search_document],
                metadatas=[
                    {
                        "user_id": user_id,
                        "user_message": user_message,
                        "ai_response": ai_response,
                        "model_used": model_used,
                        "timestamp": timestamp,
                        "timestamp_unix": timestamp_unix,
                        "request_datetime": timestamp,
                        "request_timestamp_unix": timestamp_unix,
                        "date": date_str,
                    }
                ],
                ids=[doc_id],
            )
            logger.info(f"  会話保存完了: {doc_id}")

            # ファイルにもバックアップ保存
            self._save_to_file(user_id, user_message, ai_response, model_used, timestamp)

        except Exception as e:
            logger.error(f"  会話保存失敗: {e}")

    def search_related(
        self,
        user_id: str,
        query: str,
        top_k: int = 3,
        max_distance: float = 1.5,
        reference_time: datetime | None = None,
    ) -> list[dict]:
        """
        現在のメッセージに関連する過去の会話を検索する

        ChromaDB のベクトル検索を使い、意味的に近い過去会話を取得
        max_distance で関連性の低い結果をフィルタリング
        """
        if self.collection is None or self.collection.count() == 0:
            return []

        try:
            time_range = extract_time_range(query, reference_time)
            where: dict = {"user_id": user_id}
            if time_range is not None:
                start_timestamp, end_timestamp = time_range
                where = {
                    "$and": [
                        {"user_id": {"$eq": user_id}},
                        {"timestamp_unix": {"$gte": start_timestamp}},
                        {"timestamp_unix": {"$lt": end_timestamp}},
                    ]
                }

            candidate_count = min(20, self.collection.count())
            logger.info(f"  関連会話候補取得: 最大{candidate_count}件")
            results = self.collection.query(
                query_texts=[query],
                n_results=candidate_count,
                where=where,
                include=["metadatas", "distances"],
            )

            # 結果を整形（類似度フィルタ付き）
            related = []
            if results and results.get("metadatas"):
                distances = results.get("distances", [[]])[0]
                ranked = []
                for i, metadata in enumerate(results["metadatas"][0]):
                    # 距離が閾値以下のもののみ採用
                    dist = distances[i] if i < len(distances) else 999
                    if dist <= max_distance:
                        timestamp_unix = metadata.get("timestamp_unix")
                        try:
                            age_days = max(
                                0.0,
                                (
                                    (reference_time or datetime.now(APP_TIMEZONE)).timestamp()
                                    - float(timestamp_unix)
                                )
                                / 86400,
                            )
                        except (TypeError, ValueError):
                            age_days = 0.0
                        freshness_penalty = 0.15 * (
                            1 - math.exp(-age_days / TIME_DECAY_HALF_LIFE_DAYS)
                        )
                        ranked.append(
                            (
                                dist + freshness_penalty,
                                {
                                    "user_message": metadata.get("user_message", ""),
                                    "ai_response": metadata.get("ai_response", ""),
                                    "timestamp": metadata.get("timestamp", ""),
                                    "request_datetime": metadata.get(
                                        "request_datetime", metadata.get("timestamp", "")
                                    ),
                                    "date": metadata.get("date", ""),
                                },
                            )
                        )
                        logger.info(f"  関連会話 [{i+1}] 距離={dist:.3f}: {metadata.get('user_message', '')[:40]}")
                    else:
                        logger.info(f"  除外（距離超過）[{i+1}] 距離={dist:.3f}: {metadata.get('user_message', '')[:40]}")

                ranked.sort(key=lambda item: item[0])
                related = [item[1] for item in ranked[:top_k]]

            logger.info(f"  関連会話検索: {len(related)}件採用（フィルタ後）")
            return related

        except Exception as e:
            logger.error(f"  関連会話検索失敗: {e}")
            return []

    def get_recent(self, user_id: str, limit: int = 20) -> list[dict]:
        """直近の会話を時系列で取得"""
        if self.collection is None or self.collection.count() == 0:
            return []

        try:
            results = self.collection.get(
                where={"user_id": user_id},
            )

            conversations = []
            if results and results["metadatas"]:
                for metadata in results["metadatas"]:
                    conversations.append(
                        {
                            "user_message": metadata.get("user_message", ""),
                            "ai_response": metadata.get("ai_response", ""),
                            "model_used": metadata.get("model_used", ""),
                            "timestamp": metadata.get("timestamp", ""),
                            "request_datetime": metadata.get(
                                "request_datetime", metadata.get("timestamp", "")
                            ),
                            "date": metadata.get("date", ""),
                        }
                    )

                # タイムスタンプでソート（新しい順）
                conversations.sort(key=lambda x: x["timestamp"], reverse=True)

            return conversations[:limit]

        except Exception as e:
            logger.error(f"  履歴取得失敗: {e}")
            return []

    def clear_backup_files(self) -> None:
        """会話バックアップのJSONLファイルをすべて削除"""
        log_dir = os.getenv("LOG_DIR", "/logs")
        if not os.path.isdir(log_dir):
            return

        for filename in os.listdir(log_dir):
            if filename.endswith(".jsonl"):
                os.remove(os.path.join(log_dir, filename))

    def _save_to_file(
        self,
        user_id: str,
        user_message: str,
        ai_response: str,
        model_used: str,
        timestamp: str,
    ) -> None:
        """会話をJSONファイルにもバックアップ保存"""
        log_dir = os.getenv("LOG_DIR", "/logs")
        os.makedirs(log_dir, exist_ok=True)

        date_str = datetime.now().strftime("%Y-%m-%d")
        filepath = os.path.join(log_dir, f"{user_id}_{date_str}.jsonl")

        entry = {
            "timestamp": timestamp,
            "user_message": user_message,
            "ai_response": ai_response,
            "model_used": model_used,
        }

        try:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"  ファイル保存失敗: {e}")
