# ローカルAI統合システム - README

## 📋 プロジェクト概要

このプロジェクトは、**複数のAIモデルをDocker環境で動作させるローカルAIシステム**です。軽量な会話AI（Phi3）と高性能な生成AI（Qwen）を目的に応じて使い分け、会話履歴管理機能を搭載しています。

### 🎯 主な特徴

- **デュアルAI構成**: Phi3（Intent分類用）と Qwen（実行用）の2段階処理
- **マイクロサービスアーキテクチャ**: Docker Composeで各サービスを独立管理
- **会話履歴管理**: ChromaDBを使用した継続的な記憶機能
- **ローカル実行**: インターネット不要でプライベートに実行可能

---

## 📁 ディレクトリ構成

```
local-ai-project/
│
├── 01_main/                          # 🌟 メインシステム
│   ├── docker-compose.yml            # サービス全体のオーケストレーション
│   ├── .env                          # 環境変数設定ファイル
│   │
│   ├── fastapi/                      # 🔌 制御サーバー（司令塔）
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py               # FastAPI メインアプリケーション
│   │       ├── router.py             # AI ルーター（Intent分類 + 振り分け）
│   │       └── history.py            # 会話履歴管理（ChromaDB連携）
│   │
│   ├── phi3/                         # 🧠 軽量AI（Intent分類専用）
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       └── main.py               # LLM推論エンドポイント
│   │
│   ├── qwen/                         # ⚡ 高性能AI（メイン処理用）
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       └── main.py               # LLM推論エンドポイント
│   │
│   └── mem0/                         # 💾 メモリ管理（開発中）
│       └── app/
│
├── 02_logs/                          # 📊 ログ・会話データ（実行時に作成）
│   ├── chroma_db/                    # ChromaDB永続化ストレージ
│   └── conversations/                # 会話ログ（JSON形式）
│
├── 03_models/                        # 🤖 AIモデルファイル保存先（モデル配置が必要）
│   ├── phi3/                         # Phi3 モデル（GGUF形式）
│   └── qwen/                         # Qwen モデル（GGUF形式）
│
├── config.json                       # 全体設定ファイル
└── README.md                         # 本ファイル
```

---

## 🔄 システムアーキテクチャ & 通信フロー

### **全体フロー図**

```
┌─────────────┐
│   クライアント  │ (HTTP/WebSocket)
└──────┬──────┘
       │ HTTP/WS
       │ ChatRequest (JSON)
       ▼
┌─────────────────────────────┐
│  FastAPI サーバー            │  ← 司令塔
│  (ポート: 8000)              │
│                             │
│ 1) リクエスト受信            │
│ 2) Intent分類を指示          │
│ 3) 実行AIに指示             │
│ 4) 会話履歴を保存            │
│ 5) レスポンスを返送          │
└──────┬──────────────────────┘
       │
       ├─ HTTP ──────────────────┐
       │                         │
       ▼                         ▼
┌──────────────┐         ┌──────────────┐
│   Phi3       │         │    Qwen      │
│  (ポート:8001) │         │  (ポート:8002) │
│              │         │              │
│ 役割:         │         │ 役割:        │
│ Intent分類   │         │ メイン処理   │
│ （軽量）      │         │ （高性能）   │
└──────────────┘         └──────────────┘
                         │
                         ├─ HTTP ──────────────┐
                         │                    │
                         ▼                    ▼
                   ┌──────────────┐
                   │   ChromaDB    │
                   │  会話履歴      │
                   │  メモリ保存    │
                   └──────────────┘
```

### **通信ステップ詳細**

#### **1️⃣ リクエスト段階 (クライアント → FastAPI)**
```json
{
  "message": "Pythonで階乗を計算する関数を作って",
  "user_id": "player_123",
  "force_model": null
}
```

#### **2️⃣ Intent分類段階 (FastAPI → Phi3)**
- FastAPI が Phi3 に「このメッセージのIntentは何か」と尋ねる
- Phi3 が分類結果を返す：`code`（コード実装）

#### **3️⃣ 実行段階 (FastAPI → Qwen)**
- FastAPIが Qwen に「[MODE: CODE] の指示」を付加して送信
- Qwen が詳細で実用的なコード例を生成

#### **4️⃣ 応答段階 (FastAPI → クライアント)**
```json
{
  "response": "def factorial(n):\n    return 1 if n <= 1 else n * factorial(n-1)",
  "model_used": "qwen",
  "processing_time": 2.34
}
```

---

## 🧠 Intent分類システム

FastAPI のルーターは、ユーザーの入力を **4つのIntentカテゴリ**に自動分類します：

| Intent | 対応モード | 説明 | 例 |
|--------|---------|------|-----|
| **chat** | [MODE: CHAT] | 雑談・情報提供 | 「今日の天気は？」 |
| **code** | [MODE: CODE] | コード実装・例 | 「リスト処理を教えて」 |
| **fix** | [MODE: FIX] | デバッグ・問題解決 | 「このエラーの修正方法は？」 |
| **idea** | [MODE: IDEA] | アイデア発想・企画 | 「ゲーム演出のアイデア」 |

**分類プロセス**:
1. Phi3 に「この入力は chat/code/fix/idea のどれ？」と問い合わせ
2. 失敗時は fallback ロジック（キーワード検索）で自動判定
3. 判定結果に応じた専用プロンプトを Qwen に送信

---

## 💬 会話履歴 & メモリ管理

### **ChromaDB統合**
- 会話ごとに **ユーザーID + 日時** で会話ログを作成
- ログは JSON Lines形式で `/02_logs/conversations/` に保存
  ```json
  {"timestamp": "2026-05-10T14:23:45", "user": "player_123", "message": "こんにちは", "response": "こんにちは！"}
  ```

### **ベクトル化＆メモリ**
- ChromaDB が会話をベクトル化し、"意味的な関連性"を学習
- 過去の会話から関連コンテキストを自動抽出
- メモリ上限：`config.json` の `memory.max_size` で調整可能（デフォルト1024ユニット）

---

## 🚀 セットアップ＆実行手順

### **前提条件**
- Docker / Docker Compose インストール済み
- モデルファイル（GGUF形式）をダウンロード済み

### **ステップ1: モデルファイルの配置**
```bash
# Phi3 モデル
mkdir -p 03_models/phi3
# → Phi-3-mini-4k-instruct-q4.gguf を配置

# Qwen モデル
mkdir -p 03_models/qwen
# → Qwen2.5-Coder-3B-4bit.gguf を配置
```

### **ステップ2: 環境変数の設定**
```bash
cd 01_main
cat > .env << EOF
# FastAPI設定
FASTAPI_PORT=8000
API_KEY=your-secret-key-here

# AIモデルURL
PHI3_URL=http://phi3:8001
QWEN_URL=http://qwen:8002

# ChromaDB
CHROMA_DATA_DIR=/app/logs/chroma_db

# ログ出力
LOG_LEVEL=INFO
EOF
```

### **ステップ3: Docker サービス起動**
```bash
cd 01_main
docker-compose up -d

# ログ確認
docker-compose logs -f fastapi
```

### **ステップ4: 動作確認**
```bash
# FastAPI は自動的にポート 8000 で起動
# http://localhost:8000/docs にアクセス → Swagger UI で API テスト可能

# 例：チャットリクエスト
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "こんにちは",
    "user_id": "test_user"
  }'
```

### **ステップ5: クライアントとの連携**
FastAPIサーバーはHTTP APIとWebSocketを提供します。クライアントアプリケーションから以下のエンドポイントにアクセス可能です：
- HTTP API: `http://localhost:8000/docs` (Swagger UI)
- WebSocket: `ws://localhost:8000/ws`

詳細なフロントエンド連携方法は以下のセクションを参照してください。

---

## 📡 WebSocket 通信仕様

### **接続確立**
```javascript
// JavaScriptの例
const ws = new WebSocket("ws://localhost:8000/ws");

ws.onopen = () => {
  console.log("接続成功");
};
```

### **メッセージ送信**
```json
{
  "type": "chat_message",
  "data": {
    "message": "Pythonを教えて",
    "user_id": "player_1"
  }
}
```

### **メッセージ受信**
```json
{
  "type": "chat_response",
  "data": {
    "response": "Pythonは...",
    "model_used": "qwen",
    "processing_time": 1.45
  }
}
```

### **接続終了**
```javascript
ws.close();
```

---

## 🎨 フロントエンド連携ガイド

このバックエンドシステムは、様々なフロントエンドアプリケーションから使用できます。以下に主要なプラットフォームでの実装例を示します。

### **Unity (C#) での実装**

UnityプロジェクトからこのAIシステムを使用する場合、以下の手順で実装します。

#### **1. 必要なパッケージのインストール**
UnityではWebSocket通信のために以下のパッケージが必要です：
- **WebSocketSharp** (NuGetパッケージ) または
- **UnityWebRequest** (Unity標準)

#### **2. AIManager.cs の実装**
```csharp
using UnityEngine;
using WebSocketSharp;
using Newtonsoft.Json;

public class AIManager : MonoBehaviour
{
    private WebSocket ws;
    private string serverUrl = "ws://localhost:8000/ws";
    private string userId = "unity_player";

    void Start()
    {
        ConnectToServer();
    }

    void ConnectToServer()
    {
        ws = new WebSocket(serverUrl);
        
        ws.OnOpen += (sender, e) => {
            Debug.Log("AIサーバーに接続しました");
        };
        
        ws.OnMessage += (sender, e) => {
            HandleResponse(e.Data);
        };
        
        ws.OnError += (sender, e) => {
            Debug.LogError("WebSocketエラー: " + e.Message);
        };
        
        ws.OnClose += (sender, e) => {
            Debug.Log("接続が閉じられました");
        };
        
        ws.Connect();
    }

    public void SendMessage(string message)
    {
        if (ws == null || !ws.IsAlive)
        {
            Debug.LogWarning("サーバーに接続されていません");
            return;
        }

        var request = new
        {
            type = "chat_message",
            data = new
            {
                message = message,
                user_id = userId
            }
        };

        string json = JsonConvert.SerializeObject(request);
        ws.Send(json);
    }

    void HandleResponse(string response)
    {
        var data = JsonConvert.DeserializeObject<dynamic>(response);
        
        if (data.type == "chat_response")
        {
            string aiResponse = data.data.response.ToString();
            string modelUsed = data.data.model_used.ToString();
            float processingTime = (float)data.data.processing_time;
            
            Debug.Log($"AI応答: {aiResponse}");
            Debug.Log($"使用モデル: {modelUsed}");
            Debug.Log($"処理時間: {processingTime}秒");
            
            // UIに表示するなどの処理
            // UIManager.Instance.DisplayResponse(aiResponse);
        }
    }

    void OnDestroy()
    {
        if (ws != null)
        {
            ws.Close();
            ws = null;
        }
    }
}
```

#### **3. UIManager.cs の実装例**
```csharp
using UnityEngine;
using UnityEngine.UI;

public class UIManager : MonoBehaviour
{
    public InputField inputField;
    public Text responseText;
    public Button sendButton;
    private AIManager aiManager;

    void Start()
    {
        aiManager = FindObjectOfType<AIManager>();
        sendButton.onClick.AddListener(OnSendButtonClick);
    }

    void OnSendButtonClick()
    {
        string message = inputField.text;
        if (!string.IsNullOrEmpty(message))
        {
            aiManager.SendMessage(message);
            inputField.text = "";
        }
    }

    public void DisplayResponse(string response)
    {
        responseText.text = response;
    }
}
```

### **Webアプリケーション (JavaScript/TypeScript) での実装**

#### **1. 基本的なWebSocket通信**
```javascript
class AIClient {
    constructor(serverUrl = 'ws://localhost:8000/ws') {
        this.ws = new WebSocket(serverUrl);
        this.userId = 'web_user_' + Date.now();
        this.setupEventListeners();
    }

    setupEventListeners() {
        this.ws.onopen = () => {
            console.log('AIサーバーに接続しました');
        };

        this.ws.onmessage = (event) => {
            const response = JSON.parse(event.data);
            this.handleResponse(response);
        };

        this.ws.onerror = (error) => {
            console.error('WebSocketエラー:', error);
        };

        this.ws.onclose = () => {
            console.log('接続が閉じられました');
        };
    }

    sendMessage(message) {
        const request = {
            type: 'chat_message',
            data: {
                message: message,
                user_id: this.userId
            }
        };
        this.ws.send(JSON.stringify(request));
    }

    handleResponse(response) {
        if (response.type === 'chat_response') {
            console.log('AI応答:', response.data.response);
            console.log('使用モデル:', response.data.model_used);
            console.log('処理時間:', response.data.processing_time);
            // UIに表示するなどの処理
        }
    }

    close() {
        this.ws.close();
    }
}

// 使用例
const aiClient = new AIClient();
aiClient.sendMessage('こんにちは');
```

#### **2. Reactコンポーネントの例**
```jsx
import React, { useState, useEffect, useRef } from 'react';

function AIChat() {
    const [messages, setMessages] = useState([]);
    const [input, setInput] = useState('');
    const [isConnected, setIsConnected] = useState(false);
    const wsRef = useRef(null);

    useEffect(() => {
        wsRef.current = new WebSocket('ws://localhost:8000/ws');
        const userId = 'react_user_' + Date.now();

        wsRef.current.onopen = () => {
            setIsConnected(true);
            console.log('AIサーバーに接続しました');
        };

        wsRef.current.onmessage = (event) => {
            const response = JSON.parse(event.data);
            if (response.type === 'chat_response') {
                setMessages(prev => [...prev, {
                    type: 'ai',
                    content: response.data.response,
                    model: response.data.model_used,
                    time: response.data.processing_time
                }]);
            }
        };

        wsRef.current.onerror = (error) => {
            console.error('WebSocketエラー:', error);
        };

        wsRef.current.onclose = () => {
            setIsConnected(false);
        };

        return () => {
            wsRef.current.close();
        };
    }, []);

    const handleSend = () => {
        if (!input.trim() || !isConnected) return;

        const message = input;
        setMessages(prev => [...prev, { type: 'user', content: message }]);
        setInput('');

        const request = {
            type: 'chat_message',
            data: {
                message: message,
                user_id: 'react_user'
            }
        };
        wsRef.current.send(JSON.stringify(request));
    };

    return (
        <div className="ai-chat">
            <div className="connection-status">
                状態: {isConnected ? '接続中' : '未接続'}
            </div>
            <div className="messages">
                {messages.map((msg, index) => (
                    <div key={index} className={`message ${msg.type}`}>
                        <div className="content">{msg.content}</div>
                        {msg.model && <div className="meta">モデル: {msg.model}</div>}
                    </div>
                ))}
            </div>
            <div className="input-area">
                <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyPress={(e) => e.key === 'Enter' && handleSend()}
                    disabled={!isConnected}
                />
                <button onClick={handleSend} disabled={!isConnected}>
                    送信
                </button>
            </div>
        </div>
    );
}

export default AIChat;
```

### **HTTP API の使用**

WebSocketの他に、HTTP APIでも通信可能です。

#### **チャットエンドポイント**
```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-key" \
  -d '{
    "message": "こんにちは",
    "user_id": "test_user",
    "force_model": null
  }'
```

#### **JavaScript (fetch API)**
```javascript
async function sendChatMessage(message, userId = 'web_user') {
    const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer your-secret-key'
        },
        body: JSON.stringify({
            message: message,
            user_id: userId,
            force_model: null
        })
    });

    const data = await response.json();
    console.log('AI応答:', data.response);
    console.log('使用モデル:', data.model_used);
    console.log('処理時間:', data.processing_time);
    
    return data;
}

// 使用例
sendChatMessage('Pythonを教えて');
```

### **認証とセキュリティ**

#### **APIキーの設定**
`.env`ファイルでAPIキーを設定します：
```bash
API_KEY=your-secret-key-here
```

#### **リクエストヘッダーへの認証情報追加**
```javascript
headers: {
    'Authorization': 'Bearer ' + apiKey,
    'Content-Type': 'application/json'
}
```

```csharp
// Unityでの認証ヘッダー追加（HTTPリクエストの場合）
headers.Add("Authorization", "Bearer " + apiKey);
```

### **エラーハンドリング**

#### **一般的なエラーコード**
| ステータスコード | 説明 | 対処方法 |
|----------------|------|----------|
| 401 | 認証エラー | APIキーを確認 |
| 500 | サーバーエラー | サーバーログを確認 |
| 503 | サービス利用不可 | AIモデルが起動しているか確認 |

#### **JavaScriptでのエラーハンドリング**
```javascript
try {
    const response = await fetch('http://localhost:8000/chat', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + apiKey
        },
        body: JSON.stringify(requestData)
    });

    if (!response.ok) {
        if (response.status === 401) {
            throw new Error('認証エラー: APIキーを確認してください');
        } else if (response.status === 500) {
            throw new Error('サーバーエラー: 管理者にお問い合わせください');
        }
        throw new Error(`エラー: ${response.status}`);
    }

    const data = await response.json();
    return data;
} catch (error) {
    console.error('リクエストエラー:', error);
    // ユーザーにエラーを表示
}
```

#### **Unityでのエラーハンドリング**
```csharp
void HandleResponse(string response)
{
    try
    {
        var data = JsonConvert.DeserializeObject<dynamic>(response);
        
        if (data.error != null)
        {
            string errorMessage = data.error.ToString();
            Debug.LogError("AIエラー: " + errorMessage);
            // ユーザーにエラーを表示
            return;
        }
        
        // 正常なレスポンスの処理
        string aiResponse = data.data.response.ToString();
        // ...
    }
    catch (JsonException e)
    {
        Debug.LogError("JSONパースエラー: " + e.Message);
    }
}
```

---

## 🔧 主要な設定ファイル

### **config.json**
```json
{
  "server": {
    "port": 8080,
    "host": "localhost"
  },
  "model": {
    "name": "default-model",
    "version": "1.0"
  },
  "memory": {
    "max_size": 1024,
    "timeout": 300
  },
  "websocket": {
    "url": "ws://localhost:8080/ws",
    "protocol": "json"
  }
}
```

### **.env ファイル（例）**
```bash
# サーバー
FASTAPI_PORT=8000

# AI モデル
PHI3_URL=http://phi3:8001
QWEN_URL=http://qwen:8002

# API キー
API_KEY=secret-key-12345

# ログレベル
LOG_LEVEL=INFO
```

---

## 📊 ログ出力と監視

### **ログの種類と保存先**

| ログタイプ | 保存先 | 内容 |
|----------|-------|------|
| **FastAPI** | `/02_logs/system/fastapi.log` | リクエスト/レスポンス、エラー |
| **会話ログ** | `/02_logs/conversations/` | ユーザーの会話履歴（JSONL） |
| **システム** | `/02_logs/system/` | イベント・警告・デバッグ情報 |

### **リアルタイム監視**
```bash
# FastAPI ログの リアルタイム表示
docker-compose logs -f fastapi

# 全サービスのログ表示
docker-compose logs -f
```

---

## 🐛 トラブルシューティング

### **Q: FastAPI が起動しない**
- ✅ ポート 8000 が使用中でないか確認
- ✅ `.env` ファイルが正しく設定されているか確認
- ✅ `docker-compose logs fastapi` でエラーを確認

### **Q: Phi3/Qwen が応答しない**
- ✅ モデルファイル（GGUF）が `03_models/` に配置されているか確認
- ✅ Docker ネットワークで `phi3:8001` / `qwen:8002` に疎通があるか確認
- ✅ メモリが十分か確認（4GB以上推奨）

### **Q: クライアントから接続できない**
- ✅ WebSocket URL が正しいか確認
- ✅ FastAPI が起動しているか確認
- ✅ ファイアウォール設定を確認

---

## 📦 依存パッケージ一覧

### **FastAPI サーバー**
```
FastAPI==0.115.0          # Webフレームワーク
Uvicorn==0.30.0           # ASGIサーバー
httpx==0.27.0             # 非同期HTTP通信
ChromaDB>=1.0.0           # ベクトルDB
Pydantic==2.9.0           # データ検証
Python-dotenv==1.0.1      # 環境変数読み込み
aiofiles==23.2.1          # 非同期ファイルIO
```

### **Phi3/Qwen (LLM)**
```
fastapi==0.115.0          # Webフレームワーク
uvicorn==0.30.0           # ASGIサーバー
llama-cpp-python          # LLM推論エンジン
pydantic==2.9.0           # データ検証
```

---

## 📝 ライセンス & 貢献

このプロジェクトはオープンソースです。改善提案やバグ報告は随時受け付けています。

---

## 📞 サポート

トラブルや質問がある場合：
- ログファイル (`/02_logs/`) を確認
- GitHub Issues で報告

**最終更新**: 2026年5月30日
