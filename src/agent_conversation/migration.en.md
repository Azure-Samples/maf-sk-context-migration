# Agent Conversation Migration Guide

## 1. Context and Vision

- **Objective**
	- Provide a structured migration from the existing Semantic Kernel (SK) scenario runner to the Microsoft Agent Framework (MAF) runner without losing workforce insights.
- **Scope**
	- Agent conversations executed from `src/agent_conversation`.
	- Scenarios defined in `scenario_definitions.py` and orchestrated through `main.py`.
- **Target Outcome**
	- Single, maintainable code path centred on MAF with equivalent tooling, logging, and scenario coverage.

## 2. Present-State Capabilities

- **Semantic Kernel Scenario Runner**
	- Loads environment variables and Azure AI deployment identifiers.
	- Creates temporary Azure AI Agents (researcher, planner) per execution.
	- Uses `ConversationToolsPlugin` to call MCP workforce endpoints (`evaluate_workforce`, `get_staff_schedule`, etc.).
	- Persists context via plugin storage and emits structured logs with `OperationTracker`.
	- Cleans up remote agents after every run to avoid resource leaks.
- **Microsoft Agent Framework Scenario Runner**
	- Validates Azure AI credentials then instantiates persistent `ChatAgent` objects (facilitator, specialist).
	- Shares MCP tooling through `@ai_function` wrappers (`store_context_tool`, `evaluate_workforce_tool`, etc.).
	- Executes multi-step conversations (kickoff, response, follow-up, wrap-up) with thread reuse.
	- Records timing metrics via `OperationTracker` and detailed middleware traces.

## 3. Migration Goals and Preserved Capabilities

- **Goals**
	- Replace SK runner with MAF while keeping scenario logic intact.
	- Standardise logging, telemetry, and MCP tool access.
	- Reduce duplicated orchestration code and maintenance overhead.
- **Capabilities to Maintain**
	- Workforce data retrieval routes (`/workforce/schedule`, `/workforce/coverage`, etc.).
	- Scenario definitions, prompts, and evaluation pathways.
	- Context persistence semantics (scenario summary, facilitator/planner contributions, follow-up notes).
	- Metrics collection enabled by `OperationTracker` and log summaries.

## 4. Detailed Migration Plan

1. **Inventory and Baseline**
	 - Review existing SK runner modules (`sk.py`, `tools.py`) and document MCP tool usage.
	 - Capture current log samples and `comparison_result.md` outputs as acceptance criteria.
2. **Align Configuration**
	 - Verify `.env` contains `AZURE_AI_PROJECT_ENDPOINT`, `AZURE_AI_MODEL_DEPLOYMENT_NAME`, and `WORKFORCE_MCP_BASE_URL`.
	 - Create a shared configuration module if additional variables emerge during migration.
3. **Enhance Tool Layer (if needed)**
	 - Ensure all workforce utilities exist as `@ai_function` definitions.
		 - `store_context_tool`
		 - `get_staff_schedule_tool`
		 - `evaluate_workforce_tool`
	 - Validate Pydantic models regenerate cleanly (already patched to use native `dict`/`list`).
4. **Map Prompts and Roles**
	 - Convert SK prompts into facilitator/specialist instructions.
		 - Kickoff prompt → facilitator kickoff message.
		 - Planner output → specialist response.
		 - Follow-up prompt → specialist follow-up step.
		 - Wrap-up prompt → facilitator wrap-up.
	 - Document mapping in scenario definition comments for future maintainers.
5. **Thread and Context Handling**
	 - Leverage `ChatAgent.get_new_thread()` to create conversation state.
	 - Replace plugin `store_context` calls with `store_context_tool` invocations inside MAF flow.
	 - Confirm context snapshots mirror SK structure (keys: `facilitator_summary`, `specialist_response`, etc.).
6. **Logging and Metrics**
	 - Ensure `OperationTracker` spans exist for each new MAF step.
		 - Context preparation.
		 - Kickoff, specialist response, follow-up, wrap-up.
	 - Retain scenario-level logs implemented in `scenario_strategies.py`.
7. **Decommission SK Runner**
	 - Once parity tests pass, mark SK implementation as deprecated.
	 - Optionally keep SK code behind a feature flag or maintain it in docs only.

## 5. Testing and Validation Strategy

- **Unit/Integration Checks**
	- Run `python src/agent_conversation/main.py` for each scenario selection (`coverage`, `forward`).
	- Inspect generated `comparison_result.md` to confirm log and output parity.
- **Data Consistency**
	- Validate MCP responses used by both frameworks return identical payloads for the same input date.
	- Confirm context snapshots contain the same derived brief strings.
- **Telemetry Review**
	- Compare elapsed time metrics before and after migration to detect regressions.
	- Monitor Azure AI telemetry (if enabled) for increased failure rates.

## 6. Risks and Mitigations

- **Risk: Tool Contract Drift**
	- *Impact*: MAF tool signatures diverge from SK usage causing runtime failures.
	- *Mitigation*: Maintain shared `tools.py` module; run linting and minimal integration tests after edits.
- **Risk: Prompt Behaviour Changes**
	- *Impact*: Different agent instructions may alter scenario outcomes.
	- *Mitigation*: Preserve prompt content verbatim during migration; capture baseline transcripts for comparison.
- **Risk: Azure AI Agent Limits**
	- *Impact*: Increased use of persistent ChatAgents could hit service quotas.
	- *Mitigation*: Clean up threads when scenarios finish; monitor Azure usage dashboards.
- **Risk: Logging Regression**
	- *Impact*: Loss of detailed metrics would hinder debugging.
	- *Mitigation*: `OperationTracker` spans must wrap every major step; verify presence in Markdown output.

## 7. Post-Migration Checklist

- [ ] SK runner removed or clearly marked as legacy.
- [ ] `comparison_result.md` reflects logs exclusively from MAF executions.
- [ ] Migration guide updated with final lessons learned (this document).
- [ ] Automation (CI/CD) configured to run the agent conversation script with sample data.

## 8. Appendix

- **Key Source Files**
	- `src/agent_conversation/main.py`
	- `src/agent_conversation/maf.py`
	- `src/agent_conversation/tools.py`
	- `src/agent_conversation/scenario_strategies.py`
- **External Dependencies**
	- `agent-framework-core`
	- `semantic-kernel`
	- `azure-identity`
	- MCP workforce FastAPI service (local host).
