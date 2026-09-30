<div align="center">

<img src="docs/logo.svg" alt="dashcam logo" width="340">

# dashcam

**あなたの AI エージェントのためのドライブレコーダー。**

LLM アプリとエージェントのための、ゼロ設定・ローカルファーストのトレーシング、リプレイ、コストデバッグツール。

[クイックスタート](#クイックスタート) · [仕組み](#仕組み) · [設定](#️-設定) · [FAQ](#faq)

[![CI](https://github.com/Lts1sds/dashcam/actions/workflows/ci.yml/badge.svg)](https://github.com/Lts1sds/dashcam/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org)
![Zero dependencies](https://img.shields.io/badge/dependencies-zero-green.svg)

[English](README.md) | [简体中文](README.zh-CN.md) | **日本語** | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Русский](README.ru.md) | [Português (Brasil)](README.pt-BR.md) | [हिन्दी](README.hi.md)

</div>

---

深夜 2 時、エージェントが落ちた。*どの*呼び出しが失敗した？実際に*何を*送った？実行全体でいくらかかり、トークンはどこへ消えた？

車のドライブレコーダーは、すべてをバックグラウンドで静かに記録し、何かが起きたときに映像を巻き戻して何が起きたかを正確に確認できます。**dashcam は LLM アプリに対してそれを行います**：プログラムが発するすべての LLM 呼び出しを静かに記録し、ローカルのタイムラインでリプレイ・検査・失敗の原因究明ができます。

## dashcam を選ぶ理由

| | dashcam | LangSmith / Langfuse | print() デバッグ |
|---|---|---|---|
| 必要なコード変更 | **なし** | SDK / デコレータ | あらゆる場所 |
| マシン外へのデータ送信 | **一切なし** | クラウドまたはセルフホスト | - |
| 依存関係 | **ゼロ**（純正標準ライブラリ） | サーバー + DB + SDK | - |
| セットアップ時間 | 10 秒 | 数分〜数時間 | - |
| コスト追跡 | 内蔵 | 方式による | 手動 |
| フレームワーク非依存 | はい（SDK をパッチ） | フレームワーク固有 | - |

## クイックスタート

```bash
pip install dashcam
dashcam demo        # API キー不要のデモトレースを生成
dashcam             # ダッシュボードを http://127.0.0.1:8377 で開く
```

### 方式 A — コード変更ゼロ（推奨）

```bash
dashcam install                          # 一回だけ。.pth フックを書き込む
DASHCAM=1 python your_agent.py           # 以上。すべて記録されます
```

Windows の場合：`set DASHCAM=1 && python your_agent.py`

### 方式 B — インポート 1 行

```python
import dashcam
dashcam.instrument()   # openai / anthropic / litellm / mcp があれば自動パッチ
```

### 方式 C — 明示的なトレース境界（任意）

```python
with dashcam.trace("refund-processing-agent") as tid:
    run_agent()   # 内のすべての LLM 呼び出しが 1 つのトレースにまとまる
```

明示的な境界がなくても、呼び出しはスレッド + アクティビティ間隔で自動的にグループ化されます。コード変更は不要です。

## 得られるもの

<p align="center">
  <img src="docs/screenshot.png" alt="dashcam ダッシュボード：エージェントのタイムライン" width="860">
</p>

- **タイムラインリプレイ** — すべての LLM 呼び出しを順番に、完全なリクエストメッセージ・パラメータ・ツール・レスポンス付きで表示。クリックで展開。
- **ツールステップの推定** — dashcam は連続するメッセージ配列を diff して、呼び出し間に*エージェントが何をしたか*（ツール実行、ユーザー発言）を再構築します。**フレームワーク統合は不要**。
- **失敗の原因究明** — 失敗した呼び出しは完全な例外付きの赤いカードに。トレース一覧でエラーがひと目で分かります。
- **コスト・トークン管理** — 呼び出しごと・トレースごとのトークン数とドルコスト概算。OpenAI / Anthropic / DeepSeek / Gemini / Qwen の主要モデルに対応。`DASHCAM_PRICES` で独自価格表を指定可能。
- **ストリーミング対応** — ストリーミングレスポンスは再構築されて記録されます。ツール呼び出しフラグメント含む。
- **ローカル & プライベート** — すべて単一の SQLite ファイル（`~/.dashcam/traces.db`）に保存。サーバー不要、アカウント不要、テレメトリなし。

## 仕組み

```
                    あなたのプログラム
                         │
        openai / anthropic / litellm / mcp SDK 呼び出し
                         │
              ┌──────────▼──────────┐
              │  dashcam patcher    │   SDK エントリーポイントを monkey-patch
              │  (ゼロ設定)          │   リクエスト / レスポンス / usage を記録
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  SQLite ストア       │   ~/.dashcam/traces.db (WAL)
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  ローカルダッシュボード │   標準ライブラリ http.server、ポート 8377
              │  リプレイ · コスト     │   トレース一覧、タイムライン、JSON エクスポート
              └─────────────────────┘
```

dashcam は、インストール済み SDK のクライアントクラスをインポート時にパッチします。プログラムの動作は一切変更されません。dashcam 自身が失敗しても、静かに失敗してエージェントは動き続けます。

### 対応 SDK

| SDK | エントリーポイント | 同期 | 非同期 | ストリーミング |
|---|---|---|---|---|
| openai >= 1.0 | `chat.completions.create`、`responses.create` | ✅ | ✅ | ✅ |
| anthropic | `messages.create`、`messages.stream` | ✅ | ✅ | ✅ |
| litellm | `completion`、`acompletion` | ✅ | ✅ | ✅ |
| mcp >= 1.0 | `ClientSession.call_tool`, `list_tools`, `read_resource` | — | ✅ | — |

これらを経由するもの（LangChain、AutoGen、CrewAI、litellm 経由の OpenAI 互換エンドポイントなど）は自動的にキャプチャされます。

## ⚙️ 設定

| 環境変数 | デフォルト | 意味 |
|---|---|---|
| `DASHCAM` | 未設定 | `1` に設定すると、`.pth` フックがインタプリタ起動時に自動計測 |
| `DASHCAM_DB` | `~/.dashcam/traces.db` | SQLite データベースの場所 |
| `DASHCAM_PRICES` | 内蔵価格表 | JSON 価格表のパス：`{"モデル部分文字列": [入力1Mトークンあたり, 出力1Mトークンあたり]}` |

価格マッチングは部分文字列ベースで、最長キーが優先されます（例：`gpt-4o-mini` は `gpt-4o` より優先）。価格は概算です。請求グレードの精度が必要な場合は独自の表で上書きしてください。

## FAQ

**エージェントが遅くなりますか？**
記録は LLM 呼び出しごとに 1 回の SQLite 挿入（マイクロ秒オーダー）です。LLM 呼び出し自体は数百ミリ秒かかります。体感できません。

**dashcam が壊れたら？**
すべての dashcam 内部ロジックは防御的にラップされています。dashcam 内部で何が起きても例外は握りつぶされ、プログラムは影響を受けません。

**データをどこかに送りますか？**
いいえ。ネットワーク呼び出し、テレメトリ、アカウントすべてなし。ダッシュボードは 127.0.0.1 にのみバインドします。

**呼び出しはどうトレースにグループ化されますか？**
`dashcam.trace(name)` で明示的に、または自動的に：同じスレッドで 5 分以内のアクティビティギャップの呼び出しは同じトレースに。アイドルトレースは自動的に閉じられます。

**ストリーミングレスポンスは？**
チャンク（テキスト、ツール呼び出しフラグメント、usage）が蓄積され、ストリーム終了時に記録されます。OpenAI の usage キャプチャには `stream_options={"include_usage": True}` が尊重されます。

## 開発

```bash
git clone https://github.com/Lts1sds/dashcam
cd dashcam
pip install -e ".[dev]"
pytest                       # 23 テスト、API キー不要
python examples/demo_agent.py   # オフラインのエージェントループデモ
```

## Roadmap

- [ ] MCP ツール呼び出しのキャプチャ
- [ ] プロンプト diff ビュー（呼び出し間で何が変わったか）
- [ ] 全トレース横断検索
- [ ] 1 ステップのタイムトラベルリプレイを REPL で
- [ ] フレームワークアダプタ（LangChain コールバック、OpenTelemetry ブリッジ）

## ライセンス

MIT
