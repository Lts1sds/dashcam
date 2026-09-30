<div align="center">

<img src="docs/logo.svg" alt="dashcam logo" width="340">

# dashcam

**La dashcam pour vos agents IA.**

Traçage, rejeu et débogage des coûts pour les applications LLM et les agents — zéro configuration, local d'abord.

[Démarrage rapide](#démarrage-rapide) · [Fonctionnement](#fonctionnement) · [Configuration](#️-configuration) · [FAQ](#faq)

[![CI](https://github.com/Lts1sds/dashcam/actions/workflows/ci.yml/badge.svg)](https://github.com/Lts1sds/dashcam/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org)
![Zero dependencies](https://img.shields.io/badge/dependencies-zero-green.svg)

[English](README.md) | [简体中文](README.zh-CN.md) | [日本語](README.ja.md) | [한국어](README.ko.md) | [Español](README.es.md) | **Français** | [Deutsch](README.de.md) | [Русский](README.ru.md) | [Português (Brasil)](README.pt-BR.md) | [हिन्दी](README.hi.md)

</div>

---

Il est 2 h du matin, votre agent a planté. *Quelle* requête a échoué ? Qu'a-t-il *réellement* envoyé ? Combien a coûté toute l'exécution, et où sont passés les tokens ?

Le dashcam d'une voiture enregistre tout silencieusement en arrière-plan — et quand quelque chose tourne mal, vous rembobinez la bande et voyez exactement ce qui s'est passé. **dashcam fait ça pour les applications LLM** : il enregistre silencieusement chaque appel LLM émis par votre programme, puis vous donne une timeline locale pour rejouer, inspecter et attribuer les échecs.

## Pourquoi dashcam

| | dashcam | LangSmith / Langfuse | débogage print() |
|---|---|---|---|
| Modifications de code nécessaires | **aucune** | SDK / décorateur | partout |
| Données quittant votre machine | **jamais** | cloud ou serveur auto-hébergé | - |
| Dépendances | **zéro** (bibliothèque standard pure) | serveur + BDD + SDK | - |
| Temps de configuration | 10 secondes | de quelques minutes à quelques heures | - |
| Suivi des coûts | intégré | variable | manuel |
| Compatible tout framework | oui (patche le SDK) | spécifique au framework | - |

## Démarrage rapide

```bash
pip install dashcam
dashcam demo        # génère des traces de démo, sans clé API
dashcam             # ouvre le tableau de bord sur http://127.0.0.1:8377
```

### Option A — zéro modification de code (recommandé)

```bash
dashcam install                          # une seule fois, écrit un hook .pth
DASHCAM=1 python your_agent.py           # c'est tout. tout est enregistré
```

Sous Windows : `set DASHCAM=1 && python your_agent.py`

### Option B — une seule ligne d'import

```python
import dashcam
dashcam.instrument()   # patche openai / anthropic / litellm / mcp s'ils sont présents
```

### Option C — frontières de trace explicites (optionnel)

```python
with dashcam.trace("refund-processing-agent") as tid:
    run_agent()   # tous les appels LLM à l'intérieur sont regroupés en une trace
```

Sans frontières explicites, les appels sont regroupés automatiquement par fil + intervalle d'activité — aucune modification de code requise.

## Ce que vous obtenez

<p align="center">
  <img src="docs/screenshot.png" alt="Tableau de bord dashcam montrant la timeline d'un agent" width="860">
</p>

- **Rejeu en timeline** — chaque appel LLM dans l'ordre, avec messages de requête complets, paramètres, outils et réponses. Cliquez sur une étape pour la déplier.
- **Étapes d'outils déduites** — dashcam compare les tableaux de messages consécutifs pour reconstruire *ce que votre agent a fait entre les appels* (exécutions d'outils, tours utilisateur) — **sans intégration de framework**.
- **Attribution des échecs** — les appels en échec reçoivent des cartes rouges avec l'exception complète. La liste des traces montre les erreurs d'un coup d'œil.
- **Comptabilité coûts et tokens** — décomptes de tokens et coûts estimés en USD par appel et par trace pour les modèles courants OpenAI / Anthropic / DeepSeek / Gemini / Qwen. Fournissez votre propre table de prix via `DASHCAM_PRICES`.
- **Support du streaming** — les réponses en streaming sont réassemblées et enregistrées, fragments de tool-calls compris.
- **Local et privé** — tout dans un seul fichier SQLite (`~/.dashcam/traces.db`). Pas de serveur, pas de compte, pas de télémétrie.

## Fonctionnement

```
                    votre programme
                         │
        appels SDK openai / anthropic / litellm / mcp
                         │
              ┌──────────▼──────────┐
              │  patcher dashcam   │   monkey-patche les points d'entrée du SDK
              │  (zéro config)      │   enregistre requête / réponse / usage
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  stockage SQLite    │   ~/.dashcam/traces.db (WAL)
              └──────────┬──────────┘
                         │
              ┌──────────▼──────────┐
              │  tableau de bord    │   http.server de la stdlib, port 8377
              │  local · coûts      │   liste des traces, timeline, export JSON
              └─────────────────────┘
```

dashcam patche les classes clientes des SDK installés au moment de l'import. Le comportement de votre programme n'est pas touché — si dashcam échoue, il échoue silencieusement et votre agent continue de tourner.

### SDK pris en charge

| SDK | points d'entrée | synchrone | asynchrone | streaming |
|---|---|---|---|---|
| openai >= 1.0 | `chat.completions.create`, `responses.create` | ✅ | ✅ | ✅ |
| anthropic | `messages.create`, `messages.stream` | ✅ | ✅ | ✅ |
| litellm | `completion`, `acompletion` | ✅ | ✅ | ✅ |
| mcp >= 1.0 | `ClientSession.call_tool`, `list_tools`, `read_resource` | — | ✅ | — |

Tout ce qui passe par ces points (LangChain, AutoGen, CrewAI, endpoints compatibles OpenAI via litellm, ...) est capturé automatiquement.

## ⚙️ Configuration

| Variable d'environnement | Défaut | Signification |
|---|---|---|
| `DASHCAM` | non définie | Si elle vaut `1`, le hook `.pth` instrumente automatiquement au démarrage de l'interpréteur |
| `DASHCAM_DB` | `~/.dashcam/traces.db` | Emplacement de la base SQLite |
| `DASHCAM_PRICES` | table intégrée | Chemin vers une table de prix JSON : `{"sous-chaîne-de-modèle": [entrée_par_mtok, sortie_par_mtok]}` |

La correspondance des prix se fait par sous-chaîne, la clé la plus longue gagne (ex. `gpt-4o-mini` bat `gpt-4o`). Les prix sont des estimations — surchargez avec votre propre table pour des chiffres de niveau facturation.

## FAQ

**Est-ce que ça ralentit mon agent ?**
L'enregistrement est une seule insertion SQLite par appel LLM (microsecondes). Vos appels LLM prennent des centaines de millisecondes. Vous ne remarquerez rien.

**Et si dashcam casse ?**
Toute la logique interne de dashcam est enveloppée défensivement — si quelque chose lève une exception à l'intérieur de dashcam, elle est silencée et votre programme continue, sans impact.

**Est-ce que des données sont envoyées quelque part ?**
Non. Aucun appel réseau, pas de télémétrie, pas de compte. Le tableau de bord se lie uniquement à 127.0.0.1.

**Comment les appels sont-ils regroupés en traces ?**
Explicitement via `dashcam.trace(name)`, ou automatiquement : les appels d'un même fil dans un intervalle d'activité de 5 minutes rejoignent la même trace. Les traces inactives se ferment automatiquement.

**Réponses en streaming ?**
Les fragments (texte, fragments de tool-calls, usage) sont accumulés et enregistrés à la fin du flux. `stream_options={"include_usage": True}` d'OpenAI est respecté pour la capture de l'usage.

## Développement

```bash
git clone https://github.com/Lts1sds/dashcam
cd dashcam
pip install -e ".[dev]"
pytest                       # 34 tests, sans clés API
python examples/demo_agent.py   # démo de boucle d'agent hors ligne
```

## Feuille de route

- [x] Capture des tool-calls MCP
- [ ] Vue diff des prompts (ce qui a changé entre les appels)
- [ ] Recherche sur toutes les traces
- [ ] Rejeu d'une seule étape dans un REPL (voyage dans le temps)
- [ ] Adaptateurs de framework (callbacks LangChain, pont OpenTelemetry)

## Licence

MIT
