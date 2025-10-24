"""Semantic Kernel context-engineering demonstration.

The module orchestrates a state machine that mutates a shared context store,
invokes the Semantic Kernel with Azure OpenAI, and records comparative timing
metrics.

Examples
--------
>>> from context_engineering.sk import _compose_context
>>> _compose_context({'topic': 'agents'})
'- topic: agents'
"""
from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from typing import Any, Dict

from azure.identity import DefaultAzureCredential
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.exceptions import KernelInvokeException
from semantic_kernel.functions.kernel_arguments import KernelArguments

from .tools import (
	ContextRepository,
	OperationTracker,
	SemanticKernelTools,
	build_comparative_table,
	configure_azure_ai_environment,
)


FRAMEWORK_KEY = "semantic_kernel"


def _compose_context(context: Dict[str, Any]) -> str:
	"""Render the stored context as a human-friendly list.

	Examples
	--------
	>>> _compose_context({'role': 'facilitator'})
	'- role: facilitator'
	>>> _compose_context({})
	'(no additional context)'
	"""

	sections = [f"- {key}: {value}" for key, value in context.items()]
	return "\n".join(sections) if sections else "(no additional context)"


def _resolve_chat_settings() -> tuple[str, str, str, str | None]:
	"""Resolve Azure chat completion settings from environment variables."""

	configure_azure_ai_environment()
	api_version = os.getenv("AZURE_OPENAI_API_VERSION", os.getenv("AZURE_AI_API_VERSION", "2024-10-21"))
	endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
	deployment = os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
	api_key = os.getenv("AZURE_OPENAI_API_KEY")
	if endpoint and deployment:
		return endpoint.rstrip("/"), deployment, api_version, api_key

	raise RuntimeError(
		"Missing Azure configuration. Ensure AZURE_AI_PROJECT_ENDPOINT and AZURE_AI_MODEL_DEPLOYMENT_NAME are set."
	)


def _extract_text_from_result(result: Any) -> str:
	"""Normalise Semantic Kernel responses to plain text.

	Examples
	--------
	>>> class Dummy:
	...     value = 'Hello world'
	>>> _extract_text_from_result(Dummy())
	'Hello world'
	"""

	if result is None:
		return ""
	value = getattr(result, "value", None) or getattr(result, "result", None)
	if isinstance(value, str):
		return value
	if isinstance(value, (list, tuple)):
		chunks: list[str] = []
		for item in value:
			text = getattr(item, "text", None)
			if text:
				chunks.append(text)
			elif isinstance(item, str):
				chunks.append(item)
		return "\n".join(chunks)
	message = getattr(result, "message", None)
	if message:
		return str(message)
	return str(result)


class SemanticKernelState(ABC):
	"""Interface for the Semantic Kernel context-engineering state machine.

	Examples
	--------
	>>> isinstance(SemanticKernelState.__subclasses__(), list)
	True
	"""

	@abstractmethod
	async def handle(self, context: "SemanticKernelContext") -> "SemanticKernelState | None":
		"""Executa a transição e retorna o próximo estado."""


class SemanticKernelContext:
	"""Aggregate shared dependencies for all Semantic Kernel states.

	Examples
	--------
	>>> from pathlib import Path
	>>> from context_engineering.tools import ContextRepository, OperationTracker
	>>> repo = ContextRepository(Path('memory.json'))
	>>> tracker = OperationTracker()
	>>> ctx = SemanticKernelContext(repo, tracker)  # doctest: +SKIP
	>>> isinstance(ctx.kernel, Kernel)  # doctest: +SKIP
	True
	"""

	prompt_template = (
		"Resumo de Engenharia de Contexto\n"
		"Contexto persistente:\n{contexto}\n\n"
		"Tarefa:\n{tarefa}\n\n"
		"Responda de forma estruturada."
	)
	task_description = (
		"Definir agenda de 30 minutos comparando Semantic Kernel e Microsoft Agent Framework"
		" destacando pontos de atenção para manipular contexto."
	)

	def __init__(self, repository: ContextRepository, tracker: OperationTracker) -> None:
		endpoint, deployment, api_version, api_key = _resolve_chat_settings()

		self.repository = repository
		self.tracker = tracker
		self.tools = SemanticKernelTools(repository)
		self.prompt_response: str = ""

		self.credential: DefaultAzureCredential | None = None
		self.kernel = Kernel()
		if api_key:
			chat_service = AzureChatCompletion(
				service_id="sk-chat",
				endpoint=endpoint,
				deployment_name=deployment,
				api_key=api_key,
				api_version=api_version,
			)
		else:
			self.credential = DefaultAzureCredential()
			chat_service = AzureChatCompletion(
				service_id="sk-chat",
				endpoint=endpoint,
				deployment_name=deployment,
				credential=self.credential,
				api_version=api_version,
			)
		self.kernel.add_service(chat_service)

	def snapshot(self) -> Dict[str, Any]:
		return self.repository.snapshot(FRAMEWORK_KEY)

	def span(self, phase: str, action: str):
		return self.tracker.span("Semantic Kernel", phase, action, self.snapshot)

	def compose_prompt_arguments(self) -> KernelArguments:
		contexto = _compose_context(self.snapshot())
		return KernelArguments(contexto=contexto, tarefa=self.task_description)

	def close(self) -> None:
		if self.credential:
			self.credential.close()


class SKAddInstructionsState(SemanticKernelState):
	"""Populate the shared context with facilitator instructions.

	Examples
	--------
	>>> isinstance(SKAddInstructionsState(), SemanticKernelState)
	True
	"""

	async def handle(self, context: SemanticKernelContext) -> SemanticKernelState:
		with context.span("Contexto", "Adicionar instruções"):
			context.tools.store_context(
				FRAMEWORK_KEY,
				"instrucoes",
				(
					"Você é um especialista em workshops técnicos. Seja objetivo, organize a resposta"
					" em tópicos e finalize com um checklist para o time."
				),
			)
		return SKAddAudienceState()


class SKAddAudienceState(SemanticKernelState):
	"""Introduce the target audience metadata before planning.

	Examples
	--------
	>>> isinstance(SKAddAudienceState(), SemanticKernelState)
	True
	"""

	async def handle(self, context: SemanticKernelContext) -> SemanticKernelState:
		with context.span("Contexto", "Adicionar público-alvo"):
			context.tools.store_context(
				FRAMEWORK_KEY,
				"publico_alvo",
				"Equipe de arquitetura que ainda não domina agentes inteligentes.",
			)
		return SKPlanWorkshopState()


class SKPlanWorkshopState(SemanticKernelState):
	"""Call the Semantic Kernel to design the workshop agenda.

	Examples
	--------
	>>> isinstance(SKPlanWorkshopState(), SemanticKernelState)
	True
	"""

	async def handle(self, context: SemanticKernelContext) -> SemanticKernelState:
		try:
			with context.span("Execução", "Planejar workshop"):
				result = await context.kernel.invoke_prompt(
					prompt=context.prompt_template,
					arguments=context.compose_prompt_arguments(),
				)
			context.prompt_response = _extract_text_from_result(result)
		except KernelInvokeException as exc:
			context.prompt_response = f"Falha ao invocar o kernel: {exc}"
		return SKPersistResponseState()


class SKPersistResponseState(SemanticKernelState):
	"""Persist the latest Semantic Kernel answer for subsequent states.

	Examples
	--------
	>>> isinstance(SKPersistResponseState(), SemanticKernelState)
	True
	"""

	async def handle(self, context: SemanticKernelContext) -> SemanticKernelState:
		with context.span("Contexto", "Adicionar resposta recente"):
			context.tools.store_context(FRAMEWORK_KEY, "ultima_resposta", context.prompt_response)
		return SKCleanupState()


class SKCleanupState(SemanticKernelState):
	"""Remove transient keys from the context before finishing.

	Examples
	--------
	>>> isinstance(SKCleanupState(), SemanticKernelState)
	True
	"""

	async def handle(self, context: SemanticKernelContext) -> SemanticKernelState | None:
		with context.span("Contexto", "Remover público-alvo"):
			context.tools.remove_context(FRAMEWORK_KEY, "publico_alvo")
		return None


async def run_semantic_kernel_demo(
	repository: ContextRepository,
	tracker: OperationTracker,
) -> Dict[str, Any]:
	"""Run the Semantic Kernel context-engineering demo.

	Examples
	--------
	>>> from pathlib import Path
	>>> from context_engineering.tools import ContextRepository, OperationTracker
	>>> repo = ContextRepository(Path('memory.json'))
	>>> tracker = OperationTracker()
	>>> asyncio.run(run_semantic_kernel_demo(repo, tracker))  # doctest: +SKIP
	{...}
	"""

	repository.clear(FRAMEWORK_KEY)
	context = SemanticKernelContext(repository, tracker)

	state: SemanticKernelState | None = SKAddInstructionsState()
	while state is not None:
		state = await state.handle(context)

	contexto_final = repository.snapshot(FRAMEWORK_KEY)
	context.close()

	return {
		"framework": "Semantic Kernel",
		"resposta": context.prompt_response,
		"contexto_final": contexto_final,
		"metricas": build_comparative_table(tracker),
	}


if __name__ == "__main__":
	async def _runner() -> None:
		repo = ContextRepository()
		tracker = OperationTracker()
		resultado = await run_semantic_kernel_demo(repo, tracker)
		print(resultado["resposta"])

	asyncio.run(_runner())

