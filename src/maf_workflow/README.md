# Microsoft Agent Framework Workflow Demo

This sample wires five Microsoft Agent Framework chat agents together using the
official Python `WorkflowBuilder` API. The code in `agents.py` constructs two
workflows—`quick_schedule_review` and `schedule_allocation_end_to_end`—without
any custom orchestration layer. Supporting tools live in `tools.py`, while the
declarative `workflows.yaml` file mirrors the official Agent Framework YAML schema
for reference.

## 1. Prepare the Environment

1. Create or refresh the local virtual environment and install dependencies:
   ```bash
   bash scripts/setup_environment.sh
   ```
2. Export the required environment variables before running the workflows:
   - `AZURE_AI_PROJECT_ENDPOINT`
   - `AZURE_AI_MODEL_DEPLOYMENT_NAME`
   - (optional) `WORKFORCE_MCP_ENDPOINT` – defaults to `http://127.0.0.1:8000/mcp`
3. (Optional) start the sample MCP server if you need the workforce data sources:
   ```bash
   uvicorn mcp_server.main:app --reload
   ```

## 2. Run the Workflows

Use the Python entry point to execute the workflows directly:

```bash
python src/maf_workflow/agents.py --workflow quick_schedule_review
python src/maf_workflow/agents.py --workflow schedule_allocation_end_to_end
```

Additional flags:
- `--job` and `--target-date` override the values passed to the seed executor.
- `--disable-mcp` runs the agents without attaching MCP tools (useful when the
  sample MCP service is not running).

The script streams workflow events and writes the final payload as formatted JSON.

## 3. Declarative Workflow Reference

`workflows.yaml` contains Microsoft Agent Framework declarative workflow
definitions that mirror the two programmatic workflows. Python does not yet
consume these files, but keeping them in the official format ensures a smooth
transition once declarative workflows become available for Python.

## 4. Troubleshooting

- Ensure the required environment variables are present before running the
  script. The helper will raise a descriptive exception if a value is missing.
- MCP connection errors indicate that the sample MCP server is unavailable. Start
  it with `uvicorn mcp_server.main:app --reload` or run with `--disable-mcp`.
- The workflow output is printed at the end of each run. If no output appears,
  re-run the script with the same parameters to confirm the configuration.
