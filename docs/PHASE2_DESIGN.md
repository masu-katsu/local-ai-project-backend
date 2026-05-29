# Phase2 詳細設計: 思考フローの構造化

## 概要

Phase2では、LangGraphによるAI思考フローの構造化と、Emotion System（感情管理）を実装する。

**目的**:
- AI内部の思考手順を構造化する（LangGraph）
- 人格と会話の安定化（Emotion System）
- Unityとの感情連携

---

## コンポーネント詳細

### 1. LangGraph（AI思考フロー制御）

#### 役割
- AI内部の思考手順を構造化
- 状態維持
- Agent化の基盤

#### 思考フローノード

```python
# app/graph_nodes.py

from typing import TypedDict, Annotated, Sequence
from operator import add
from langgraph.graph import StateGraph, END

class AIState(TypedDict):
    """AIの状態定義"""
    user_id: str
    input_message: str
    emotion: dict
    short_term_context: dict
    long_term_context: list
    important_memories: list
    task_analysis: dict
    selected_tools: list
    llm_response: str
    final_response: str
    processing_steps: list[str]

# ノード1: 感情更新
async def update_emotion_node(state: AIState) -> AIState:
    """感情状態を更新"""
    from app.emotion_manager import EmotionManager
    emotion_manager = EmotionManager()
    
    # 入力に基づいて感情を更新
    updated_emotion = emotion_manager.update_from_input(
        state["input_message"],
        state["emotion"]
    )
    
    state["emotion"] = updated_emotion
    state["processing_steps"].append("emotion_update")
    
    return state

# ノード2: 記憶検索
async def search_memory_node(state: AIState) -> AIState:
    """記憶を検索（短期・長期・重要）"""
    from app.short_term_memory import ShortTermMemory
    from app.memory_organizer import MemoryOrganizer
    from app.history import ConversationHistory
    
    # 短期記憶
    short_term = ShortTermMemory()
    state["short_term_context"] = short_term.get_state(state["user_id"])
    
    # 長期記憶（ChromaDB）
    history = ConversationHistory()
    state["long_term_context"] = history.search_related(
        user_id=state["user_id"],
        query=state["input_message"],
        top_k=3
    )
    
    # 重要記憶（Mem0）
    mem0 = MemoryOrganizer()
    state["important_memories"] = await mem0.search_memories(
        query=state["input_message"],
        user_id=state["user_id"],
        top_k=3
    )
    
    state["processing_steps"].append("memory_search")
    
    return state

# ノード3: タスク分析
async def analyze_task_node(state: AIState) -> AIState:
    """タスクを分析・分解"""
    from app.task_manager import TaskManager
    
    task_manager = TaskManager()
    
    # 入力を分析してタスクか判断
    analysis = await task_manager.analyze_input(
        state["input_message"],
        context={
            "short_term": state["short_term_context"],
            "long_term": state["long_term_context"],
            "emotion": state["emotion"]
        }
    )
    
    state["task_analysis"] = analysis
    state["processing_steps"].append("task_analysis")
    
    return state

# ノード4: ツール選択
async def select_tools_node(state: AIState) -> AIState:
    """必要なツールを選択"""
    from app.tool_registry import ToolRegistry
    
    tool_registry = ToolRegistry()
    
    # タスク分析に基づいてツールを選択
    selected_tools = tool_registry.select_tools(
        state["task_analysis"],
        state["input_message"]
    )
    
    state["selected_tools"] = selected_tools
    state["processing_steps"].append("tool_selection")
    
    return state

# ノード5: ツール実行（条件付き）
async def execute_tools_node(state: AIState) -> AIState:
    """選択されたツールを実行"""
    from app.tool_registry import ToolRegistry
    
    tool_registry = ToolRegistry()
    
    tool_results = []
    for tool_name in state["selected_tools"]:
        result = await tool_registry.execute_tool(
            tool_name,
            state["input_message"],
            state
        )
        tool_results.append({
            "tool": tool_name,
            "result": result
        })
    
    state["tool_results"] = tool_results
    state["processing_steps"].append("tool_execution")
    
    return state

# ノード6: LLM推論
async def llm_inference_node(state: AIState) -> AIState:
    """LLMで推論を実行"""
    from app.router import AIRouter
    
    ai_router = AIRouter(
        phi3_url=os.getenv("PHI3_URL"),
        qwen_url=os.getenv("QWEN_URL")
    )
    
    # コンテキストを構築
    context_parts = []
    
    # 重要記憶
    if state["important_memories"]:
        context_parts.append("重要な記憶:")
        for mem in state["important_memories"]:
            context_parts.append(f"- {mem['content']}")
    
    # 長期記憶
    if state["long_term_context"]:
        context_parts.append("過去の会話:")
        for ctx in state["long_term_context"]:
            context_parts.append(f"- {ctx['user_message']}")
    
    # ツール結果
    if "tool_results" in state:
        context_parts.append("ツール実行結果:")
        for tr in state["tool_results"]:
            context_parts.append(f"- {tr['tool']}: {tr['result']}")
    
    context = "\n".join(context_parts) if context_parts else ""
    
    # Intent分類
    intent = await ai_router.classify_intent(state["input_message"])
    
    # プロンプト構築
    if state["emotion"]:
        emotion_prompt = f"現在の感情状態: {state['emotion'].get('mood', 'neutral')}\n"
    else:
        emotion_prompt = ""
    
    message = f"{emotion_prompt}コンテキスト:\n{context}\n\nユーザー入力:\n{state['input_message']}"
    
    # LLM実行
    response = await ai_router.send_to_ai(
        model="qwen",
        message=message,
        context=[]
    )
    
    state["llm_response"] = response
    state["processing_steps"].append("llm_inference")
    
    return state

# ノード7: 記憶保存
async def save_memory_node(state: AIState) -> AIState:
    """記憶を保存"""
    from app.short_term_memory import ShortTermMemory
    from app.memory_organizer import MemoryOrganizer
    from app.conversation_summarizer import ConversationSummarizer
    from app.router import AIRouter
    
    # 短期記憶更新
    short_term = ShortTermMemory()
    short_term.add_recent_message(state["user_id"], state["input_message"])
    short_term.update_state(
        state["user_id"],
        emotion=state["emotion"].get("mood", "neutral")
    )
    
    # 重要情報抽出・保存
    mem0 = MemoryOrganizer()
    important_info = await mem0.extract_important_info(
        state["llm_response"],
        state["user_id"]
    )
    for info in important_info:
        await mem0.save_memory(
            content=info["content"],
            user_id=state["user_id"],
            importance=info["importance"],
            category=info["category"]
        )
    
    state["processing_steps"].append("memory_save")
    
    return state

# ノード8: 最終応答生成
async def generate_final_response_node(state: AIState) -> AIState:
    """最終応答を生成"""
    state["final_response"] = state["llm_response"]
    state["processing_steps"].append("final_response")
    
    return state

# 条件付きエッジ: ツール実行が必要か判断
def should_execute_tools(state: AIState) -> str:
    """ツール実行が必要か判断"""
    if state.get("selected_tools"):
        return "execute_tools"
    return "llm_inference"
```

#### LangGraphオーケストレーター

```python
# app/langgraph_orchestrator.py

import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from app.graph_nodes import (
    AIState,
    update_emotion_node,
    search_memory_node,
    analyze_task_node,
    select_tools_node,
    execute_tools_node,
    llm_inference_node,
    save_memory_node,
    generate_final_response_node,
    should_execute_tools
)

logger = logging.getLogger(__name__)

class LangGraphOrchestrator:
    """LangGraphによる思考フローオーケストレーション"""
    
    def __init__(self):
        self.graph = self._build_graph()
        logger.info("LangGraphオーケストレーター初期化完了")
    
    def _build_graph(self) -> StateGraph:
        """グラフを構築"""
        graph = StateGraph(AIState)
        
        # ノード追加
        graph.add_node("emotion_update", update_emotion_node)
        graph.add_node("memory_search", search_memory_node)
        graph.add_node("task_analysis", analyze_task_node)
        graph.add_node("tool_selection", select_tools_node)
        graph.add_node("execute_tools", execute_tools_node)
        graph.add_node("llm_inference", llm_inference_node)
        graph.add_node("memory_save", save_memory_node)
        graph.add_node("final_response", generate_final_response_node)
        
        # エッジ設定
        graph.set_entry_point("emotion_update")
        graph.add_edge("emotion_update", "memory_search")
        graph.add_edge("memory_search", "task_analysis")
        graph.add_edge("task_analysis", "tool_selection")
        
        # 条件付きエッジ
        graph.add_conditional_edges(
            "tool_selection",
            should_execute_tools,
            {
                "execute_tools": "execute_tools",
                "llm_inference": "llm_inference"
            }
        )
        
        graph.add_edge("execute_tools", "llm_inference")
        graph.add_edge("llm_inference", "memory_save")
        graph.add_edge("memory_save", "final_response")
        graph.add_edge("final_response", END)
        
        return graph.compile()
    
    async def process_message(
        self,
        user_id: str,
        message: str,
        initial_emotion: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        メッセージを処理
        
        Returns:
            最終状態
        """
        # 初期状態
        initial_state: AIState = {
            "user_id": user_id,
            "input_message": message,
            "emotion": initial_emotion or {"mood": "neutral", "energy": 50},
            "short_term_context": {},
            "long_term_context": [],
            "important_memories": [],
            "task_analysis": {},
            "selected_tools": [],
            "llm_response": "",
            "final_response": "",
            "processing_steps": []
        }
        
        # グラフ実行
        final_state = await self.graph.ainvoke(initial_state)
        
        logger.info(
            f"処理完了: {user_id} | "
            f"ステップ数: {len(final_state['processing_steps'])} | "
            f"感情: {final_state['emotion'].get('mood')}"
        )
        
        return final_state
```

#### LangGraphサービス実装

```python
# langgraph/app/main.py

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any, Optional
import logging

app = FastAPI(title="LangGraph Service")
logger = logging.getLogger(__name__)

class ProcessRequest(BaseModel):
    user_id: str
    message: str
    initial_emotion: Optional[Dict[str, Any]] = None

class ProcessResponse(BaseModel):
    final_response: str
    emotion: Dict[str, Any]
    processing_steps: list[str]
    task_analysis: Dict[str, Any]

# 実際のグラフはFastAPI側で実装するため、
# このサービスはプレースホルダー
@app.post("/process")
async def process_message(request: ProcessRequest) -> ProcessResponse:
    """メッセージを処理（プレースホルダー）"""
    logger.info(f"処理リクエスト: {request.user_id}")
    
    return ProcessResponse(
        final_response="プレースホルダー応答",
        emotion={"mood": "neutral", "energy": 50},
        processing_steps=["placeholder"],
        task_analysis={}
    )
```

#### LangGraph Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8081"]
```

#### LangGraph requirements.txt

```
fastapi==0.115.0
uvicorn==0.30.0
langgraph==0.2.0
langchain==0.3.0
pydantic==2.9.0
```

---

### 2. Emotion System（感情管理）

#### 役割
- 人格と会話の安定化
- Unityとの感情連携
- 感情状態の永続化

#### 感情データ構造

```python
{
    "mood": "happy",              # 主要な感情
    "energy": 70,                 # エネルギーレベル (0-100)
    "focus": "Unity",             # 現在のフォーカス
    "engagement": "high",         # エンゲージメント
    "valence": 0.8,               # 快・不快 (-1.0 ~ 1.0)
    "arousal": 0.6,               # 覚醒度 (0.0 ~ 1.0)
    "last_updated": "2026-05-27T20:30:00"
}
```

#### 感情カテゴリ

```python
# 主要な感情
MOODS = [
    "happy",      # 喜び
    "sad",        # 悲しみ
    "angry",      # 怒り
    "fear",       # 恐怖
    "surprise",   # 驚き
    "disgust",    # 嫌悪
    "neutral",    # 中立
    "thinking",   # 思考中
    "excited",    # 興奮
    "calm"        # 落ち着き
]

# エンゲージメントレベル
ENGAGEMENT_LEVELS = ["low", "medium", "high"]
```

#### 実装

```python
# app/emotion_manager.py

import logging
from typing import Dict, Any, Optional
from datetime import datetime
import re

logger = logging.getLogger(__name__)

class EmotionManager:
    """感情管理システム"""
    
    def __init__(self):
        self.emotion_keywords = {
            "happy": ["嬉しい", "楽しい", "好き", "すごい", "わーい", "やったー"],
            "sad": ["悲しい", "辛い", "寂しい", "つらい", "泣きたい"],
            "angry": ["怒ってる", "腹立つ", "むかつく", "最悪", "許せない"],
            "fear": ["怖い", "不安", "心配", "恐い", "ヒヤッとする"],
            "surprise": ["驚いた", "えっ", "まさか", "信じられない", "びっくり"],
            "thinking": ["考えて", "検討", "分析", "調べて", "どうすれば"],
            "excited": ["興奮", "ワクワク", "たのしみ", "楽しみ"],
            "calm": ["落ち着く", "平静", "安らぎ", "穏やか"]
        }
    
    def update_from_input(
        self,
        input_text: str,
        current_emotion: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        入力テキストから感情を更新
        
        Args:
            input_text: ユーザー入力
            current_emotion: 現在の感情状態
        
        Returns:
            更新後の感情状態
        """
        # 感情キーワード検出
        detected_mood = self._detect_mood(input_text)
        
        # エネルギー更新
        energy_change = self._calculate_energy_change(input_text, detected_mood)
        new_energy = self._clamp(current_emotion.get("energy", 50) + energy_change, 0, 100)
        
        # Valence/Arousal更新
        valence, arousal = self._calculate_va(detected_mood, input_text)
        
        # エンゲージメント更新
        engagement = self._calculate_engagement(input_text, new_energy)
        
        # フォーカス更新
        focus = self._update_focus(input_text, current_emotion.get("focus"))
        
        # 感情の緩やかな変化（慣性）
        if detected_mood == "neutral":
            detected_mood = current_emotion.get("mood", "neutral")
        
        updated_emotion = {
            "mood": detected_mood,
            "energy": new_energy,
            "focus": focus,
            "engagement": engagement,
            "valence": valence,
            "arousal": arousal,
            "last_updated": datetime.now().isoformat()
        }
        
        logger.info(
            f"感情更新: {current_emotion.get('mood')} -> {detected_mood} | "
            f"エネルギー: {new_energy}"
        )
        
        return updated_emotion
    
    def _detect_mood(self, text: str) -> str:
        """テキストから感情を検出"""
        text_lower = text.lower()
        
        max_score = 0
        detected = "neutral"
        
        for mood, keywords in self.emotion_keywords.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > max_score:
                max_score = score
                detected = mood
        
        return detected
    
    def _calculate_energy_change(self, text: str, mood: str) -> int:
        """エネルギー変化を計算"""
        # 感情によるエネルギー変化
        mood_energy = {
            "happy": 10,
            "excited": 20,
            "angry": 15,
            "fear": 10,
            "surprise": 15,
            "sad": -10,
            "calm": -5,
            "thinking": 5,
            "neutral": 0
        }
        
        change = mood_energy.get(mood, 0)
        
        # 文字数による調整（長い入力はエネルギー消費）
        if len(text) > 100:
            change -= 5
        
        return change
    
    def _calculate_va(self, mood: str, text: str) -> tuple[float, float]:
        """Valence（快・不快）とArousal（覚醒）を計算"""
        # Valence: 快(-1) ~ 不快(1)
        valence_map = {
            "happy": 0.8,
            "excited": 0.9,
            "sad": -0.7,
            "angry": -0.6,
            "fear": -0.5,
            "surprise": 0.3,
            "calm": 0.5,
            "thinking": 0.1,
            "neutral": 0.0
        }
        
        # Arousal: 覚醒度(0) ~ 覚醒(1)
        arousal_map = {
            "excited": 0.9,
            "angry": 0.8,
            "fear": 0.8,
            "surprise": 0.9,
            "happy": 0.6,
            "thinking": 0.4,
            "sad": 0.3,
            "calm": 0.1,
            "neutral": 0.2
        }
        
        return valence_map.get(mood, 0.0), arousal_map.get(mood, 0.2)
    
    def _calculate_engagement(self, text: str, energy: int) -> str:
        """エンゲージメントを計算"""
        if energy > 70:
            return "high"
        elif energy > 40:
            return "medium"
        return "low"
    
    def _update_focus(self, text: str, current_focus: str) -> str:
        """フォーカスを更新"""
        # キーワードベースのフォーカス検出
        focus_keywords = {
            "Unity": ["unity", "ゲーム", "3d", "シーン", "オブジェクト"],
            "プログラミング": ["コード", "プログラム", "関数", "クラス", "実装"],
            "デザイン": ["デザイン", "ui", "ux", "色", "レイアウト"],
            "一般": ["こんにちは", "ありがとう", "どうも"]
        }
        
        text_lower = text.lower()
        
        for focus, keywords in focus_keywords.items():
            if any(kw in text_lower for kw in keywords):
                return focus
        
        return current_focus
    
    def _clamp(self, value: int, min_val: int, max_val: int) -> int:
        """値を範囲内にクランプ"""
        return max(min_val, min(value, max_val))
    
    def get_unity_animation_params(self, emotion: Dict[str, Any]) -> Dict[str, Any]:
        """
        Unity用のアニメーションパラメータを生成
        
        Returns:
            {
                "expression": "happy",
                "animation_speed": 1.2,
                "voice_pitch": 1.1
            }
        """
        mood = emotion.get("mood", "neutral")
        energy = emotion.get("energy", 50)
        
        # 表情マッピング
        expression_map = {
            "happy": "smile",
            "sad": "sad",
            "angry": "angry",
            "surprise": "surprised",
            "thinking": "thinking",
            "excited": "excited",
            "calm": "calm",
            "neutral": "neutral"
        }
        
        # アニメーション速度（エネルギーに応じて）
        animation_speed = 0.5 + (energy / 100.0)
        
        # 音声ピッチ（エネルギーに応じて）
        voice_pitch = 0.8 + (energy / 250.0)
        
        return {
            "expression": expression_map.get(mood, "neutral"),
            "animation_speed": round(animation_speed, 2),
            "voice_pitch": round(voice_pitch, 2),
            "energy": energy
        }
    
    def decay_emotion(self, emotion: Dict[str, Any]) -> Dict[str, Any]:
        """
        感情の減衰（時間経過による）
        """
        # エネルギーを徐々に減少
        new_energy = max(30, emotion.get("energy", 50) - 5)
        
        # 中立に近づける
        if emotion["mood"] not in ["neutral", "calm"]:
            # 確率的に中立に戻る
            import random
            if random.random() < 0.1:
                emotion["mood"] = "neutral"
        
        emotion["energy"] = new_energy
        emotion["last_updated"] = datetime.now().isoformat()
        
        return emotion
```

---

## FastAPIへの統合

### main.pyの更新

```python
# app/main.pyに追加

from app.langgraph_orchestrator import LangGraphOrchestrator
from app.emotion_manager import EmotionManager

# 環境変数追加
LANGGRAPH_URL = os.getenv("LANGGRAPH_URL", "http://langgraph:8081")

# 初期化
langgraph_orchestrator = LangGraphOrchestrator()
emotion_manager = EmotionManager()

# startupイベントで初期化確認
@app.on_event("startup")
async def startup_event():
    # 既存の初期化...
    
    # LangGraph確認
    logger.info("  LangGraph: 初期化完了")
    
    # Emotion Manager確認
    logger.info("  Emotion Manager: 初期化完了")
```

### chatエンドポイントの更新

```python
@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    start_time = time.time()
    user_id = request.user_id
    
    # =========================================
    # LangGraphによる処理
    # =========================================
    
    # 現在の感情状態を取得
    current_state = short_term_memory.get_state(user_id)
    current_emotion = current_state.get("emotion", {"mood": "neutral", "energy": 50})
    
    # LangGraphで処理
    final_state = await langgraph_orchestrator.process_message(
        user_id=user_id,
        message=request.message,
        initial_emotion=current_emotion
    )
    
    # =========================================
    # レスポンス構築
    # =========================================
    
    # 最終応答
    ai_response = final_state["final_response"]
    
    # 感情状態を更新
    updated_emotion = final_state["emotion"]
    short_term_memory.update_state(
        user_id,
        emotion=updated_emotion.get("mood", "neutral")
    )
    
    # Unity用アニメーションパラメータ
    unity_params = emotion_manager.get_unity_animation_params(updated_emotion)
    
    processing_time = round(time.time() - start_time, 3)
    
    logger.info(
        f"[{user_id}] 応答完了 ({processing_time}秒) | "
        f"感情: {updated_emotion.get('mood')} | "
        f"ステップ: {len(final_state['processing_steps'])}"
    )
    
    return ChatResponse(
        response=ai_response,
        model_used="langgraph:qwen",
        processing_time=processing_time,
        context_used=len(final_state["long_term_context"]) > 0,
        web_search_used=False,
        requires_confirmation=False,
        search_in_progress=False,
        # 拡張フィールド
        emotion=updated_emotion,
        unity_params=unity_params,
        processing_steps=final_state["processing_steps"]
    )
```

---

## 新規APIエンドポイント

```python
# 感情関連
@app.get("/api/emotion/state")
async def get_emotion_state(user_id: str = "default_user"):
    """感情状態を取得"""
    state = short_term_memory.get_state(user_id)
    emotion = state.get("emotion", {"mood": "neutral", "energy": 50})
    return {"user_id": user_id, "emotion": emotion}

@app.post("/api/emotion/update")
async def update_emotion(
    user_id: str = "default_user",
    mood: Optional[str] = None,
    energy: Optional[int] = None
):
    """感情状態を手動更新"""
    current_state = short_term_memory.get_state(user_id)
    current_emotion = current_state.get("emotion", {"mood": "neutral", "energy": 50})
    
    if mood:
        current_emotion["mood"] = mood
    if energy is not None:
        current_emotion["energy"] = energy
    
    short_term_memory.update_state(user_id, emotion=current_emotion["mood"])
    
    return {"status": "updated", "emotion": current_emotion}

@app.get("/api/emotion/unity-params")
async def get_unity_params(user_id: str = "default_user"):
    """Unity用アニメーションパラメータを取得"""
    state = short_term_memory.get_state(user_id)
    emotion = state.get("emotion", {"mood": "neutral", "energy": 50})
    params = emotion_manager.get_unity_animation_params(emotion)
    return {"user_id": user_id, "params": params}

# LangGraph関連
@app.get("/api/graph/status")
async def get_graph_status():
    """LangGraphの状態を取得"""
    return {"status": "active", "nodes": 8}

@app.post("/api/graph/process")
async def process_with_graph(
    message: str,
    user_id: str = "default_user"
):
    """LangGraphで処理（デバッグ用）"""
    current_state = short_term_memory.get_state(user_id)
    current_emotion = current_state.get("emotion", {"mood": "neutral", "energy": 50})
    
    result = await langgraph_orchestrator.process_message(
        user_id=user_id,
        message=message,
        initial_emotion=current_emotion
    )
    
    return {
        "final_response": result["final_response"],
        "emotion": result["emotion"],
        "processing_steps": result["processing_steps"],
        "task_analysis": result["task_analysis"]
    }
```

---

## Unity連携拡張

### WebSocketメッセージ

```csharp
// Unity側の実装例

public class EmotionManager : MonoBehaviour
{
    private AIManager aiManager;
    
    void Start()
    {
        aiManager = GetComponent<AIManager>();
        aiManager.OnMessageReceived += HandleAIResponse;
    }
    
    void HandleAIResponse(string json)
    {
        var response = JsonUtility.FromJson<AIResponse>(json);
        
        // 感情状態を適用
        if (response.emotion != null)
        {
            ApplyEmotion(response.emotion);
        }
        
        // Unityパラメータを適用
        if (response.unity_params != null)
        {
            ApplyUnityParams(response.unity_params);
        }
    }
    
    void ApplyEmotion(EmotionData emotion)
    {
        // 表情アニメーション
        Animator animator = GetComponent<Animator>();
        animator.SetTrigger(emotion.mood);
        
        // 音声ピッチ
        AudioSource audioSource = GetComponent<AudioSource>();
        audioSource.pitch = emotion.voice_pitch;
    }
    
    void ApplyUnityParams(UnityParams params)
    {
        Animator animator = GetComponent<Animator>();
        animator.SetFloat("Speed", params.animation_speed);
        animator.SetTrigger(params.expression);
    }
}

[System.Serializable]
public class AIResponse
{
    public string response;
    public EmotionData emotion;
    public UnityParams unity_params;
}

[System.Serializable]
public class EmotionData
{
    public string mood;
    public int energy;
}

[System.Serializable]
public class UnityParams
{
    public string expression;
    public float animation_speed;
    public float voice_pitch;
}
```

---

## テスト計画

### ユニットテスト

```python
# tests/test_emotion_manager.py

import pytest
from app.emotion_manager import EmotionManager

def test_detect_mood():
    manager = EmotionManager()
    
    assert manager._detect_mood("嬉しい！") == "happy"
    assert manager._detect_mood("悲しいな") == "sad"
    assert manager._detect_mood("普通の会話") == "neutral"

def test_update_from_input():
    manager = EmotionManager()
    
    current = {"mood": "neutral", "energy": 50}
    updated = manager.update_from_input("すごく嬉しい！", current)
    
    assert updated["mood"] == "happy"
    assert updated["energy"] > 50

def test_get_unity_animation_params():
    manager = EmotionManager()
    
    emotion = {"mood": "happy", "energy": 80}
    params = manager.get_unity_animation_params(emotion)
    
    assert params["expression"] == "smile"
    assert params["animation_speed"] > 1.0
```

### 統合テスト

```python
# tests/test_langgraph_integration.py

import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_langgraph_processing():
    from app.langgraph_orchestrator import LangGraphOrchestrator
    
    orchestrator = LangGraphOrchestrator()
    
    result = await orchestrator.process_message(
        user_id="test_user",
        message="Unityでゲームを作っています",
        initial_emotion={"mood": "neutral", "energy": 50}
    )
    
    assert result["final_response"]
    assert result["emotion"]["mood"]
    assert len(result["processing_steps"]) > 0
```

---

## デプロイ手順

### 1. LangGraphサービス構築

```bash
cd 01_main
mkdir -p langgraph/app
# Dockerfile, requirements.txt, main.pyを作成
docker-compose build langgraph
docker-compose up -d langgraph
```

### 2. FastAPI更新

```bash
cd fastapi
# requirements.txtにlanggraph, langchainを追加
pip install -r requirements.txt

# 新規モジュールを作成
# app/langgraph_orchestrator.py
# app/emotion_manager.py
# app/graph_nodes.py

# main.pyを更新
```

### 3. 環境変数設定

```bash
# .envに追加
LANGGRAPH_URL=http://langgraph:8081
```

### 4. 再起動

```bash
docker-compose up -d fastapi
```

---

## 依存関係

```
Phase2コンポーネントの依存関係:

LangGraph
  ├─ Phase1 (Redis, Mem0)
  ├─ Phase3 (Task Manager, Tool Registry) - 将来
  └─ LLM (Phi3/Qwen)

Emotion System
  ├─ Redis (状態保存)
  └─ Unity (連携)

FastAPI main.py
  ├─ LangGraphOrchestrator
  └─ EmotionManager
```

---

## 次のステップ

Phase2完了後、以下を確認:
- LangGraphが正常に動作しているか
- 感情状態が正しく更新されているか
- Unityとの連携が機能しているか
- 思考フローの各ノードが正しく実行されているか

確認後、Phase3（Task Manager, Tool Calling）へ進む。
