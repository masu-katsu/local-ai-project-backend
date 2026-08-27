# ============================================
# 会話履歴管理（ChromaDB ベクトル検索）
# ============================================
# 会話を保存し、関連する過去会話を検索する
# ChromaDB で「意味の近さ」による検索を実現
# ============================================

import os
import json
import logging
import time
from datetime import datetime

import chromadb

logger = logging.getLogger(__name__)

CHROMA_HOST = os.getenv("CHROMA_HOST", "chromadb")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8003"))


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
    ) -> None:
        """
        会話を保存する

        ChromaDB には以下の形で保存:
        - document: ユーザーメッセージ（ベクトル検索対象）
        - metadata: 応答・モデル名・タイムスタンプなど
        """
        if self.collection is None:
            return

        timestamp = datetime.now().isoformat()
        doc_id = f"{user_id}_{timestamp}"

        try:
            # Q&Aペアを検索対象にすることで、文脈の類似度を向上
            search_document = f"Q: {user_message} A: {ai_response[:200]}"
            self.collection.add(
                documents=[search_document],
                metadatas=[
                    {
                        "user_id": user_id,
                        "user_message": user_message,
                        "ai_response": ai_response,
                        "model_used": model_used,
                        "timestamp": timestamp,
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
    ) -> list[dict]:
        """
        現在のメッセージに関連する過去の会話を検索する

        ChromaDB のベクトル検索を使い、意味的に近い過去会話を取得
        max_distance で関連性の低い結果をフィルタリング
        """
        if self.collection is None or self.collection.count() == 0:
            return []

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=min(top_k, self.collection.count()),
                where={"user_id": user_id},
                include=["metadatas", "distances"],
            )

            # 結果を整形（類似度フィルタ付き）
            related = []
            if results and results["metadatas"]:
                distances = results.get("distances", [[]])[0]
                for i, metadata in enumerate(results["metadatas"][0]):
                    # 距離が閾値以下のもののみ採用
                    dist = distances[i] if i < len(distances) else 999
                    if dist <= max_distance:
                        related.append(
                            {
                                "user_message": metadata.get("user_message", ""),
                                "ai_response": metadata.get("ai_response", ""),
                                "timestamp": metadata.get("timestamp", ""),
                            }
                        )
                        logger.info(f"  関連会話 [{i+1}] 距離={dist:.3f}: {metadata.get('user_message', '')[:40]}")
                    else:
                        logger.info(f"  除外（距離超過）[{i+1}] 距離={dist:.3f}: {metadata.get('user_message', '')[:40]}")

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
