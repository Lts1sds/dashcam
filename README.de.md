<div align="center">

<img src="docs/logo.svg" alt="dashcam logo" width="340">

# dashcam

**Der Dashcam für deine KI-Agenten.**

Zero-Konfiguration, lokal-first: Tracing, Replay und Kosten-Debugging für LLM-Apps und Agenten.

[Schnellstart](#schnellstart) · [Funktionsweise](#funktionsweise) · [Konfiguration](#️-konfiguration) · [FAQ](#faq)

[![CI](https://github.com/Lts1sds/dashcam/actions/workflows/ci.yml/badge.svg)](https://github.com/Lts1sds/dashcam/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org)
![Zero dependencies](https://img.shields.io/badge/dependencies-zero-green.svg)

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | **Deutsch** | [Русский](README.ru.md) | [Português (Brasil)](README.pt-BR.md) | [हिन्दी](README.hi.md)

</div>

---

Es ist 2 Uhr nachts, dein Agent ist abgestürzt. *Welcher* Aufruf ist fehlgeschlagen? Was wurde *tatsächlich* gesendet? Wie viel hat der ganze Lauf gekostet und wohin sind die Tokens geflossen?

Ein Dashcam im Auto zeichnet still im Hintergrund alles auf — und wenn etwas schiefgeht, spulst du zurück und siehst genau, was passiert ist. **dashcam macht genau das für LLM-Apps**: Es zeichnet jeden LLM-Aufruf deines Programms still auf und gibt dir dann ein lokales Timeline-Panel zum Replays, Inspizieren und Fehler-Zuordnung.

## Warum dashcam

| | dashcam | LangSmith / Langfuse | print()-Debugging |
|---|---|---|---|
| Nötige Codeänderungen | **keine** | SDK / Decorator | überall |
| Daten verlassen deinen Rechner | **nie** | Cloud oder Self-Hosted-Server | - |
| Abhängigkeiten | **null** (reine Standardbibliothek) | Server + DB + SDK | - |
| Einrichtungszeit | 10 Sekunden | Minuten bis Stunden | - |
| Kosten-Tracking | eingebaut | variabel | manuell |
| Framework-unabhängig | ja (patcht das SDK) | framework-spezifisch | - |

## Schnellstart

```bash
pip install dashcam
dashcam demo        # erzeugt Demo-Traces, kein API-Key nötig
dashcam             # öffnet das Dashboard auf http://127.0.0.1:8377
```

### Option A — null Codeänderungen (empfohlen)

```bash
dashcam install                          # einmalig, schreibt einen .pth-Hook
DASHCAM=1 python your_agent.py           # das war's. alles wird aufgezeichnet
```

Unter Windows: `set DASHCAM=1 && python your_agent.py`

### Option B — eine Import-Zeile

```python
import dashcam
dashcam.instrument()   # patcht openai / anthropic / litellm, falls vorhanden
```

### Option C — explizite Trace-Grenzen (optional)

```python
with dashcam.trace("refund-processing-agent") as tid:
    run_agent()   # alle LLM-Aufrufe darin landen in einem Trace
```

Ohne explizite Grenzen werden Aufrufe automatisch nach Thread + Aktivitätsabstand gruppiert — ganz ohne Codeänderungen.

## Was du bekommst

<p align="center">
  <img src="docs/screenshot.png" alt="dashcam-Dashboard mit einer Agenten-Timeline" width="860">
</p>

- **Timeline-Replay** — jeder LLM-Aufruf in Reihenfolge, mit vollständigen Request-Nachrichten, Parametern, Tools und Responses. Klicke auf einen Schritt zum Aufklappen.
- **Abgeleitete Tool-Schritte** — dashcam vergleicht aufeinanderfolgende Nachrichten-Arrays und rekonstruiert, *was dein Agent zwischen den Aufrufen getan hat* (Tool-Ausführungen, Nutzer-Turns) — **ohne jegliche Framework-Integration**.
- **Fehler-Zuordnung** — fehlgeschlagene Aufrufe bekommen rote Karten mit der vollständigen Exception. Die Trace-Liste zeigt Fehler auf einen Blick.
- **Kosten- und Token-Buchhaltung** — Token-Zahlen und USD-Kostenschätzungen pro Aufruf und pro Trace für gängige OpenAI- / Anthropic- / DeepSeek- / Gemini- / Qwen-Modelle. Eigene Preistabelle via `DASHCAM_PRICES`.
- **Streaming-Support** — Streaming-Responses werden wieder zusammengesetzt und aufgezeichnet, einschließlich Tool-Call-Fragmenten.
- **Lokal & privat** — alles in einer einzigen SQLite-Datei (`~/.dashcam/traces.db`). Kein Server, kein Konto, keine Telemetrie.

## Funktionsweise

```
                    dein Programm
                         │
        openai / anthropic / litellm SDK-Aufrufe
                         │
              ┌──────────▼──────────┐
              │  dashcam patcher   │   monkey-patcht SDK-Einstiegspunkte
              │  (Zero-Konfig)     │   zeichnet Request / Response / Usage auf
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  SQLite-Speicher    │   ~/.dashcam/traces.db (WAL)
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  lokales Dashboard  │   http.server aus der stdlib, Port 8377
              │  Replay · Kosten    │   Trace-Liste, Timeline, JSON-Export
              └─────────────────────┘
```

dashcam patcht beim Import die Client-Klassen der installierten SDKs. Das Verhalten deines Programms bleibt unangetastet — wenn dashcam selbst fehlschlägt, scheitert es still und dein Agent läuft weiter.

### Unterstützte SDKs

| SDK | Einstiegspunkte | synchron | asynchron | Streaming |
|---|---|---|---|---|
| openai >= 1.0 | `chat.completions.create`, `responses.create` | ✅ | ✅ | ✅ |
| anthropic | `messages.create`, `messages.stream` | ✅ | ✅ | ✅ |
| litellm | `completion`, `acompletion` | ✅ | ✅ | ✅ |

Alles, was über diese läuft (LangChain, AutoGen, CrewAI, OpenAI-kompatible Endpoints via litellm, ...) wird automatisch erfasst.

## ⚙️ Konfiguration

| Umgebungsvariable | Standard | Bedeutung |
|---|---|---|
| `DASHCAM` | nicht gesetzt | Bei `1` instrumentiert der `.pth`-Hook automatisch beim Interpreter-Start |
| `DASHCAM_DB` | `~/.dashcam/traces.db` | Speicherort der SQLite-Datenbank |
| `DASHCAM_PRICES` | eingebaute Tabelle | Pfad zu einer JSON-Preistabelle: `{"modell-substring": [eingabe_pro_mtok, ausgabe_pro_mtok]}` |

Die Preis-Zuordnung erfolgt per Substring, längster Schlüssel gewinnt (z. B. schlägt `gpt-4o-mini` das `gpt-4o`). Preise sind Schätzungen — für fakturierungsgenaue Zahlen überschreibe sie mit deiner eigenen Tabelle.

## FAQ

**Verlangsamt das meinen Agenten?**
Das Aufzeichnen ist ein einziger SQLite-Insert pro LLM-Aufruf (Mikrosekunden). Deine LLM-Aufrufe dauern Hunderte Millisekunden. Du wirst nichts merken.

**Was, wenn dashcam kaputtgeht?**
Die gesamte dashcam-interne Logik ist defensiv gekapselt — wenn innerhalb von dashcam etwas eine Exception wirft, wird sie verschluckt und dein Programm läuft unbeeinflusst weiter.

**Werden Daten irgendwohin gesendet?**
Nein. Keine Netzwerkaufrufe, keine Telemetrie, kein Konto. Das Dashboard bindet nur an 127.0.0.1.

**Wie werden Aufrufe zu Traces gruppiert?**
Explizit per `dashcam.trace(name)`, oder automatisch: Aufrufe im selben Thread innerhalb eines 5-Minuten-Aktivitätsfensters landen im selben Trace. Inaktive Traces werden automatisch geschlossen.

**Streaming-Responses?**
Chunks (Text, Tool-Call-Fragmente, Usage) werden akkumuliert und beim Stream-Ende aufgezeichnet. `stream_options={"include_usage": True}` von OpenAI wird für die Usage-Erfassung respektiert.

## Entwicklung

```bash
git clone https://github.com/Lts1sds/dashcam
cd dashcam
pip install -e ".[dev]"
pytest                       # 23 Tests, keine API-Keys nötig
python examples/demo_agent.py   # Offline-Agenten-Loop-Demo
```

## Roadmap

- [ ] MCP-Tool-Call-Erfassung
- [ ] Prompt-Diff-Ansicht (was sich zwischen Aufrufen geändert hat)
- [ ] Suche über alle Traces
- [ ] Zeitreise-Replay eines einzelnen Schritts in einer REPL
- [ ] Framework-Adapter (LangChain-Callbacks, OpenTelemetry-Bridge)

## Lizenz

MIT
