# システム拡張アーキテクチャ設計

## 概要

現在の単純チャットAIから、ChatGPT/Claude系の長期記憶+タスク管理AIへ進化させるための全体設計。

Unityは「UI専用」とし、AIの思考・記憶・タスク処理はDockerコンテナ側で管理する。

---

## 現在のシステム構造

### 既存コンポーネント

```
Unity (UI専用)
  ↓ WebSocket
FastAPI (制御サーバー)
  ↓ HTTP
├─ Phi3 (Intent分類)
├─ Qwen (実行AI)
└─ ChromaDB (長期記憶・ベクトル検索)
```

### 現在のフロー

```
ユーザー入力
  ↓
FastAPI受信
  ↓
Phi3でIntent分類 (chat/code/fix/idea)
  ↓
Qwenで応答生成
  ↓
ChromaDBに保存
  ↓
Unityへ返送
```

---

## 拡張後のシステム構造

### 新コンポーネント追加

```
Unity (UI専用)
  ↓ WebSocket
FastAPI (制御サーバー)
  ↓
LangGraph (AI思考フロー制御)
  ↓
├─ Redis (短期記憶)
├─ Mem0 (記憶整理・要約)
├─ ChromaDB (長期記憶・ベクトル検索)
├─ Emotion System (感情管理)
├─ Task Manager (タスク管理)
├─ Tool Registry (ツール登録)
│  ├─ Web Search (SearxNG)
│  ├─ File Operations
│  ├─ Git Operations
│  ├─ Docker Operations
│  └─ Unity Control
├─ Whisper (音声認識)
├─ Piper (音声合成)
└─ MCP (Model Context Protocol - 将来拡張)
     ↓
Phi3/Qwen (LLM推論)
```

---

## 拡張後の思考フロー

### LangGraphによる構造化フロー

```
入力 (テキスト/音声)
  ↓
【感情更新】Emotion System
  ├─ 現在の感情状態を更新
  └─ Unityへ感情状態を送信
  ↓
【短期記憶更新】Redis
  ├─ current_topic, emotion, recent_messages
  └─ active_taskを更新
  ↓
【記憶検索】Mem0 + ChromaDB
  ├─ Mem0: 重要情報を検索
  ├─ ChromaDB: ベクトル検索
  └─ 関連コンテキストを統合
  ↓
【タスク判断】Task Manager
  ├─ 新規タスクか判断
  ├─ タスク分解
  └─ 優先順位付け
  ↓
【ツール選択】Tool Registry
  ├─ Web検索が必要か？
  ├─ ファイル操作が必要か？
  ├─ Git操作が必要か？
  └─ 必要なツールを呼び出し
  ↓
【LLM思考】Phi3/Qwen
  ├─ コンテキスト + ツール結果
  └─ 応答生成
  ↓
【記憶保存】Mem0 + ChromaDB
  ├─ Mem0: 重要情報を抽出・保存
  ├─ ChromaDB: ベクトル化して保存
  └─ 会話要約を生成
  ↓
【応答返送】Unity
  ├─ テキスト応答
  ├─ 感情状態
  └─ タスク状態
```

---

## データフロー図

### 記憶の階層構造

```
┌─────────────────────────────────────┐
│   Unity UI (表示・入力のみ)          │
└──────────────┬──────────────────────┘
               │ WebSocket
┌──────────────▼──────────────────────┐
│   FastAPI + LangGraph               │
│   (思考フロー制御)                    │
└──────┬──────────────────────────┬───┘
       │                          │
┌──────▼──────────┐    ┌─────────▼──────────┐
│  Redis          │    │  Mem0              │
│  (短期記憶)      │    │  (記憶整理・要約)   │
│  - 会話状態      │    │  - 重要情報抽出    │
│  - 感情状態      │    │  - 会話要約        │
│  - 直近メッセージ│    │  - 優先順位付け    │
└─────────────────┘    └───────────────────┘
       │                          │
       └──────────┬───────────────┘
                  │
         ┌────────▼─────────┐
         │  ChromaDB        │
         │  (長期記憶)      │
         │  - ベクトル検索   │
         │  - 会話履歴      │
         └──────────────────┘
```

---

## Phase別実装計画

### Phase1: 基礎記憶層の強化

**目的**: 短期記憶と記憶整理システムの導入

**追加コンポーネント**:
- Redis (短期記憶)
- Mem0 (記憶整理)
- 会話要約機能

**Dockerサービス追加**:
```yaml
redis:
  image: redis:7-alpine
  ports: ["6379:6379"]
  volumes: ["../02_logs/redis_data:/data"]

mem0:
  build: ./mem0
  environment:
    - REDIS_URL=redis://redis:6379
    - CHROMA_HOST=chromadb
```

**FastAPIモジュール追加**:
- `app/short_term_memory.py` (Redisラッパー)
- `app/memory_organizer.py` (Mem0連携)
- `app/conversation_summarizer.py` (会話要約)

**データ構造**:
```json
// Redisキー構造
user:{user_id}:state -> {
  "current_topic": "Unity開発",
  "emotion": "thinking",
  "recent_messages": [],
  "active_task": null
}

user:{user_id}:session -> {
  "start_time": "2026-05-27T20:00:00",
  "message_count": 15
}
```

---

### Phase2: 思考フローの構造化

**目的**: LangGraphによるAI思考手順の構造化

**追加コンポーネント**:
- LangGraph (思考フロー制御)
- Emotion System (感情管理)

**Dockerサービス追加**:
```yaml
langgraph:
  build: ./langgraph
  environment:
    - REDIS_URL=redis://redis:6379
    - PHI3_URL=http://phi3:8001
    - QWEN_URL=http://qwen:8002
```

**FastAPIモジュール追加**:
- `app/langgraph_orchestrator.py` (LangGraph統合)
- `app/emotion_manager.py` (感情管理)
- `app/graph_nodes.py` (LangGraphノード定義)

**LangGraphノード構成**:
```python
graph = StateGraph(AIState)

# ノード定義
graph.add_node("emotion_update", update_emotion_node)
graph.add_node("memory_search", search_memory_node)
graph.add_node("task_analysis", analyze_task_node)
graph.add_node("tool_selection", select_tools_node)
graph.add_node("llm_inference", llm_inference_node)
graph.add_node("memory_save", save_memory_node)

# エッジ定義
graph.set_entry_point("emotion_update")
graph.add_edge("emotion_update", "memory_search")
graph.add_edge("memory_search", "task_analysis")
graph.add_conditional_edges("task_analysis", route_to_tools)
```

**感情状態データ構造**:
```json
{
  "mood": "happy",
  "energy": 70,
  "focus": "Unity",
  "engagement": "high",
  "last_updated": "2026-05-27T20:30:00"
}
```

**Unity連携**:
- WebSocketで感情状態をリアルタイム送信
- Unity側で表情・アニメーション・音声を変更

---

### Phase3: タスク管理とツール呼び出し

**目的**: AIに作業能力を持たせる

**追加コンポーネント**:
- Task Manager (タスク管理)
- Tool Calling System (ツール呼び出し)

**FastAPIモジュール追加**:
- `app/task_manager.py` (タスク管理)
- `app/tool_registry.py` (ツール登録)
- `app/tools/` (ツール実装ディレクトリ)
  - `web_search_tool.py`
  - `file_tool.py`
  - `git_tool.py`
  - `docker_tool.py`
  - `unity_tool.py`

**タスクデータ構造**:
```json
{
  "task_id": "task_001",
  "title": "README修正",
  "description": "READMEの内容を確認して修正する",
  "status": "in_progress",
  "priority": "high",
  "subtasks": [
    {"id": "st1", "title": "内容確認", "status": "completed"},
    {"id": "st2", "title": "修正文生成", "status": "in_progress"},
    {"id": "st3", "title": "Git確認", "status": "pending"},
    {"id": "st4", "title": "commit提案", "status": "pending"}
  ],
  "created_at": "2026-05-27T20:00:00",
  "updated_at": "2026-05-27T20:30:00"
}
```

**ツール定義例**:
```python
@tool
def web_search(query: str) -> str:
    """Web検索を実行する"""
    # SearxNG API呼び出し
    pass

@tool
def read_file(path: str) -> str:
    """ファイルを読み込む"""
    pass

@tool
def git_status() -> str:
    """Gitステータスを取得"""
    pass
```

---

### Phase4: マルチモーダル対応

**目的**: 音声入出力とWeb検索の強化

**追加コンポーネント**:
- SearxNG (プライベートWeb検索)
- Whisper (音声認識)
- Piper (音声合成)

**Dockerサービス追加**:
```yaml
searxng:
  image: searxng/searxng:latest
  ports: ["8080:8080"]
  volumes: ["./searxng/settings.yml:/etc/searxng/settings.yml"]

whisper:
  build: ./whisper
  environment:
    - MODEL_PATH=/models/whisper
  volumes: ["../03_models/whisper:/models/whisper"]

piper:
  build: ./piper
  environment:
    - MODEL_PATH=/models/piper
  volumes: ["../03_models/piper:/models/piper"]
```

**FastAPIモジュール追加**:
- `app/voice_input.py` (Whisper連携)
- `app/voice_output.py` (Piper連携)
- `app/searxng_client.py` (SearxNG連携)

**音声フロー**:
```
音声入力
  ↓
Whisper (音声→テキスト)
  ↓
LangGraphフロー
  ↓
Piper (テキスト→音声)
  ↓
音声出力
```

---

### Phase5: 高度な拡張

**目的**: 外部ツール統合と自律エージェント化

**追加コンポーネント**:
- MCP (Model Context Protocol)
- Vision (画像認識)
- 自律エージェント

**Dockerサービス追加**:
```yaml
mcp-server:
  build: ./mcp-server
  ports: ["3000:3000"]
```

**FastAPIモジュール追加**:
- `app/mcp_client.py` (MCPクライアント)
- `app/vision_processor.py` (画像処理)
- `app/autonomous_agent.py` (自律エージェント)

**MCP対応ツール**:
- VSCode
- GitHub
- Browser
- FileSystem
- Unity

---

## Docker Compose全体構成

```yaml
version: '3.8'

services:
  # 既存サービス
  fastapi:
    build: ./fastapi
    ports: ["8000:8000"]
    depends_on:
      - redis
      - mem0
      - langgraph
      - chromadb
    environment:
      - REDIS_URL=redis://redis:6379
      - MEM0_URL=http://mem0:8080
      - LANGGRAPH_URL=http://langgraph:8081
      - CHROMA_HOST=chromadb

  phi3:
    build: ./phi3
    # 既存設定

  qwen:
    build: ./qwen
    # 既存設定

  chromadb:
    image: chromadb/chroma:latest
    # 既存設定

  # Phase1
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    volumes: ["../02_logs/redis_data:/data"]

  mem0:
    build: ./mem0
    ports: ["8080:8080"]
    environment:
      - REDIS_URL=redis://redis:6379
      - CHROMA_HOST=chromadb

  # Phase2
  langgraph:
    build: ./langgraph
    ports: ["8081:8081"]
    environment:
      - REDIS_URL=redis://redis:6379
      - PHI3_URL=http://phi3:8001
      - QWEN_URL=http://qwen:8002

  # Phase3
  # Task Manager は FastAPI内で実装

  # Phase4
  searxng:
    image: searxng/searxng:latest
    ports: ["8082:8080"]

  whisper:
    build: ./whisper
    ports: ["8083:8000"]

  piper:
    build: ./piper
    ports: ["8084:8000"]

  # Phase5
  mcp-server:
    build: ./mcp-server
    ports: ["3000:3000"]

networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true
```

---

## ディレクトリ構成

```
local-ai-project/
├── 01_main/
│   ├── docker-compose.yml          # 更新
│   ├── fastapi/
│   │   ├── app/
│   │   │   ├── main.py             # 更新
│   │   │   ├── router.py           # 既存
│   │   │   ├── history.py          # 既存
│   │   │   ├── short_term_memory.py      # 新規
│   │   │   ├── memory_organizer.py       # 新規
│   │   │   ├── conversation_summarizer.py # 新規
│   │   │   ├── langgraph_orchestrator.py  # 新規
│   │   │   ├── emotion_manager.py         # 新規
│   │   │   ├── graph_nodes.py            # 新規
│   │   │   ├── task_manager.py           # 新規
│   │   │   ├── tool_registry.py          # 新規
│   │   │   ├── tools/                    # 新規ディレクトリ
│   │   │   │   ├── web_search_tool.py
│   │   │   │   ├── file_tool.py
│   │   │   │   ├── git_tool.py
│   │   │   │   ├── docker_tool.py
│   │   │   │   └── unity_tool.py
│   │   │   ├── voice_input.py            # 新規
│   │   │   ├── voice_output.py           # 新規
│   │   │   ├── searxng_client.py         # 新規
│   │   │   ├── mcp_client.py             # 新規
│   │   │   ├── vision_processor.py       # 新規
│   │   │   └── autonomous_agent.py       # 新規
│   │   └── requirements.txt       # 更新
│   ├── mem0/                     # 新規
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       └── main.py
│   ├── langgraph/                 # 新規
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       └── main.py
│   ├── whisper/                  # 新規
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       └── main.py
│   ├── piper/                    # 新規
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       └── main.py
│   ├── mcp-server/               # 新規
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       └── main.py
│   ├── phi3/                     # 既存
│   ├── qwen/                     # 既存
│   └── unity/                    # 既存
├── 02_logs/
│   ├── chroma_db/                # 既存
│   ├── conversations/            # 既存
│   ├── system/                   # 既存
│   ├── redis_data/               # 新規
│   └── mem0_data/                # 新規
├── 03_models/
│   ├── phi3/                     # 既存
│   ├── qwen/                     # 既存
│   ├── whisper/                  # 新規
│   └── piper/                    # 新規
└── docs/
    ├── ARCHITECTURE.md           # 既存
    ├── SYSTEM_EXTENSION_ARCHITECTURE.md  # 新規
    ├── PHASE1_DESIGN.md          # 新規
    ├── PHASE2_DESIGN.md          # 新規
    ├── PHASE3_DESIGN.md          # 新規
    ├── PHASE4_DESIGN.md          # 新規
    └── PHASE5_DESIGN.md          # 新規
```

---

## 依存パッケージ追加

### FastAPI requirements.txt 更新

```
# 既存
fastapi==0.115.0
uvicorn==0.30.0
httpx==0.27.0
numpy<2.0
chromadb>=1.0.0
pydantic==2.9.0
python-dotenv==1.0.1
aiofiles==23.2.1

# Phase1
redis==5.0.0
mem0ai==0.1.0

# Phase2
langgraph==0.2.0
langchain==0.3.0

# Phase3
# ツール関連は既存パッケージで対応可能

# Phase4
openai-whisper==20240930
piper-tts==1.2.0

# Phase5
mcp==0.1.0
pillow==10.0.0
```

---

## APIエンドポイント追加

### 新規エンドポイント

```
# 感情状態
GET  /api/emotion/state
POST /api/emotion/update

# タスク管理
GET    /api/tasks
POST   /api/tasks
PUT    /api/tasks/{task_id}
DELETE /api/tasks/{task_id}
POST   /api/tasks/{task_id}/complete

# ツール実行
POST /api/tools/execute

# 音声
POST /api/voice/transcribe  # Whisper
POST /api/voice/synthesize  # Piper

# MCP
GET  /api/mcp/tools
POST /api/mcp/invoke
```

---

## Unity連携拡張

### WebSocketメッセージ拡張

```json
// 既存
{
  "type": "chat_message",
  "data": {
    "message": "こんにちは",
    "user_id": "player_1"
  }
}

// 新規: 感情状態
{
  "type": "emotion_update",
  "data": {
    "mood": "happy",
    "energy": 70,
    "focus": "Unity"
  }
}

// 新規: タスク状態
{
  "type": "task_update",
  "data": {
    "task_id": "task_001",
    "status": "in_progress",
    "progress": 50
  }
}

// 新規: 音声
{
  "type": "voice_audio",
  "data": {
    "audio_data": "base64_encoded_audio",
    "duration": 3.5
  }
}
```

---

## 実装優先度と依存関係

```
Phase1 (基礎記憶)
  ├─ Redis (独立)
  ├─ Mem0 (Redis依存)
  └─ 会話要約 (Mem0依存)

Phase2 (思考フロー)
  ├─ LangGraph (Phase1依存)
  └─ Emotion System (LangGraph依存)

Phase3 (タスク管理)
  ├─ Task Manager (LangGraph依存)
  └─ Tool Calling (Task Manager依存)

Phase4 (マルチモーダル)
  ├─ SearxNG (独立)
  ├─ Whisper (独立)
  └─ Piper (独立)

Phase5 (高度拡張)
  ├─ MCP (Tool Calling依存)
  ├─ Vision (独立)
  └─ 自律Agent (全Phase依存)
```

---

## パフォーマンス考慮

### キャッシュ戦略
- Redis: 短期記憶キャッシュ (TTL: 1時間)
- Mem0: 重要情報キャッシュ (TTL: 24時間)
- ChromaDB: 長期記憶 (永続化)

### 並列処理
- 記憶検索 (Redis + ChromaDB) は並列実行
- ツール呼び出しは並列実行可能
- 音声処理はバックグラウンド実行

### リソース制限
- Phi3: 4GBメモリ
- Qwen: 8GBメモリ (GPU)
- Redis: 512MB
- Mem0: 2GB
- LangGraph: 1GB
- Whisper: 2GB
- Piper: 1GB

---

## セキュリティ考慮

### API認証
- 既存のAPIキー認証を維持
- MCP接続はトークン認証
- ツール実行は権限チェック

### データ保護
- Redisデータは暗号化 (Redis ACL)
- ChromaDBは内部ネットワークのみ
- ユーザーデータの分離 (user_id)

### 外部接続
- SearxNGはプライベートインスタンス
- Web検索はユーザー確認必須
- Git/Docker操作は制限付き

---

## テスト戦略

### ユニットテスト
- 各モジュールの単体テスト
- ツールの個別テスト
- LangGraphノードのテスト

### 統合テスト
- Phaseごとの統合テスト
- エンドツーエンドフローテスト
- Unity連携テスト

### 負荷テスト
- 同時接続テスト
- 長時間稼働テスト
- メモリリークチェック

---

## 次のステップ

各Phaseの詳細設計ドキュメントを作成:
1. Phase1_DESIGN.md (Redis, Mem0, 会話要約)
2. Phase2_DESIGN.md (LangGraph, Emotion System)
3. Phase3_DESIGN.md (Task Manager, Tool Calling)
4. Phase4_DESIGN.md (Web Search, Whisper, Piper)
5. Phase5_DESIGN.md (MCP, Vision, 自律Agent)
