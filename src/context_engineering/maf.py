"""Microsoft Agent Framework context-engineering demonstration.

The module implements a state machine that enriches shared context, interacts
with an Azure-hosted agent, and records timing information for comparisons with
the Semantic Kernel sample.

Examples
--------
>>> from context_engineering.maf import _compose_dynamic_message
>>> _compose_dynamic_message({'topic': 'agents'}, 'Next steps?')
'Contexto compartilhado atualizado:\n* topic: agents\n\nPergunta: Next steps?'
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List

from agent_framework import ChatAgent
from agent_framework.azure import AzureAIAgentClient
from azure.identity.aio import DefaultAzureCredential

from .tools import (
	AgentFrameworkTools,
	ContextRepository,
	OperationTracker,
	build_comparative_table,
	configure_azure_ai_environment,
	ensure_env,
)


FRAMEWORK_KEY = "agent_framework"


def _response_to_text(response: Any) -> str:
	"""Extract plain text from Agent Framework responses.

	Examples
	--------
	>>> class DummyItem:
	...     text = 'hello'
	>>> class DummyMessage:
	...     contents = [DummyItem()]
	>>> class DummyResponse:
	...     messages = [DummyMessage()]
	>>> _response_to_text(DummyResponse())
	'hello'
	"""

	messages: Iterable[Any] = getattr(response, "messages", [])
	collected: list[str] = []
	for message in messages:
		for item in getattr(message, "contents", []):
			text = getattr(item, "text", None)
			if text:
				collected.append(text)
	return "\n".join(collected) if collected else str(response)


def _compose_dynamic_message(context: Dict[str, Any], pergunta: str) -> str:
	"""Compose the dynamic briefing shared with the facilitator.

	Examples
	--------
	>>> _compose_dynamic_message({'tema': 'agentes'}, 'Próximos passos?')
	'Contexto compartilhado atualizado:\n* tema: agentes\n\nPergunta: Próximos passos?'
	"""
	linhas = [f"* {nome}: {valor}" for nome, valor in context.items()]
	contexto_formatado = "\n".join(linhas) if linhas else "(nenhum contexto local)"
	return (
		"Contexto compartilhado atualizado:\n"
		f"{contexto_formatado}\n\n"
		f"Pergunta: {pergunta}"
	)


class AgentFrameworkState(ABC):
	"""Interface for states in the Agent Framework workflow.

	Examples
	--------
	>>> issubclass(AFAddBriefingState, AgentFrameworkState)
	True
	"""

	@abstractmethod
	async def handle(self, context: "AgentFrameworkContext") -> "AgentFrameworkState | None":
		"""Realiza a ação do estado e retorna o próximo estado."""


class AgentFrameworkContext:
	"""Container holding dependencies shared by every Agent Framework state.

	Examples
	--------
	>>> from pathlib import Path
	>>> from context_engineering.tools import ContextRepository, OperationTracker
	>>> repo = ContextRepository(Path('memory.json'))
	>>> tracker = OperationTracker()
	>>> ctx = AgentFrameworkContext(repo, tracker, ChatAgent)  # doctest: +SKIP
	>>> isinstance(ctx.responses, list)  # doctest: +SKIP
	True
	"""

	initial_question = "Quais seções você sugere para iniciar o evento?"
	practice_question = "Como incorporamos uma seção prática com alterações de contexto?"
	closing_question = "Qual checklist final devemos usar para encerrar o workshop?"

	def __init__(self, repository: ContextRepository, tracker: OperationTracker, facilitator: ChatAgent) -> None:
		self.repository = repository
		self.tracker = tracker
		self.tools = AgentFrameworkTools(repository)
		self.facilitator = facilitator
		self.thread = facilitator.get_new_thread()
		self.responses: List[str] = []
		self._framework_key = FRAMEWORK_KEY

	def snapshot(self) -> Dict[str, Any]:
		return self.repository.snapshot(FRAMEWORK_KEY)

	def span(self, phase: str, action: str):
		return self.tracker.span("Agent Framework", phase, action, self.snapshot)

	def compose_message(self, pergunta: str) -> str:
		return _compose_dynamic_message(self.snapshot(), pergunta)

	def update_context(self, key: str, value: Any) -> Dict[str, Any]:
		return self.repository.update(self._framework_key, key, value)

	def replace_context(self, values: Dict[str, Any]) -> Dict[str, Any]:
		return self.repository.replace(self._framework_key, values)

	async def send_message(self, pergunta: str, phase: str, action: str) -> str:
		mensagem = self.compose_message(pergunta)
		with self.span(phase, action):
			resultado = await self.facilitator.run(mensagem, thread=self.thread)
		return _response_to_text(resultado)


class AFAddBriefingState(AgentFrameworkState):
	"""Seed the context with the initial workshop briefing.

	Examples
	--------
	>>> isinstance(AFAddBriefingState(), AgentFrameworkState)
	True
	"""

	async def handle(self, context: AgentFrameworkContext) -> AgentFrameworkState:
		with context.span("Contexto", "Adicionar briefing inicial"):
			context.update_context(
				"briefing",
				"Workshop para comparar técnicas de engenharia de contexto com SK e Agent Framework.",
			)
		return AFFirstInteractionState()


class AFFirstInteractionState(AgentFrameworkState):
	"""Trigger the first facilitator interaction.

	Examples
	--------
	>>> isinstance(AFFirstInteractionState(), AgentFrameworkState)
	True
	"""

	async def handle(self, context: AgentFrameworkContext) -> AgentFrameworkState:
		response = await context.send_message(
			context.initial_question,
			phase="Execução",
			action="Primeira interação",
		)
		context.responses.append(response)
		return AFAddDynamicContextState()


class AFAddDynamicContextState(AgentFrameworkState):
	"""Add a new key that highlights dynamic agenda requirements.

	Examples
	--------
	>>> isinstance(AFAddDynamicContextState(), AgentFrameworkState)
	True
	"""

	async def handle(self, context: AgentFrameworkContext) -> AgentFrameworkState:
		with context.span("Contexto", "Adicionar pauta dinâmica"):
			context.update_context(
				"pauta_dinamica",
				"Destacar quando remover contexto pode evitar respostas irrelevantes.",
			)
		return AFSecondInteractionState()


class AFSecondInteractionState(AgentFrameworkState):
	"""Request practical context-engineering guidance.

	Examples
	--------
	>>> isinstance(AFSecondInteractionState(), AgentFrameworkState)
	True
	"""

	async def handle(self, context: AgentFrameworkContext) -> AgentFrameworkState:
		response = await context.send_message(
			context.practice_question,
			phase="Execução",
			action="Iteração com contexto extra",
		)
		context.responses.append(response)
		return AFReplaceContextState()


class AFReplaceContextState(AgentFrameworkState):
	"""Replace transient context keys with a condensed summary.

	Examples
	--------
	>>> isinstance(AFReplaceContextState(), AgentFrameworkState)
	True
	"""

	async def handle(self, context: AgentFrameworkContext) -> AgentFrameworkState:
		ultimo_sumario = context.responses[-1] if context.responses else ""
		with context.span("Contexto", "Substituir contexto"):
			context.replace_context(
				{
					"briefing": "Reforçar próximos passos e validar checklist final.",
					"ultimo_sumario": ultimo_sumario,
				},
			)
		return AFFinalInteractionState()


class AFFinalInteractionState(AgentFrameworkState):
	"""Collect the facilitator's final checklist.

	Examples
	--------
	>>> isinstance(AFFinalInteractionState(), AgentFrameworkState)
	True
	"""

	async def handle(self, context: AgentFrameworkContext) -> AgentFrameworkState:
		response = await context.send_message(
			context.closing_question,
			phase="Execução",
			action="Checklist final",
		)
		context.responses.append(response)
		return AFPersistFinalState()


class AFPersistFinalState(AgentFrameworkState):
	"""Persist the final answer before closing the workflow.

	Examples
	--------
	>>> isinstance(AFPersistFinalState(), AgentFrameworkState)
	True
	"""

	async def handle(self, context: AgentFrameworkContext) -> AgentFrameworkState | None:
		with context.span("Contexto", "Registrar resposta final"):
			context.update_context("ultima_resposta", context.responses[-1])
		return None




async def run_agent_framework_demo(
	repository: ContextRepository,
	tracker: OperationTracker,
) -> Dict[str, Any]:
	"""Run the Agent Framework context-engineering demo.

	Examples
	--------
	>>> from pathlib import Path
	>>> from context_engineering.tools import ContextRepository, OperationTracker
	>>> repo = ContextRepository(Path('memory.json'))
	>>> tracker = OperationTracker()
	>>> asyncio.run(run_agent_framework_demo(repo, tracker))  # doctest: +SKIP
	{...}
	"""

	configure_azure_ai_environment()
	ensure_env("AZURE_AI_PROJECT_ENDPOINT")
	ensure_env("AZURE_AI_MODEL_DEPLOYMENT_NAME")

	repository.clear(FRAMEWORK_KEY)
	context: AgentFrameworkContext | None = None

	async with DefaultAzureCredential() as credential:
		async with AzureAIAgentClient(async_credential=credential) as client:
			facilitator = ChatAgent(
				name="Facilitador",
				chat_client=client,
				instructions=(
					"Você orquestra workshops de agentes inteligentes. Resuma próximos passos"
					" e verifique se o especialista concorda."
				),
			)
			context = AgentFrameworkContext(repository, tracker, facilitator)
			state: AgentFrameworkState | None = AFAddBriefingState()
			while state is not None:
				state = await state.handle(context)

	if context is None:
		raise RuntimeError("Contexto do Agent Framework não foi inicializado corretamente.")

	return {
		"framework": "Agent Framework",
		"respostas": context.responses,
		"contexto_final": repository.snapshot(FRAMEWORK_KEY),
		"metricas": build_comparative_table(tracker),
	}


if __name__ == "__main__":
	async def _runner() -> None:
		repo = ContextRepository()
		tracker = OperationTracker()
		resultado = await run_agent_framework_demo(repo, tracker)
		for resposta in resultado["respostas"]:
			print(resposta)

	asyncio.run(_runner())

