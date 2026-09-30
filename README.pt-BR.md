<div align="center">

<img src="docs/logo.svg" alt="dashcam logo" width="340">

# dashcam

**A dashcam para seus agentes de IA.**

Rastreamento, replay e depuração de custos para apps LLM e agentes — configuração zero, local primeiro.

[Início rápido](#início-rápido) · [Como funciona](#como-funciona) · [Configuração](#️-configuração) · [FAQ](#faq)

[![CI](https://github.com/Lts1sds/dashcam/actions/workflows/ci.yml/badge.svg)](https://github.com/Lts1sds/dashcam/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org)
![Zero dependencies](https://img.shields.io/badge/dependencies-zero-green.svg)

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | [Français](README.fr.md) | [Deutsch](README.de.md) | [Русский](README.ru.md) | **Português (Brasil)** | [हिन्दी](README.hi.md)

</div>

---

São 2 da manhã e seu agente caiu. *Qual* chamada falhou? O que ele *realmente* enviou? Quanto custou a execução inteira e para onde foram os tokens?

A câmera de bordo de um carro grava tudo silenciosamente em segundo plano — e quando algo dá errado, você rebobina a fita e vê exatamente o que aconteceu. **O dashcam faz isso para apps LLM**: ele grava silenciosamente cada chamada LLM que seu programa faz, e te dá uma timeline local para reproduzir, inspecionar e atribuir falhas.

## Por que dashcam

| | dashcam | LangSmith / Langfuse | depuração com print() |
|---|---|---|---|
| Mudanças de código necessárias | **nenhuma** | SDK / decorator | por toda parte |
| Dados saindo da sua máquina | **nunca** | nuvem ou servidor self-hosted | - |
| Dependências | **zero** (biblioteca padrão pura) | servidor + banco + SDK | - |
| Tempo de configuração | 10 segundos | de minutos a horas | - |
| Rastreamento de custos | embutido | varia | manual |
| Funciona com qualquer framework | sim (faz patch do SDK) | específico do framework | - |

## Início rápido

```bash
pip install dashcam
dashcam demo        # gera traces de demonstração, sem precisar de API key
dashcam             # abre o painel em http://127.0.0.1:8377
```

### Opção A — zero mudanças de código (recomendado)

```bash
dashcam install                          # uma vez só, escreve um hook .pth
DASHCAM=1 python your_agent.py           # pronto. tudo é gravado
```

No Windows: `set DASHCAM=1 && python your_agent.py`

### Opção B — uma linha de import

```python
import dashcam
dashcam.instrument()   # faz patch do openai / anthropic / litellm / mcp se presentes
```

### Opção C — fronteiras de trace explícitas (opcional)

```python
with dashcam.trace("refund-processing-agent") as tid:
    run_agent()   # todas as chamadas LLM dentro viram um único trace
```

Sem fronteiras explícitas, as chamadas são agrupadas automaticamente por thread + intervalo de atividade — sem mudanças de código.

## O que você ganha

<p align="center">
  <img src="docs/screenshot.png" alt="Painel do dashcam mostrando a timeline de um agente" width="860">
</p>

- **Replay em timeline** — cada chamada LLM em ordem, com mensagens de requisição completas, parâmetros, ferramentas e respostas. Clique em qualquer passo para expandir.
- **Passos de ferramenta inferidos** — o dashcam compara arrays de mensagens consecutivos para reconstruir *o que seu agente fez entre as chamadas* (execuções de ferramentas, turnos do usuário) — **sem integração com nenhum framework**.
- **Atribuição de falhas** — chamadas que falham ganham cartões vermelhos com a exceção completa. A lista de traces mostra erros de relance.
- **Contabilidade de custos e tokens** — contagens de tokens e estimativas de custo em USD por chamada e por trace para modelos comuns de OpenAI / Anthropic / DeepSeek / Gemini / Qwen. Traga sua própria tabela de preços com `DASHCAM_PRICES`.
- **Suporte a streaming** — respostas em streaming são remontadas e gravadas, incluindo fragmentos de tool-calls.
- **Local e privado** — tudo num único arquivo SQLite (`~/.dashcam/traces.db`). Sem servidor, sem conta, sem telemetria.

## Como funciona

```
                    seu programa
                         │
        chamadas ao SDK openai / anthropic / litellm / mcp
                         │
              ┌──────────▼──────────┐
              │  dashcam patcher   │   monkey-patch dos pontos de entrada do SDK
              │  (config zero)     │   grava requisição / resposta / usage
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  armazenamento       │   ~/.dashcam/traces.db (WAL)
              │  SQLite             │
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  painel local       │   http.server da stdlib, porta 8377
              │  replay · custos   │   lista de traces, timeline, export JSON
              └─────────────────────┘
```

O dashcam faz patch das classes de cliente dos SDKs instalados no momento do import. O comportamento do seu programa não é tocado — se o próprio dashcam falhar, ele falha em silêncio e seu agente continua rodando.

### SDKs suportados

| SDK | pontos de entrada | síncrono | assíncrono | streaming |
|---|---|---|---|---|
| openai >= 1.0 | `chat.completions.create`, `responses.create` | ✅ | ✅ | ✅ |
| anthropic | `messages.create`, `messages.stream` | ✅ | ✅ | ✅ |
| litellm | `completion`, `acompletion` | ✅ | ✅ | ✅ |
| mcp >= 1.0 | `ClientSession.call_tool`, `list_tools`, `read_resource` | — | ✅ | — |

Tudo que passa por esses pontos (LangChain, AutoGen, CrewAI, endpoints compatíveis com OpenAI via litellm, ...) é capturado automaticamente.

## ⚙️ Configuração

| Variável de ambiente | Padrão | Significado |
|---|---|---|
| `DASHCAM` | não definida | Quando vale `1`, o hook `.pth` instrumenta automaticamente na inicialização do interpretador |
| `DASHCAM_DB` | `~/.dashcam/traces.db` | Local do banco SQLite |
| `DASHCAM_PRICES` | tabela embutida | Caminho para uma tabela de preços JSON: `{"substring-do-modelo": [entrada_por_mtok, saída_por_mtok]}` |

O casamento de preços é por substring, a chave mais longa vence (ex.: `gpt-4o-mini` vence `gpt-4o`). Os preços são estimativas — sobrescreva com sua própria tabela para números de nível de faturamento.

## FAQ

**Vai deixar meu agente lento?**
Gravar é um único insert SQLite por chamada LLM (microssegundos). Suas chamadas LLM levam centenas de milissegundos. Você não vai notar.

**E se o dashcam quebrar?**
Toda a lógica interna do dashcam é envolvida defensivamente — se algo dentro do dashcam lançar uma exceção, ela é engolida e seu programa continua intacto.

**Envia dados para algum lugar?**
Não. Sem chamadas de rede, sem telemetria, sem conta. O painel escuta apenas em 127.0.0.1.

**Como as chamadas são agrupadas em traces?**
Explicitamente com `dashcam.trace(name)`, ou automaticamente: chamadas na mesma thread dentro de um intervalo de atividade de 5 minutos entram no mesmo trace. Traces inativos são fechados sozinhos.

**Respostas em streaming?**
Os chunks (texto, fragmentos de tool-calls, usage) são acumulados e gravados quando o fluxo termina. O `stream_options={"include_usage": True}` do OpenAI é respeitado para captura de usage.

## Desenvolvimento

```bash
git clone https://github.com/Lts1sds/dashcam
cd dashcam
pip install -e ".[dev]"
pytest                       # 23 testes, sem API keys
python examples/demo_agent.py   # demo offline de loop de agente
```

## Roadmap

- [x] Captura de tool-calls MCP
- [ ] Visão de diff de prompts (o que mudou entre chamadas)
- [ ] Busca em todos os traces
- [ ] Replay de um único passo num REPL (viagem no tempo)
- [ ] Adaptadores de framework (callbacks LangChain, ponte OpenTelemetry)

## Licença

MIT
