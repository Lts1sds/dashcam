<div align="center">

<img src="docs/logo.svg" alt="dashcam logo" width="340">

# dashcam

**La dashcam para tus agentes de IA.**

Trazado, reproducción y depuración de costes para apps LLM y agentes — con configuración cero y prioridad local.

[Inicio rápido](#inicio-rápido) · [Cómo funciona](#cómo-funciona) · [Configuración](#️-configuración) · [FAQ](#faq)

[![CI](https://github.com/Lts1sds/dashcam/actions/workflows/ci.yml/badge.svg)](https://github.com/Lts1sds/dashcam/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org)
![Zero dependencies](https://img.shields.io/badge/dependencies-zero-green.svg)

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | **Español** | [Français](README.fr.md) | [Deutsch](README.de.md) | [Русский](README.ru.md) | [Português (Brasil)](README.pt-BR.md) | [हिन्दी](README.hi.md)

</div>

---

Son las 2 de la madrugada y tu agente ha fallado. ¿*Cuál* llamada falló? ¿Qué envió *realmente*? ¿Cuánto costó toda la ejecución y a dónde fueron los tokens?

La dashcam de un coche graba todo en silencio en segundo plano — y cuando algo sale mal, rebobinas la cinta y ves exactamente qué pasó. **dashcam hace eso para las apps LLM**: graba silenciosamente cada llamada LLM que hace tu programa, y te da una línea de tiempo local para reproducir, inspeccionar y atribuir fallos.

## Por qué dashcam

| | dashcam | LangSmith / Langfuse | depuración con print() |
|---|---|---|---|
| Cambios de código necesarios | **ninguno** | SDK / decorador | por todas partes |
| Datos que salen de tu máquina | **nunca** | nube o servidor autohospedado | - |
| Dependencias | **cero** (solo librería estándar) | servidor + BD + SDK | - |
| Tiempo de configuración | 10 segundos | de minutos a horas | - |
| Seguimiento de costes | integrado | varía | manual |
| Funciona con cualquier framework | sí (parchea el SDK) | específico del framework | - |

## Inicio rápido

```bash
pip install dashcam
dashcam demo        # genera trazas de demo, sin necesidad de API key
dashcam             # abre el panel en http://127.0.0.1:8377
```

### Opción A — cero cambios de código (recomendado)

```bash
dashcam install                          # una sola vez, escribe un hook .pth
DASHCAM=1 python your_agent.py           # eso es todo. todo queda grabado
```

En Windows: `set DASHCAM=1 && python your_agent.py`

### Opción B — una línea de import

```python
import dashcam
dashcam.instrument()   # parchea openai / anthropic / litellm / mcp si están presentes
```

### Opción C — límites de traza explícitos (opcional)

```python
with dashcam.trace("refund-processing-agent") as tid:
    run_agent()   # todas las llamadas LLM dentro se agrupan en una traza
```

Sin límites explícitos, las llamadas se agrupan automáticamente por hilo + intervalo de actividad — sin cambios de código.

## Qué obtienes

<p align="center">
  <img src="docs/screenshot.png" alt="Panel de dashcam mostrando la línea de tiempo de un agente" width="860">
</p>

- **Reproducción en línea de tiempo** — cada llamada LLM en orden, con mensajes de petición completos, parámetros, herramientas y respuestas. Haz clic en cualquier paso para expandirlo.
- **Pasos de herramienta inferidos** — dashcam compara arrays de mensajes consecutivos para reconstruir *qué hizo tu agente entre llamadas* (ejecuciones de herramientas, turnos de usuario) — **sin integración con ningún framework**.
- **Atribución de fallos** — las llamadas fallidas reciben tarjetas rojas con la excepción completa. La lista de trazas muestra los errores de un vistazo.
- **Contabilidad de costes y tokens** — recuentos de tokens y coste estimado en USD por llamada y por traza para modelos comunes de OpenAI / Anthropic / DeepSeek / Gemini / Qwen. Trae tu propia tabla de precios con `DASHCAM_PRICES`.
- **Soporte de streaming** — las respuestas en streaming se reensamblan y se graban, incluidos los fragmentos de tool-calls.
- **Local y privado** — todo en un único archivo SQLite (`~/.dashcam/traces.db`). Sin servidor, sin cuenta, sin telemetría.

## Cómo funciona

```
                    tu programa
                         │
        llamadas al SDK openai / anthropic / litellm / mcp
                         │
              ┌──────────▼──────────┐
              │  dashcam patcher   │   parchea los puntos de entrada del SDK
              │  (configuración    │   graba petición / respuesta / usage
              │   cero)            │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  almacén SQLite     │   ~/.dashcam/traces.db (WAL)
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  panel local        │   http.server de la librería estándar, puerto 8377
              │  replay · costes   │   lista de trazas, línea de tiempo, export JSON
              └─────────────────────┘
```

dashcam parchea las clases cliente de los SDK instalados en el momento del import. El comportamiento de tu programa no se toca — si dashcam falla, falla en silencio y tu agente sigue funcionando.

### SDKs soportados

| SDK | puntos de entrada | síncrono | asíncrono | streaming |
|---|---|---|---|---|
| openai >= 1.0 | `chat.completions.create`, `responses.create` | ✅ | ✅ | ✅ |
| anthropic | `messages.create`, `messages.stream` | ✅ | ✅ | ✅ |
| litellm | `completion`, `acompletion` | ✅ | ✅ | ✅ |
| mcp >= 1.0 | `ClientSession.call_tool`, `list_tools`, `read_resource` | — | ✅ | — |

Todo lo que pase por estos (LangChain, AutoGen, CrewAI, endpoints compatibles con OpenAI vía litellm, ...) se captura automáticamente.

## ⚙️ Configuración

| Variable de entorno | Por defecto | Significado |
|---|---|---|
| `DASHCAM` | sin definir | Si vale `1`, el hook `.pth` auto-instrumenta al arrancar el intérprete |
| `DASHCAM_DB` | `~/.dashcam/traces.db` | Ubicación de la base de datos SQLite |
| `DASHCAM_PRICES` | tabla integrada | Ruta a una tabla de precios JSON: `{"subcadena-de-modelo": [entrada_por_mtok, salida_por_mtok]}` |

La coincidencia de precios es por subcadena, gana la clave más larga (p. ej. `gpt-4o-mini` gana a `gpt-4o`). Los precios son estimaciones — sobrescribe con tu propia tabla para números de nivel de facturación.

## FAQ

**¿Ralentiza mi agente?**
Grabar es una única inserción SQLite por llamada LLM (microsegundos). Tus llamadas LLM tardan cientos de milisegundos. No lo notarás.

**¿Y si dashcam falla?**
Toda la lógica interna de dashcam está envuelta de forma defensiva — si algo dentro de dashcam lanza una excepción, se silencia y tu programa continúa sin afectarse.

**¿Envía datos a algún sitio?**
No. Sin llamadas de red, sin telemetría, sin cuenta. El panel solo escucha en 127.0.0.1.

**¿Cómo se agrupan las llamadas en trazas?**
Explícitamente con `dashcam.trace(name)`, o automáticamente: las llamadas del mismo hilo dentro de un intervalo de actividad de 5 minutos se unen a la misma traza. Las trazas inactivas se cierran solas.

**¿Respuestas en streaming?**
Los fragmentos (texto, fragmentos de tool-calls, usage) se acumulan y se graban cuando el flujo termina. Se respeta `stream_options={"include_usage": True}` de OpenAI para capturar el usage.

## Desarrollo

```bash
git clone https://github.com/Lts1sds/dashcam
cd dashcam
pip install -e ".[dev]"
pytest                       # 34 tests, sin API keys
python examples/demo_agent.py   # demo de bucle de agente sin conexión
```

## Roadmap

- [x] Captura de tool-calls MCP
- [ ] Vista diff de prompts (qué cambió entre llamadas)
- [ ] Búsqueda en todas las trazas
- [ ] Reproducción de un solo paso en un REPL (viaje en el tiempo)
- [ ] Adaptadores de framework (callbacks de LangChain, puente OpenTelemetry)

## Licencia

MIT
