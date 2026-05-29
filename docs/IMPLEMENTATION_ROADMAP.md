# 実装ロードマップ

## 概要

本ドキュメントは、システム拡張の実装ロードマップを示す。全5Phaseの設計が完了しており、順次実装を進める。

---

## 実装順序と依存関係

### 依存関係グラフ

```
Phase1 (基礎記憶)
  ├─ Redis (独立)
  ├─ Mem0 (独立)
  └─ 会話要約 (Mem0依存)
       ↓
Phase2 (思考フロー)
  ├─ LangGraph (Phase1依存)
  └─ Emotion System (LangGraph依存)
       ↓
Phase3 (タスク管理)
  ├─ Task Manager (LangGraph依存)
  └─ Tool Calling (Task Manager依存)
       ↓
Phase4 (マルチモーダル)
  ├─ SearxNG (独立)
  ├─ Whisper (独立)
  └─ Piper (独立)
       ↓
Phase5 (高度拡張)
  ├─ MCP (Tool Calling依存)
  ├─ Vision (独立)
  └─ 自律Agent (全Phase依存)
```

---

## Phase別実装チェックリスト

### Phase1: 基礎記憶層の強化

#### Redis
- [ ] Dockerコンテナ追加
- [ ] Redisデータ永続化設定
- [ ] ShortTermMemoryモジュール実装
- [ ] FastAPIへの統合
- [ ] APIエンドポイント追加
- [ ] テスト実装

#### Mem0
- [ ] Dockerコンテナ追加
- [ ] Mem0サービス実装
- [ ] MemoryOrganizerモジュール実装
- [ ] FastAPIへの統合
- [ ] APIエンドポイント追加
- [ ] テスト実装

#### 会話要約
- [ ] ConversationSummarizerモジュール実装
- [ ] FastAPIへの統合
- [ ] 自動要約ロジック実装
- [ ] テスト実装

#### 統合
- [ ] Phase1全体の統合テスト
- [ ] パフォーマンス確認
- [ ] ドキュメント更新

---

### Phase2: 思考フローの構造化

#### LangGraph
- [ ] Dockerコンテナ追加
- [ ] LangGraphサービス実装
- [ ] Graphノード実装
  - [ ] emotion_update
  - [ ] memory_search
  - [ ] task_analysis
  - [ ] tool_selection
  - [ ] execute_tools
  - [ ] llm_inference
  - [ ] memory_save
  - [ ] final_response
- [ ] LangGraphOrchestrator実装
- [ ] FastAPIへの統合
- [ ] テスト実装

#### Emotion System
- [ ] EmotionManagerモジュール実装
- [ ] 感情検出ロジック実装
- [ ] Unityアニメーションパラメータ生成
- [ ] FastAPIへの統合
- [ ] APIエンドポイント追加
- [ ] Unity連携実装
- [ ] テスト実装

#### 統合
- [ ] Phase2全体の統合テスト
- [ ] LangGraphフローの検証
- [ ] 感情状態の検証
- [ ] ドキュメント更新

---

### Phase3: タスク管理とツール呼び出し

#### Task Manager
- [ ] TaskManagerモジュール実装
- [ ] Task/Subtaskクラス実装
- [ ] タスク分析ロジック実装
- [ ] FastAPIへの統合
- [ ] APIエンドポイント追加
- [ ] テスト実装

#### Tool Registry
- [ ] BaseToolクラス実装
- [ ] ツール実装
  - [ ] WebSearchTool
  - [ ] FileTool
  - [ ] GitTool
  - [ ] DockerTool
  - [ ] UnityTool
- [ ] ToolRegistry実装
- [ ] FastAPIへの統合
- [ ] APIエンドポイント追加
- [ ] テスト実装

#### LangGraph統合
- [ ] LangGraphノードの更新
- [ ] ツール実行ノードの実装
- [ ] タスク管理との連携
- [ ] テスト実装

#### 統合
- [ ] Phase3全体の統合テスト
- [ ] タスク実行フローの検証
- [ ] ツール呼び出しの検証
- [ ] ドキュメント更新

---

### Phase4: マルチモーダル対応

#### SearxNG
- [ ] Dockerコンテナ追加
- [ ] SearxNG設定ファイル作成
- [ ] SearxNGClientモジュール実装
- [ ] FastAPIへの統合
- [ ] WebSearchToolの更新
- [ ] APIエンドポイント追加
- [ ] テスト実装

#### Whisper
- [ ] Dockerコンテナ追加
- [ ] Whisperサービス実装
- [ ] VoiceInputClientモジュール実装
- [ ] FastAPIへの統合
- [ ] APIエンドポイント追加
- [ ] Unity音声入力実装
- [ ] テスト実装

#### Piper
- [ ] Dockerコンテナ追加
- [ ] Piperサービス実装
- [ ] VoiceOutputClientモジュール実装
- [ ] FastAPIへの統合
- [ ] APIエンドポイント追加
- [ ] Unity音声出力実装
- [ ] テスト実装

#### LangGraph統合
- [ ] voice_input_node実装
- [ ] voice_output_node実装
- [ ] 音声フローの統合
- [ ] テスト実装

#### 統合
- [ ] Phase4全体の統合テスト
- [ ] 音声認識の検証
- [ ] 音声合成の検証
- [ ] Web検索の検証
- [ ] ドキュメント更新

---

### Phase5: 高度な拡張

#### MCP
- [ ] Dockerコンテナ追加
- [ ] MCPサーバー実装
- [ ] MCPClientモジュール実装
- [ ] MCPツール定義
  - [ ] VSCode
  - [ ] GitHub
  - [ ] Browser
  - [ ] FileSystem
  - [ ] Unity
- [ ] FastAPIへの統合
- [ ] ToolRegistryへのMCP統合
- [ ] テスト実装

#### Vision
- [ ] VisionProcessorモジュール実装
- [ ] 画像分析ロジック実装
- [ ] OCR実装（オプション）
- [ ] 物体検出実装（オプション）
- [ ] FastAPIへの統合
- [ ] APIエンドポイント追加
- [ ] テスト実装

#### 自律Agent
- [ ] AutonomousAgentモジュール実装
- [ ] 目標設定ロジック実装
- [ ] 目標実行ロジック実装
- [ ] 目標監視ロジック実装
- [ ] FastAPIへの統合
- [ ] APIエンドポイント追加
- [ ] バックグラウンド実行設定
- [ ] テスト実装

#### 統合
- [ ] Phase5全体の統合テスト
- [ ] MCPツールの検証
- [ ] Vision処理の検証
- [ ] 自律エージェントの検証
- [ ] ドキュメント更新

---

## 全体統合チェックリスト

### システム全体
- [ ] 全Phaseの統合テスト
- [ ] エンドツーエンドテスト
- [ ] パフォーマンステスト
- [ ] 負荷テスト
- [ ] セキュリティテスト

### Unity連携
- [ ] WebSocket通信の検証
- [ ] 感情状態連携の検証
- [ ] 音声入出力の検証
- [ ] UI更新の検証

### ドキュメント
- [ ] README更新
- [ ] ARCHITECTURE更新
- [ ] APIドキュメント更新
- [ ] セットアップガイド更新
- [ ] トラブルシューティング更新

---

## 推奨実装スケジュール

### 週1-2: Phase1実装
- Redis: 2日
- Mem0: 2日
- 会話要約: 1日
- 統合・テスト: 3日

### 週3-4: Phase2実装
- LangGraph: 3日
- Emotion System: 2日
- Unity連携: 2日
- 統合・テスト: 3日

### 週5-6: Phase3実装
- Task Manager: 2日
- Tool Registry: 3日
- LangGraph統合: 2日
- 統合・テスト: 3日

### 週7-8: Phase4実装
- SearxNG: 1日
- Whisper: 2日
- Piper: 2日
- Unity音声連携: 2日
- 統合・テスト: 3日

### 週9-10: Phase5実装
- MCP: 2日
- Vision: 2日
- 自律Agent: 3日
- 統合・テスト: 3日

### 週11-12: 全体統合
- 全体統合テスト: 5日
- ドキュメント更新: 3日
- バグ修正: 2日

---

## リスク管理

### 技術的リスク
- **LangGraphの複雑さ**: ノード間の依存関係が複雑になる可能性
  - 対策: 段階的な実装とテスト
- **音声処理のリソース消費**: Whisper/Piperが大量メモリを消費
  - 対策: リソース制限とモニタリング
- **MCPの互換性**: 外部ツールとの互換性問題
  - 対策: 標準的なプロトコル遵守

### 実装リスク
- **スケジュール遅延**: 各Phaseの見積もり超過
  - 対策: マイルストーン設定と進捗管理
- **統合の複雑さ**: コンポーネント間の依存関係
  - 対策: 早期の統合テスト

---

## 成功基準

### Phase1
- Redisが正常に動作し、短期記憶を保持できる
- Mem0が重要情報を抽出・保存できる
- 会話要約が自動的に実行される

### Phase2
- LangGraphが思考フローを制御できる
- 感情状態が正しく更新される
- Unityと感情状態が連携できる

### Phase3
- タスクが作成・管理できる
- ツールが正しく呼び出される
- LangGraphと統合されている

### Phase4
- Web検索が機能する
- 音声認識が機能する
- 音声合成が機能する

### Phase5
- MCPツールが使用できる
- 画像処理が機能する
- 自律エージェントが目標を実行できる

### 全体
- 全てのPhaseが統合されている
- エンドツーエンドで機能する
- パフォーマンスが許容範囲内

---

## 次のステップ

1. Phase1の実装を開始
2. 各Phaseの完了時にチェックリストを確認
3. 問題が発生した場合は早期に対処
4. 全Phase完了後に全体統合テストを実施

---

## 連絡先

実装中に問題が発生した場合は、以下のドキュメントを参照:
- SYSTEM_EXTENSION_ARCHITECTURE.md
- PHASE1_DESIGN.md
- PHASE2_DESIGN.md
- PHASE3_DESIGN.md
- PHASE4_DESIGN.md
- PHASE5_DESIGN.md
