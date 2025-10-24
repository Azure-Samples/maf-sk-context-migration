# Microsoft Agent Framework & Semantic Kernel Context Migration Samples

> Unified workforce intelligence, scenario planning, and context‑engineering demonstrations comparing **Microsoft Agent Framework (MAF)** and **Semantic Kernel (SK)** — plus a Model Context Protocol (MCP) FastAPI service. This repository shows how to structure multi‑agent conversations, mutate and persist conversational context, and migrate SK implementations to MAF with minimal friction.

## 1. Repository Overview

| Area | Path | Purpose |
|------|------|---------|
| Agent Conversations | `src/agent_conversation/` | Scenario‑driven dual‑framework conversations (coverage assessment & forward staffing) executed across SK and MAF, producing comparative metrics. |
| Context Engineering | `src/context_engineering/` | Side‑by‑side state machines illustrating low‑level context mutation patterns (add, replace, prune) for SK vs MAF. |
| MCP Workforce Service | `src/mcp_server/` | FastAPI + `fastapi-mcp` application exposing retail staffing datasets as MCP tools (schedule, updates, coverage recommendations). |
| Memory Management (Future) | `src/memory_management/` | Placeholder for advanced persistent / hierarchical memory experiments (currently empty — reserved for follow‑up). |
| Python Project Config | `pyproject.toml` | Dependency and tooling configuration (uv / setuptools). |
| Migration Guides (EN/PT) | `migration.en.md`, `migration.pt.md` (per module) | High‑level narrative of SK → MAF migration goals and steps (duplicated for localization). |
| Scenario Comparison Output | `comparison_result.md` (per module) | Generated markdown with JSON payload + log trace after running an entry point. |

### High‑Level Architecture (Text Diagram)

```
						  +---------------------------+
						  |  FastAPI MCP Server       |
						  |  (/workforce/* endpoints) |
						  +-------------+-------------+
										^ (HTTP/MCP)
										|
+-------------------------------+       |       +-------------------------------+
| agent_conversation            |       |       | context_engineering           |
| - scenario_strategies.py      |       |       | - maf.py (MAF state machine)  |
| - maf.py (MAF dialogue)       |       |       | - sk.py  (SK state machine)   |
| - sk.py  (SK dialogue)        |       |       | - tools.py (repo & tracker)   |
| - tools.py (MCP tools,        |<------+       | - main.py (parallel runner)   |
|             metrics)          |               |                               |
| - main.py (scenario runner)   |               |                               |
+-------------------------------+               +-------------------------------+
			^   ^                                            ^
			|   |                                            |
		Azure AI Agents (MAF & SK) <--------------------------+
			|   |
			v   v
		OperationTracker (metrics) & Context Repository (shared patterns)
```

## 2. Applications & Components

### 2.1 Agent Conversation (`src/agent_conversation`)
Focus: Execute business scenarios across both frameworks to compare interaction style, latency, and context handling.

Key files:
- `scenario_definitions.py` — Data classes (`ScenarioConfig`) capturing prompts & planning horizon.
- `scenario_strategies.py` — Strategy pattern that runs SK then MAF (or selected subset) and aggregates results.
- `maf.py` — MAF two‑agent orchestration (Facilitator + Specialist) with shared context persistence via tool calls.
- `sk.py` — SK two‑agent orchestration (Researcher + Planner) using Azure AI Agent service, ephemeral provisioning & cleanup.
- `strategy.py` — Abstract contracts & DTOs (`ConversationStrategy`, `FrameworkConversationResult`, `ScenarioResult`).
- `tools.py` — Unified logging (`OperationTracker`), environment validation, HTTP utilities to call MCP server, dual registration of tools (SK plugin & MAF `@ai_function`).
- `main.py` — Entry point reading `AGENT_SCENARIO_SELECTION` env var; writes `comparison_result.md` (JSON + logs).

Scenarios implemented:
1. `coverage_assessment` — Identify uncovered shifts and propose backfills (short planning horizon).  
2. `forward_staffing` — Multi‑day rota generation respecting labour constraints (hours/day, consecutive days, rest windows).

Conversation phases (treated as “session timeline”):
| Phase | SK Role | MAF Role | Purpose | Context Keys Added |
|-------|---------|---------|---------|--------------------|
| Kickoff | Researcher / Facilitator | Facilitator | Frame objective & summarise initial dataset | `summary`, `research` / `facilitator_summary` |
| Planning / Response | Planner / Specialist | Specialist | Produce structured allocations / recommendations | `plan` / `specialist_response` |
| Follow‑Up | Researcher | Specialist | Refine / verify gaps & action items | `follow_up` |
| Wrap‑Up | (Not SK symmetrical – optional) | Facilitator | Broadcast final plan & risk flags | `wrap_up` |

Metrics: Each phase wrapped by `OperationTracker.span()` capturing `framework`, `phase`, `action`, elapsed ms, snapshot of context.

### 2.2 Context Engineering (`src/context_engineering`)
Focus: Micro‑level context manipulation patterns (add / update / replace / remove) compared across frameworks via state machines.

Key abstractions:
| SK States | Purpose | Matching MAF States |
|-----------|---------|---------------------|
| `SKAddInstructionsState` | Seed persistent instructions | `AFAddBriefingState` |
| `SKAddAudienceState` | Audience metadata | `AFAddDynamicContextState` (dynamic agenda) |
| `SKPlanWorkshopState` | Invoke model & generate plan | `AFFirstInteractionState` / `AFSecondInteractionState` |
| `SKPersistResponseState` | Store last model answer | `AFReplaceContextState` (compress context) |
| `SKCleanupState` | Remove transient keys | `AFFinalInteractionState` / `AFPersistFinalState` |

Execution: `main.py` runs MAF + SK in parallel threads; logs aggregated timing; writes `comparison_result.md` (Portuguese localization visible in sample outputs).

### 2.3 MCP Workforce Service (`src/mcp_server`)
Focus: Provide consistent, queryable operational context as Model Context Protocol tools & REST endpoints.

Endpoints:
- `GET /health` — Readiness probe returning record count.
- `GET /workforce/schedule` — Full staffing snapshot + date range.
- `GET /workforce/updates` — Staff updates (absence, shift/role changes, new hires, transfers).
- `GET /workforce/daily-staff` — Employees scheduled for a date.
- `GET /workforce/daily-staff-updates` — Updates on a date.
- `GET /workforce/coverage` — Derived coverage insights with risk levels & recommendations.

Coverage algorithm (`utils.py`):
1. Load baseline schedule + updates (cached with `lru_cache`).
2. Apply transformations (absences → status `Unavailable`, shift/role changes, new hires, transfers).
3. Count scheduled vs available per `(date, shift, role)`; compute `delta` & risk level (`stable`, `monitor`, `critical`).
4. Filter by optional `date`, `role`, `shift` then return summarized insights.

Insights are consumed by both SK & MAF agents to ground scenario decisions.

### 2.4 Memory Management (`src/memory_management`)
Currently empty placeholder for advanced experiments:
- Hierarchical / long‑term memory compaction.
- Context windows across multi‑scenario sessions.
- Future addition: embedding store and summarization micro‑service.

## 3. Environment & Configuration

Required environment variables:
| Variable | Purpose |
|----------|---------|
| `AZURE_AI_PROJECT_ENDPOINT` | Azure AI Agents project endpoint (also normalized to `AZURE_OPENAI_ENDPOINT`). |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | Model deployment name (normalized to `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME`). |
| `AZURE_AI_MODEL_DEPLOYMENT_KEY` (optional) | API key if not using managed identity. |
| `AZURE_AI_API_VERSION` (optional) | Overrides default API version fallback. |
| `WORKFORCE_MCP_BASE_URL` | Base URL of the MCP FastAPI service (can include `/mcp` suffix; auto‑normalized). |
| `AGENT_SCENARIO_SELECTION` | Scenario selector for agent conversations (`coverage`, `forward`, `random`). |
| `AZURE_AI_AGENT_POLLING_TIMEOUT_SECONDS` | Polling timeout for SK Azure AI Agent runs. |

`tools.py` modules contain helpers (`configure_azure_ai_environment`, `ensure_env`) that remap Azure AI variable names for SK compatibility.

## 4. Running the Samples

### 4.1 Install Dependencies (uv)
```powershell
uv sync  # or: uv pip install -r pyproject.toml (implicit)
```

### 4.2 Start MCP Workforce Service
```powershell
python -m mcp_server.main  # Runs FastAPI on :8000
```

### 4.3 Run Agent Conversation Scenario(s)
```powershell
$env:WORKFORCE_MCP_BASE_URL="http://localhost:8000"
$env:AZURE_AI_PROJECT_ENDPOINT="https://<your-project>.agents.azure.com"
$env:AZURE_AI_MODEL_DEPLOYMENT_NAME="<deployment-name>"
python -m agent_conversation.main  # writes src/agent_conversation/comparison_result.md
```

Select specific scenario:
```powershell
$env:AGENT_SCENARIO_SELECTION="coverage"
python -m agent_conversation.main
```

### 4.4 Run Context Engineering Comparison
```powershell
python -m context_engineering.main  # writes src/context_engineering/comparison_result.md
```

### 4.5 Uvicorn Alternative (Hot Reload MCP)
```powershell
uvicorn mcp_server.main:app --host 0.0.0.0 --port 8000 --reload
```

## 5. Sessions, Topics & Context Model

The repository models “sessions” as the bounded execution of either:
1. A scenario strategy (`agent_conversation`) executing both frameworks sequentially.
2. A context‑engineering comparison run executing SK & MAF in parallel threads.

Topic granularity emerges from context keys recorded during each phase/state. Examples:
- Agent Conversation (MAF): `facilitator_summary`, `specialist_response`, `follow_up`, `wrap_up`, `scenario_brief`.
- Agent Conversation (SK): `research`, `plan`, `follow_up`, `scenario_brief`.
- Context Engineering (MAF): `briefing`, `pauta_dinamica`, `ultimo_sumario`, `ultima_resposta`.
- Context Engineering (SK): `instrucoes`, `ultima_resposta`.

Normalization Rules:
- Each state/phase must add or mutate at least one context key.
- Transient keys are pruned before final snapshot (`SKCleanupState`, `AFReplaceContextState`).
- Metrics always capture a snapshot so delta analysis can be performed offline.

## 6. Migration Strategies

### 6.1 Principles
| Principle | Rationale |
|-----------|-----------|
| Preserve prompt semantics verbatim initially | Avoid behaviour drift before benchmarking. |
| Centralize tool contracts in a single module | Prevent signature divergence across frameworks. |
| Use DTOs (`ScenarioConfig`, `ScenarioResult`) for comparison | Enables structural parity & JSON diffing. |
| Record phase metrics uniformly | Simplifies latency & throughput evaluation. |
| Deprecate SK only after parity acceptance | Ensures audit trail and rollback path. |

### 6.2 Scenario‑Specific Mapping

#### Coverage Assessment
| SK Role/Key | MAF Role/Key | Migration Notes |
|-------------|-------------|----------------|
| Researcher kickoff (`kickoff_message`) | Facilitator kickoff | Same business objective; keep wording. |
| Planner allocations (`planner_instructions`) | Specialist response | Convert summarised assignments to structured bullet output. |
| Follow‑up prompt (`follow_up_prompt`) | Specialist follow‑up | Consolidate unassigned shifts & confirm backfills. |
| Wrap‑up (not present in SK) | Facilitator wrap‑up | Add broadcast verification step; new `wrap_up` context key. |

#### Forward Staffing
| SK Researcher horizon summary | MAF Facilitator rota draft | Both fetch schedule & updates; MAF adds sample day briefing. |
| SK Planner rota plan | MAF Specialist validation | Maintain constraint wording: max 10 hours/day, 8 consecutive hours, 5 consecutive days. |
| SK Follow‑up briefing | MAF Facilitator wrap‑up | MAF emphasises risk watchlist (overtime, onboarding). |

### 6.3 Context Engineering Migration
| SK State | MAF State | Action |
|----------|----------|--------|
| Add instructions | Add briefing | Same semantic; rename field. |
| Add audience | Add dynamic agenda | Merge audience requirements into agenda clarity. |
| Plan workshop (invoke model) | First interaction (facilitator) | Single message wrap passes dynamic composed context. |
| Persistence of latest answer | Replace context | Replace multiple keys with condensed summary to show compaction pattern. |
| Cleanup | Final checklist + persist last answer | Adds audit key `ultima_resposta`; retains final Portuguese narrative. |

### 6.4 Memory Management (Planned)
| Feature | Proposed Migration Strategy |
|--------|-----------------------------|
| Long‑term summarization | Introduce periodic summarization tool callable by MAF agent after N operations. |
| Embedding pruning | Add vector store adapter; SK & MAF both call a neutral tool interface. |
| Multi‑session linking | Persist session index with scenario identifier; allow cross‑scenario retrieval via new MCP endpoint. |

## 7. Extensibility Guidelines

Add a new scenario:
1. Create a `ScenarioConfig` with both prompt sets (`agent_conversation/scenario_definitions.py`).
2. Implement subclass of `ScenarioConversationStrategy` if custom ordering is needed.
3. Reference in `available_strategies()` & selection logic.
4. Rerun `agent_conversation.main`; confirm new section in `comparison_result.md`.

Add a new MCP analytic:
1. Extend `WorkforceDataHook` with a derivation method (e.g., workload balance score).
2. Expose new FastAPI route; optionally mount as MCP tool via `fastapi_mcp`.
3. Register plugin/tool in `agent_conversation/tools.py` lists & SK plugin class.
4. Update prompts to consume the new insight.

Internationalization (i18n):
- Portuguese documents (`migration.pt.md`) mirror English structure.
- Context engineering workflow intentionally uses Portuguese keys to demonstrate multilingual context surfaces.
- Recommendation: keep key names language‑neutral for production; store localized display separately.

## 8. Observability & Metrics

`OperationTracker` records per‑operation spans:
```jsonc
{
  "framework": "Agent Framework",
  "phase": "Interaction",
  "action": "Facilitator kickoff",
  "elapsed_ms": 45250.56,
  "timestamp": "2025-10-24T14:00:44.752Z",
  "metadata": { "thread": "local" }
}
```
Aggregated summaries appear under `summary` or `metricas` depending on localization. Average ms allows cross‑framework comparison of conversational complexity.

Recommended additions:
- Emit token usage (if SDK exposes) per phase.
- Add structured risk scoring for forward staffing scenario (aggregate count of `critical` insights).
- Export Prometheus metrics from MCP service for schedule/update request latency.

## 9. Testing & Validation

Minimal smoke tests (proposed — not yet implemented):
- Validate environment mapping: call `configure_azure_ai_environment()` then assert transformed variables exist.
- Mock MCP endpoints (or run local) and assert coverage report includes risk levels.
- Run agent conversation with `AGENT_SCENARIO_SELECTION=random` and assert output JSON has `summary` key.

Potential test skeleton (pytest):
```python
def test_scenario_result_structure():
	from agent_conversation.main import execute
	result = execute("coverage")
	assert "coverage_assessment" in result
	payload = result["coverage_assessment"]
	assert payload["conversations"], "Conversations missing"
```

## 10. Roadmap / Future Improvements

| Area | Enhancement |
|------|-------------|
| Memory Management | Implement hierarchical summarization & vector pruning demo. |
| Tooling | Add automated diff of SK vs MAF transcripts with semantic similarity scoring. |
| Metrics | Track token counts & cost estimation per phase. |
| Deployment | Containerize MCP service; add GitHub Actions CI for smoke tests. |
| Security | Introduce secret scanning & rotate temporary keys automatically after demos. |
| Evaluation | Integrate an evaluation planner to score relevance & hallucination across baseline queries. |

## 11. FAQ

**Q: Why keep both frameworks instead of deleting SK?**  
A: Dual presence allows controlled migration benchmarking and education; deprecation occurs only after parity acceptance.

**Q: Can I point the agents directly at Azure OpenAI (non Agent service)?**  
A: Yes — environment remapping ensures SK’s Azure OpenAI connector receives compatible variables; MAF uses Azure AI Agents client.

**Q: How do I add token usage metrics?**  
A: Wrap calls to agent run methods; if SDK returns token accounting, extend `OperationLog.metadata` to include `prompt_tokens` / `completion_tokens`.

## 12. License & Attribution

Licensed under MIT (see `LICENSE.md`). Sample datasets (`daily_staff.json`, `daily_updates.json`) are synthetic and safe for educational use.

## 13. Quick Start Recap

```powershell
uv sync
python -m mcp_server.main
$env:WORKFORCE_MCP_BASE_URL="http://localhost:8000"
$env:AZURE_AI_PROJECT_ENDPOINT="https://<your-project>.agents.azure.com"
$env:AZURE_AI_MODEL_DEPLOYMENT_NAME="<deployment-name>"
python -m agent_conversation.main
python -m context_engineering.main
```

---
**End of README**

