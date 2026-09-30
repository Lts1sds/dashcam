<div align="center">

<img src="docs/logo.svg" alt="dashcam logo" width="340">

# dashcam

**당신의 AI 에이전트를 위한 블랙박스(dashcam).**

LLM 앱과 에이전트를 위한 제로 설정, 로컬 우선 트레이싱·리플레이·비용 디버깅 도구.

[빠른 시작](#빠른-시작) · [작동 방식](#작동-방식) · [설정](#️-설정) · [FAQ](#faq)

[![CI](https://github.com/Lts1sds/dashcam/actions/workflows/ci.yml/badge.svg)](https://github.com/Lts1sds/dashcam/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org)
![Zero dependencies](https://img.shields.io/badge/dependencies-zero-green.svg)

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | **한국어** | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Русский](README.ru.md) | [Português (Brasil)](README.pt-BR.md) | [हिन्दी](README.hi.md)

</div>

---

새벽 2시, 에이전트가 죽었다. *어느* 호출이 실패했지? 실제로*무엇을* 보냈지? 전체 실행에 얼마가 들었고, 토큰은 어디로 갔지?

자동차의 블랙박스는 모든 것을 조용히 기록하다가, 사고가 나면 영상을 되감아 정확히 무슨 일이 있었는지 보여줍니다. **dashcam은 LLM 앱에 대해 정확히 그 일을 합니다**: 프로그램이 만드는 모든 LLM 호출을 조용히 기록하고, 로컬 타임라인에서 리플레이·검사·실패 원인 분석을 할 수 있게 해줍니다.

## dashcam을 선택해야 하는 이유

| | dashcam | LangSmith / Langfuse | print() 디버깅 |
|---|---|---|---|
| 필요한 코드 변경 | **없음** | SDK / 데코레이터 | 여기저기 |
| 머신 밖으로 나가는 데이터 | **전혀 없음** | 클라우드 또는 셀프호스팅 | - |
| 의존성 | **제로** (순수 표준 라이브러리) | 서버 + DB + SDK | - |
| 설정 시간 | 10초 | 몇 분 ~ 몇 시간 | - |
| 비용 추적 | 내장 | 방식에 따라 다름 | 수동 |
| 프레임워크 독립 | 예 (SDK를 패치) | 프레임워크별 | - |

## 빠른 시작

```bash
pip install dashcam
dashcam demo        # API 키 없이 데모 트레이스 생성
dashcam             # http://127.0.0.1:8377 에서 대시보드 열기
```

### 방법 A — 코드 변경 제로 (권장)

```bash
dashcam install                          # 최초 1회, .pth 훅 작성
DASHCAM=1 python your_agent.py           # 끝. 모든 것이 기록됩니다
```

Windows: `set DASHCAM=1 && python your_agent.py`

### 방법 B — 한 줄 import

```python
import dashcam
dashcam.instrument()   # 설치된 openai / anthropic / litellm / mcp을 자동 패치
```

### 방법 C — 명시적 트레이스 경계 (선택)

```python
with dashcam.trace("refund-processing-agent") as tid:
    run_agent()   # 내부의 모든 LLM 호출이 하나의 트레이스로 묶임
```

명시적 경계가 없어도 호출은 스레드 + 활동 간격으로 자동 그룹화됩니다. 코드 변경이 필요 없습니다.

## 얻을 수 있는 것

<p align="center">
  <img src="docs/screenshot.png" alt="dashcam 대시보드: 에이전트 타임라인" width="860">
</p>

- **타임라인 리플레이** — 모든 LLM 호출을 순서대로, 완전한 요청 메시지·파라미터·도구·응답과 함께 표시. 클릭하면 펼쳐집니다.
- **암시적 도구 단계 추론** — dashcam이 연속된 메시지 배열을 diff하여 호출 *사이에* 에이전트가 무엇을 했는지(도구 실행, 사용자 발화) 재구성합니다. **프레임워크 통합 불필요**.
- **실패 원인 분석** — 실패한 호출은 전체 예외가 담긴 빨간 카드로 표시. 트레이스 목록에서 오류를 한눈에 확인.
- **비용·토큰 관리** — 호출별·트레이스별 토큰 수와 달러 비용 추정. OpenAI / Anthropic / DeepSeek / Gemini / Qwen 주요 모델 내장. `DASHCAM_PRICES`로 자체 가격표 지정 가능.
- **스트리밍 지원** — 스트리밍 응답이 재조립되어 기록됩니다. 도구 호출 조각 포함.
- **로컬 & 프라이빗** — 모든 것이 단일 SQLite 파일(`~/.dashcam/traces.db`)에 저장. 서버 없음, 계정 없음, 텔레메트리 없음.

## 작동 방식

```
                    당신의 프로그램
                       │
          openai / anthropic / litellm / mcp SDK 호출
                       │
            ┌──────────▼──────────┐
            │  dashcam patcher   │   SDK 진입점을 monkey-patch
            │  (제로 설정)         │   요청 / 응답 / usage 기록
            └──────────┬──────────┘
                       │
            ┌──────────▼──────────┐
            │  SQLite 저장소        │   ~/.dashcam/traces.db (WAL)
            └──────────┬──────────┘
                       │
            ┌──────────▼──────────┐
            │  로컬 대시보드        │   표준 라이브러리 http.server, 포트 8377
            │  리플레이 · 비용      │   트레이스 목록, 타임라인, JSON 내보내기
            └─────────────────────┘
```

dashcam은 설치된 SDK의 클라이언트 클래스를 import 시점에 패치합니다. 프로그램의 동작은 전혀 건드리지 않습니다. dashcam 자체가 실패해도 조용히 실패하고 에이전트는 계속 실행됩니다.

### 지원 SDK

| SDK | 진입점 | 동기 | 비동기 | 스트리밍 |
|---|---|---|---|---|
| openai >= 1.0 | `chat.completions.create`, `responses.create` | ✅ | ✅ | ✅ |
| anthropic | `messages.create`, `messages.stream` | ✅ | ✅ | ✅ |
| litellm | `completion`, `acompletion` | ✅ | ✅ | ✅ |
| mcp >= 1.0 | `ClientSession.call_tool`, `list_tools`, `read_resource` | — | ✅ | — |

이들을 경유하는 모든 것(LangChain, AutoGen, CrewAI, litellm 라우팅 OpenAI 호환 엔드포인트 등)은 자동으로 캡처됩니다.

## ⚙️ 설정

| 환경 변수 | 기본값 | 의미 |
|---|---|---|
| `DASHCAM` | 설정 안 됨 | `1`로 설정하면 `.pth` 훅이 인터프리터 시작 시 자동 계측 |
| `DASHCAM_DB` | `~/.dashcam/traces.db` | SQLite 데이터베이스 위치 |
| `DASHCAM_PRICES` | 내장 가격표 | JSON 가격표 경로: `{"모델 부분문자열": [입력 1M토큰당, 출력 1M토큰당]}` |

가격 매칭은 부분문자열 기반, 가장 긴 키가 우선합니다 (예: `gpt-4o-mini`가 `gpt-4o`보다 우선). 가격은 추정치입니다. 청구 등급 정확도가 필요하면 자체 표로 재정의하세요.

## FAQ

**에이전트가 느려지나요?**
기록은 LLM 호출당 SQLite insert 한 번(마이크로초 단위)입니다. LLM 호출 자체는 수백 밀리초가 걸립니다. 체감할 수 없습니다.

**dashcam이 고장 나면?**
모든 dashcam 내부 로직은 방어적으로 래핑되어 있습니다. dashcam 내부에서 무엇이 터져도 예외는 삼켜지고 프로그램은 영향을 받지 않습니다.

**데이터를 어딘가로 보내나요?**
아니요. 네트워크 호출, 텔레메트리, 계정 모두 없음. 대시보드는 127.0.0.1에만 바인딩됩니다.

**호출은 어떻게 트레이스로 그룹화되나요?**
`dashcam.trace(name)`으로 명시적으로, 또는 자동으로: 같은 스레드에서 5분 활동 간격 내의 호출은 같은 트레이스에 속합니다. 유휴 트레이스는 자동으로 닫힙니다.

**스트리밍 응답은요?**
청크(텍스트, 도구 호출 조각, usage)가 누적되어 스트림이 끝날 때 기록됩니다. OpenAI usage 캡처에는 `stream_options={"include_usage": True}`가 존중됩니다.

## 개발

```bash
git clone https://github.com/Lts1sds/dashcam
cd dashcam
pip install -e ".[dev]"
pytest                       # 23개 테스트, API 키 불필요
python examples/demo_agent.py   # 오프라인 에이전트 루프 데모
```

## Roadmap

- [ ] MCP 도구 호출 캡처
- [ ] 프롬프트 diff 뷰 (호출 간 무엇이 바뀌었는지)
- [ ] 전체 트레이스 검색
- [ ] 단일 단계의 타임트래블 리플레이를 REPL로
- [ ] 프레임워크 어댑터 (LangChain 콜백, OpenTelemetry 브리지)

## 라이선스

MIT
