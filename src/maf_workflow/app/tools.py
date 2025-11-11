"""Tooling utilities for the Microsoft Agent Framework workflow demo.

The helpers defined here expose reusable tools that agents can call during the
schedule allocation showcase. They include HTTP integrations, local document
lookups, and constructors for Model Context Protocol (MCP) bridges so agents
can reach the workforce datasets served by the sample MCP server.
"""

import os
from pathlib import Path
from typing import Annotated, Any, Collection, Mapping

import aiohttp
import dotenv
from agent_framework import MCPStreamableHTTPTool, ai_function
from pydantic import Field


dotenv.load_dotenv()


DEFAULT_HTTP_TIMEOUT = aiohttp.ClientTimeout(total=10)
DEFAULT_PUBLIC_ENDPOINT = "https://jsonplaceholder.typicode.com/todos/1"
MCP_ENDPOINT_ENV = "WORKFORCE_MCP_ENDPOINT"
DEFAULT_MCP_URL = "http://127.0.0.1:8000/mcp"
PLAYBOOK_PATH = Path(__file__).with_name("workflow_playbook.md")


def ensure_env(var_name: str, fallback: str | None = None) -> str:
	"""Return the current value for *var_name* or raise a descriptive error."""

	value = os.getenv(var_name, fallback)
	if value:
		return value
	raise RuntimeError(f"Environment variable '{var_name}' must be defined for this workflow demo.")


def _workforce_mcp_url() -> str:
	base = os.getenv(MCP_ENDPOINT_ENV, DEFAULT_MCP_URL)
	return base.rstrip("/")


def create_workforce_mcp_tool(
	name: str,
	*,
	allowed_tools: Collection[str] | None = None,
	description: str | None = None,
) -> MCPStreamableHTTPTool:
	"""Return a configured MCP tool bound to the local workforce service."""

	return MCPStreamableHTTPTool(
		name=name,
		url=_workforce_mcp_url(),
		description=description,
		allowed_tools=tuple(allowed_tools) if allowed_tools else None,
		terminate_on_close=True,
	)


def create_schedule_mcp_tool() -> MCPStreamableHTTPTool:
	"""Bridge exposing only schedule lookups from the local MCP server."""

	return create_workforce_mcp_tool(
		name="workforce-schedule",
		allowed_tools=["workforce.get_schedule"],
		description="Return staffing schedules from the local workforce MCP server.",
	)


def create_cosmos_updates_mcp_tool() -> MCPStreamableHTTPTool:
	"""Bridge exposing update and coverage tools, simulating Cosmos DB access."""

	return create_workforce_mcp_tool(
		name="cosmos-updates",
		allowed_tools=["workforce.get_updates", "workforce.get_coverage"],
		description="Retrieve staffing updates and coverage deltas via MCP (Cosmos DB simulation).",
	)


def _resolve_playbook_path(candidate: str | None) -> Path:
	base_path = PLAYBOOK_PATH if PLAYBOOK_PATH.exists() else Path.cwd()
	if candidate:
		candidate_path = Path(candidate)
		return candidate_path if candidate_path.is_absolute() else base_path.parent / candidate_path
	return PLAYBOOK_PATH


@ai_function(
	name="fetch_public_incident_feed",
	description=(
		"Fetch JSON data from an HTTPS API to correlate external incidents with staffing decisions."
	),
)
async def fetch_public_api(
	endpoint: Annotated[
		str,
		Field(description="HTTPS endpoint returning JSON insights.")
	] = DEFAULT_PUBLIC_ENDPOINT,
	query: Annotated[
		Mapping[str, Any] | None,
		Field(description="Optional query string parameters applied to the request."),
	] = None,
) -> dict[str, Any]:
	"""Return a JSON payload retrieved from a trusted HTTPS API endpoint."""

	if not endpoint.lower().startswith("https://"):
		raise ValueError("The API endpoint must use HTTPS.")

	async with aiohttp.ClientSession(timeout=DEFAULT_HTTP_TIMEOUT) as session:
		async with session.get(endpoint, params=query or None) as response:
			if response.status >= 400:
				detail = await response.text()
				raise RuntimeError(
					f"Request to '{endpoint}' failed with status {response.status}: {detail.strip()}"
				)

			content_type = response.headers.get("Content-Type", "")
			if "json" not in content_type.lower():
				snippet = (await response.text())[:500]
				raise RuntimeError(
					f"Endpoint '{endpoint}' did not return JSON content. Received: {content_type} | {snippet}"
				)

			return await response.json()


@ai_function(
	name="load_allocation_playbook",
	description="Read guidance from a local Markdown playbook to support allocation choices.",
)
def read_local_playbook(
	relative_path: Annotated[
		str | None,
		Field(description="Optional relative path to a Markdown document to load."),
	] = None,
) -> str:
	"""Return the contents of the workflow playbook used during demonstrations."""

	path = _resolve_playbook_path(relative_path)
	if not path.exists():
		raise FileNotFoundError(f"Playbook document '{path}' was not found.")
	return path.read_text(encoding="utf-8")


__all__ = [
	"DEFAULT_PUBLIC_ENDPOINT",
	"PLAYBOOK_PATH",
	"create_cosmos_updates_mcp_tool",
	"create_schedule_mcp_tool",
	"create_workforce_mcp_tool",
	"ensure_env",
	"fetch_public_api",
	"read_local_playbook",
]
