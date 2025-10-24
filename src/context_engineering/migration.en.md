# Context Engineering Migration Guide

## 1. Context and Goals

- **Objective**
  - Provide a granular plan to consolidate the context engineering demo onto the Microsoft Agent Framework (MAF) without losing data preparation or analysis capabilities.
- **Scope**
  - Modules inside `src/context_engineering` (`main.py`, `maf.py`, `sk.py`, `tools.py`).
  - Workflows that build workforce snapshots and produce comparison reports.
- **Desired Outcome**
  - Single MAF-based pipeline producing identical context documents, metrics, and Markdown artifacts as the existing Semantic Kernel (SK) version.

## 2. Existing Capabilities

- **Semantic Kernel Demo**
  - Loads environment configuration and sets up SK services for Azure OpenAI-style completions.
  - Uses repository helpers to fetch MCP workforce data (coverage, staffing, priority signals).
  - Orchestrates intent planning, content drafting, and refinement loops via SK prompts.
  - Tracks elapsed times with `OperationTracker` and consolidates outputs into the comparison report.
- **Microsoft Agent Framework Demo**
  - Validates Azure AI credentials and initializes the Azure AI Agent Client.
  - Registers MCP-backed tools through `@ai_function` to expose the same repository helpers.
  - Creates facilitator and analyst ChatAgents with instructions mirroring SK prompts.
  - Runs kickoff, collaboration, and closeout phases within persistent threads to keep state.
  - Persists context snapshots and telemetry through shared tracker utilities.

## 3. Migration Targets and Preserved Features

- **Targets**
  - Eliminate duplicate orchestration logic while retaining shared tool definitions.
  - Ensure Markdown output (`comparison_result.md`) remains structurally identical.
- **Preserved Features**
  - Workforce dataset ingestion via MCP endpoints.
  - Timing metrics and scenario labels emitted by `OperationTracker`.
  - Context repository outputs (cover summaries, staffing recommendations, risk notes).
  - CLI experience for running comparisons (`python src/context_engineering/main.py`).

## 4. Detailed Migration Plan

1. **Baseline Capture**
   - Run both SK and MAF demos to obtain reference JSON and Markdown outputs.
   - Record any discrepancies in context sections or telemetry fields.
2. **Configuration Alignment**
   - Confirm identical `.env` variables for Azure endpoint, deployment, and MCP base URL.
   - Add missing entries to documentation or `.env.sample` if needed.
3. **Tool Interface Audit**
   - Review `tools.py` to verify `@ai_function` wrappers accept the same arguments used by SK.
   - Update type hints to broad structures (`dict`, `list`) to keep schema generation stable.
4. **Prompt Translation**
   - Map SK planner and responder prompts to facilitator/analyst instructions within MAF.
   - Use shared constants or utility functions to reduce drift between versions.
5. **Thread and Context Handling**
   - Replace SK-specific memory management with explicit calls to `store_context_tool` in MAF flows.
   - Maintain a single `ChatThread` per scenario run to capture conversation history.
6. **Logging Consistency**
   - Ensure each major phase (prepare data, build brief, craft insights) remains wrapped by `OperationTracker`.
   - Keep structured logging enhancements added in `scenario_strategies.py` for per-framework timing.
7. **Deprecate SK Paths**
   - After validation, remove or flag SK orchestration code while retaining shared utilities.
   - Update README references to point to the MAF implementation as canonical.

## 5. Validation Strategy

- **Functional Checks**
  - Execute `python src/context_engineering/main.py` and compare generated Markdown to the captured baseline.
  - Verify that summaries, recommendations, and risk tables match line by line.
- **Telemetry Review**
  - Confirm `OperationTracker` sections contain matching durations and step names.
- **Regression Testing**
  - Run scenario comparisons across different days in `daily_updates.json` to ensure robustness.

## 6. Risks and Mitigations

- **Tool Contract Drift**
  - *Risk*: Changing tool signatures could break either orchestration flow.
  - *Mitigation*: Manage all MCP tool definitions centrally and add lightweight unit tests.
- **Prompt Behaviour Variance**
  - *Risk*: MAF agents produce longer or shorter briefs than SK.
  - *Mitigation*: Keep prompts aligned and review outputs during baseline capture.
- **Telemetry Gaps**
  - *Risk*: Removal of SK may drop certain log fields.
  - *Mitigation*: Audit `comparison_result.md` for parity before disabling SK code paths.
- **Azure Quotas**
  - *Risk*: Additional MAF runs increase Azure AI consumption.
  - *Mitigation*: Monitor usage metrics and re-use agent threads when feasible.

## 7. Post-Migration Checklist

- [ ] Only MAF execution path enabled in `main.py`.
- [ ] Documentation references updated from SK to MAF.
- [ ] Comparison Markdown validated for both sample datasets.
- [ ] CI pipeline includes regression run for context engineering demo.

## 8. Appendix

- **Key Files**
  - `src/context_engineering/main.py`
  - `src/context_engineering/maf.py`
  - `src/context_engineering/tools.py`
  - `src/context_engineering/sk.py` (legacy reference during migration)
- **External Dependencies**
  - `agent-framework-core`
  - `semantic-kernel`
  - `azure-identity`
  - Workforce MCP service (FastAPI).
