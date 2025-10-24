# Context Engineering Comparison: Semantic Kernel vs. Microsoft Agent Framework

This repository demonstrates how to engineer conversational context using both the **Semantic Kernel** (SK) and the **Microsoft Agent Framework** (MAF). The two implementations live side by side under `src/context_engineering/` and share common tooling and logging so you can evaluate their behaviour under identical conditions.

The code showcases:

- A state-driven workflow for each framework to highlight context mutations step by step.
- A shared context repository persisted on disk, allowing you to inspect how data changes during each phase.
- Parallel execution (thread-based) with timing metrics so you can compare performance characteristics.

## Repository Layout

```text
src/
  context_engineering/
    main.py        # Threaded orchestration and comparative logging
    sk.py          # Semantic Kernel state machine and prompt execution
    maf.py         # Microsoft Agent Framework state machine and interactions
    tools.py       # Shared utilities, context store, and decorated tool hooks
```

The `main.py` script runs both workflows in parallel, gathers their results, and prints a consolidated JSON object with timing metrics. Each implementation relies on `tools.py` for logging, environment validation, and context storage.

## Semantic Kernel vs. Microsoft Agent Framework

| Aspect                        | Semantic Kernel (SK)                                                                 | Microsoft Agent Framework (MAF)                                                        |
|------------------------------|--------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------|
| Context manipulation         | Imperative updates using kernel-decorated helpers (`SemanticKernelTools`).          | Agent tool decorators (`AgentFrameworkTools`) expose the same persistence primitives. |
| Conversation thread control  | Uses SK threads and prompt arguments with explicit context rendering.               | Uses MAF threads via `ChatAgent.get_new_thread()` and passes formatted messages.       |
| State pattern                | `SKAddInstructionsState`, `SKPlanWorkshopState`, etc.                               | `AFAddBriefingState`, `AFFirstInteractionState`, etc.                                  |
| Cleanup semantics            | Removes transient keys once the plan is ready.                                      | Replaces context in place to simulate evolving agendas.                                |
| Result capture               | Stores the latest SK answer for audit/comparison.                                   | Aggregates every facilitator response for inspection.                                  |

The common `ContextRepository` means both workflows persist their modifications to `context_store.json`. You can inspect this file to follow the evolution of context values.

## Migration Guide: From Semantic Kernel to Microsoft Agent Framework

1. **Identify Context Operations**  
   - In SK, context updates typically flow through kernel plugins or direct dictionary manipulation.  
   - In MAF, replicate these as tool functions decorated with `@ai_function` so that agents can invoke them.

2. **Refactor Execution Flow into States**  
   - Port each logical step (e.g., add instructions, gather agenda, clean up) into independent state classes inheriting from a shared base.  
   - Reuse state naming across frameworks to make parity testing straightforward.

3. **Thread Management**  
   - Replace SK thread objects with `ChatAgent.get_new_thread()` instances.  
   - Ensure messages include the formatted context produced by `_compose_dynamic_message` so that agents receive the same data SK would embed in prompts.

4. **Tool Wiring**  
   - Wrap repository helpers (store, remove, replace context) with the appropriate decorators.  
   - Register these tools when instantiating your MAF agent so the framework can call them during execution.

5. **Validation & Logging**  
   - Keep using the shared `OperationTracker` to confirm that the order and timing of operations match your expectations.  
   - After migration, run `python -m context_engineering.main` to compare the final context snapshots and response payloads.

## Running the Samples

1. Install dependencies in your activated virtual environment:

   ```bash
   uv add semantic-kernel agent-framework azure-ai-sdk python-dotenv
   ```

2. Configure the required environment variables for both frameworks:

   ```powershell
   $env:AZURE_OPENAI_ENDPOINT = "https://<your-endpoint>.openai.azure.com"
   $env:AZURE_OPENAI_CHAT_DEPLOYMENT_NAME = "<deployment-name>"
   $env:AZURE_AI_PROJECT_ENDPOINT = "https://<your-project>.agents.azure.com"
   $env:AZURE_AI_MODEL_DEPLOYMENT_NAME = "<agent-deployment>"
   ```

3. Run the comparative driver:

   ```bash
   python -m context_engineering.main
   ```

4. Inspect `context_store.json` to review the context history, and check the console logs for timing breakdowns.

## Additional Resources

- [Semantic Kernel Documentation](https://learn.microsoft.com/semantic-kernel/)
- [Microsoft Agent Framework Samples](https://github.com/microsoft/Agent-Framework-Samples)

Feel free to extend the state machines with additional steps that mirror your production workloads. The comparative scaffolding in this repository should make it easier to validate behaviour before and after a migration.
