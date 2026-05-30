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
