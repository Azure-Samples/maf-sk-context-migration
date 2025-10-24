"""Shared utilities for the context-engineering demonstrations.

The helpers collected here keep the Semantic Kernel and Microsoft Agent
Framework samples aligned regarding context persistence, logging, and metrics.

Examples
--------
>>> tracker = OperationTracker()
>>> with tracker.span("Framework", "Phase", "Action", lambda: {"step": 1}):
...     pass
>>> build_comparative_table(tracker)[0]["framework"]
'Framework'
"""
from __future__ import annotations

import json
import logging
import os
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Annotated, Any, Callable, Dict, Iterable, List, Mapping

from agent_framework import ai_function
from dotenv import load_dotenv
from pydantic import Field
from semantic_kernel.functions import kernel_function


load_dotenv()


LOGGER_NAME = "context_engineering"
DEFAULT_STORE_PATH = Path(__file__).with_name("context_store.json")


def configure_logging(level: int = logging.INFO) -> logging.Logger:
	"""Configure a single shared logger for the demos.

	Examples
	--------
	>>> logger = configure_logging()
	>>> logger.name
	'context_engineering'
	"""

	logger = logging.getLogger(LOGGER_NAME)
	if not logger.handlers:
		handler = logging.StreamHandler()
		handler.setFormatter(
			logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
		)
		logger.setLevel(level)
		logger.addHandler(handler)
		logger.propagate = False
	return logger


LOGGER = configure_logging()


def _normalize_project_endpoint(endpoint: str) -> str:
	marker = "/api/projects"
	lower_endpoint = endpoint.lower()
	if marker in lower_endpoint:
		prefix, _ = endpoint.split(marker, 1)
		return prefix.rstrip("/")
	return endpoint.rstrip("/")


def configure_azure_ai_environment() -> None:
	"""Expose Azure AI variables using the Azure OpenAI names expected by SDKs."""

	project_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
	if project_endpoint and not os.getenv("AZURE_OPENAI_ENDPOINT"):
		os.environ["AZURE_OPENAI_ENDPOINT"] = _normalize_project_endpoint(project_endpoint)

	deployment_name = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME")
	if deployment_name and not os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"):
		os.environ["AZURE_OPENAI_CHAT_DEPLOYMENT_NAME"] = deployment_name

	deployment_key = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_KEY")
	if deployment_key and not os.getenv("AZURE_OPENAI_API_KEY"):
		os.environ["AZURE_OPENAI_API_KEY"] = deployment_key

	api_version = os.getenv("AZURE_AI_API_VERSION")
	if api_version and not os.getenv("AZURE_OPENAI_API_VERSION"):
		os.environ["AZURE_OPENAI_API_VERSION"] = api_version


def ensure_env(var_name: str, fallback: str | None = None) -> str:
	"""Return an environment variable or raise a descriptive error.

	Examples
	--------
	>>> import os
	>>> os.environ['EXAMPLE_ENV'] = 'value'
	>>> ensure_env('EXAMPLE_ENV')
	'value'
	"""

	value = os.getenv(var_name, fallback)
	if value:
		return value
	raise RuntimeError(
		f"A variável de ambiente '{var_name}' precisa estar definida para executar a demonstração."
	)


@dataclass(slots=True)
class OperationLog:
	"""Capture a single tracked operation for comparative metrics.

	Examples
	--------
	>>> log = OperationLog('Framework', 'Phase', 'Action', 10.5, {'k': 'v'}, datetime.now(timezone.utc))
	>>> isinstance(log.as_dict(), dict)
	True
	"""

	framework: str
	phase: str
	action: str
	elapsed_ms: float
	context_snapshot: Mapping[str, Any]
	timestamp: datetime

	def as_dict(self) -> Dict[str, Any]:
		record = asdict(self)
		record["timestamp"] = self.timestamp.isoformat()
		record["context_snapshot"] = dict(self.context_snapshot)
		return record


class ContextRepository:
	"""Persist conversational context in a JSON file.

	Examples
	--------
	>>> from tempfile import TemporaryDirectory
	>>> with TemporaryDirectory() as tmp:
	...     repo = ContextRepository(Path(tmp) / 'context.json')
	...     repo.update('fw', 'key', 'value')
	...     repo.snapshot('fw')['key']
	'value'
	"""

	def __init__(self, store_path: Path | str | None = None) -> None:
		path = Path(store_path) if store_path else DEFAULT_STORE_PATH
		self._path = path
		self._lock = Lock()
		self._state: Dict[str, Dict[str, Any]] = self._load()

	def _load(self) -> Dict[str, Dict[str, Any]]:
		if not self._path.exists():
			return {}
		try:
			with self._path.open("r", encoding="utf-8") as handle:
				return json.load(handle)
		except json.JSONDecodeError:
			LOGGER.warning("Contexto persistido estava corrompido. Reiniciando estado.")
			return {}

	def _persist(self) -> None:
		self._path.parent.mkdir(parents=True, exist_ok=True)
		with self._path.open("w", encoding="utf-8") as handle:
			json.dump(self._state, handle, ensure_ascii=True, indent=2)

	def snapshot(self, framework: str) -> Dict[str, Any]:
		with self._lock:
			return dict(self._state.get(framework, {}))

	def update(self, framework: str, key: str, value: Any) -> Dict[str, Any]:
		with self._lock:
			bucket = self._state.setdefault(framework, {})
			bucket[key] = value
			self._persist()
			return dict(bucket)

	def replace(self, framework: str, values: Mapping[str, Any]) -> Dict[str, Any]:
		with self._lock:
			self._state[framework] = dict(values)
			self._persist()
			return dict(self._state[framework])

	def remove(self, framework: str, key: str) -> Dict[str, Any]:
		with self._lock:
			bucket = self._state.setdefault(framework, {})
			bucket.pop(key, None)
			self._persist()
			return dict(bucket)

	def clear(self, framework: str) -> None:
		with self._lock:
			self._state.pop(framework, None)
			self._persist()


class OperationTracker:
	"""Collect execution spans for later comparison between frameworks.

	Examples
	--------
	>>> tracker = OperationTracker()
	>>> with tracker.span('Demo', 'Phase', 'Action', lambda: {'flag': True}):
	...     pass
	>>> len(tracker.to_dict())
	1
	"""

	def __init__(self) -> None:
		self._records: List[OperationLog] = []
		self._lock = Lock()

	@property
	def records(self) -> Iterable[OperationLog]:
		with self._lock:
			return list(self._records)

	@contextmanager
	def span(
		self,
		framework: str,
		phase: str,
		action: str,
		context_supplier: Callable[[], Mapping[str, Any]],
	):
		start = perf_counter()
		try:
			yield
		finally:
			elapsed_ms = (perf_counter() - start) * 1000
			snapshot = dict(context_supplier())
			record = OperationLog(
				framework=framework,
				phase=phase,
				action=action,
				elapsed_ms=elapsed_ms,
				context_snapshot=snapshot,
				timestamp=datetime.now(timezone.utc),
			)
			with self._lock:
				self._records.append(record)
			LOGGER.info(
				"[%s] %s - %s | %.1f ms | contexto=%s",
				framework,
				phase,
				action,
				elapsed_ms,
				snapshot,
			)

	def to_dict(self) -> List[Dict[str, Any]]:
		return [record.as_dict() for record in self._records]


def build_comparative_table(tracker: OperationTracker) -> List[Dict[str, Any]]:
	"""Aggregate metrics in a CLI-friendly structure.

	Examples
	--------
	>>> tracker = OperationTracker()
	>>> with tracker.span('Framework', 'Phase', 'Action', lambda: {}):
	...     pass
	>>> build_comparative_table(tracker)[0]['framework']
	'Framework'
	"""

	grouped: Dict[str, Dict[str, float]] = {}
	for record in tracker.records:
		bucket = grouped.setdefault(record.framework, {"tempo_total_ms": 0.0, "operacoes": 0})
		bucket["tempo_total_ms"] += record.elapsed_ms
		bucket["operacoes"] += 1
	formatted: List[Dict[str, Any]] = []
	for framework, metrics in grouped.items():
		formatted.append(
			{
				"framework": framework,
				"operacoes": metrics["operacoes"],
				"tempo_total_ms": round(metrics["tempo_total_ms"], 2),
				"tempo_medio_ms": round(
					metrics["tempo_total_ms"] / metrics["operacoes"], 2
				),
			}
		)
	return formatted


def log_comparative_summary(tracker: OperationTracker) -> None:
	"""Log a concise summary comparing the tracked frameworks.

	Examples
	--------
	>>> tracker = OperationTracker()
	>>> with tracker.span('Framework', 'Phase', 'Action', lambda: {}):
	...     pass
	>>> log_comparative_summary(tracker)
	"""

	summary = build_comparative_table(tracker)
	for entry in summary:
		LOGGER.info(
			"[Comparativo] %s | operações=%s | tempo_total=%.2f ms | tempo_médio=%.2f ms",
			entry["framework"],
			entry["operacoes"],
			entry["tempo_total_ms"],
			entry["tempo_medio_ms"],
		)


class SemanticKernelTools:
	"""Expose repository helpers as Semantic Kernel kernel functions.

	Examples
	--------
	>>> tools = SemanticKernelTools(ContextRepository(Path('memory.json')))
	>>> tools.store_context('fw', 'key', 'value')  # doctest: +SKIP
	{'key': 'value'}
	"""

	def __init__(self, repository: ContextRepository) -> None:
		self._repository = repository

	@kernel_function(name="store_context", description="Armazena ou atualiza uma propriedade de contexto persistente.")
	def store_context(self, framework: str, key: str, value: Any) -> Dict[str, Any]:
		return self._repository.update(framework, key, value)

	@kernel_function(name="remove_context", description="Remove uma chave específica do contexto persistente.")
	def remove_context(self, framework: str, key: str) -> Dict[str, Any]:
		return self._repository.remove(framework, key)

	@kernel_function(name="replace_context", description="Substitui o contexto completo por novos valores.")
	def replace_context(self, framework: str, values: Mapping[str, Any]) -> Dict[str, Any]:
		return self._repository.replace(framework, values)


class AgentFrameworkTools:
	"""Expose repository helpers as Microsoft Agent Framework tools.

	Examples
	--------
	>>> tools = AgentFrameworkTools(ContextRepository(Path('memory.json')))
	>>> tools.store_context('fw', 'key', 'value')  # doctest: +SKIP
	{'key': 'value'}
	"""

	def __init__(self, repository: ContextRepository) -> None:
		self._repository = repository

	@ai_function(name="store_context", description="Atualiza o contexto compartilhado com uma nova informação.")
	def store_context(
		self,
		framework: Annotated[str, Field(description="Identificador do framework responsável pelo contexto.")],
		key: Annotated[str, Field(description="Chave do contexto a ser atualizada.")],
		value: Annotated[Any, Field(description="Valor a ser aplicado à chave de contexto.")],
	) -> Dict[str, Any]:
		return self._repository.update(framework, key, value)

	@ai_function(name="remove_context", description="Remove uma chave do contexto mantido localmente.")
	def remove_context(
		self,
		framework: Annotated[str, Field(description="Identificador do framework responsável pelo contexto.")],
		key: Annotated[str, Field(description="Chave que será removida do contexto.")],
	) -> Dict[str, Any]:
		return self._repository.remove(framework, key)

	@ai_function(name="replace_context", description="Substitui todo o contexto por um novo mapeamento.")
	def replace_context(
		self,
		framework: Annotated[str, Field(description="Identificador do framework responsável pelo contexto.")],
		values: Annotated[Mapping[str, Any], Field(description="Novo contexto completo." )],
	) -> Dict[str, Any]:
		return self._repository.replace(framework, values)

