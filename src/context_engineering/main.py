"""Entry point for comparing the two context-engineering workflows.

Examples
--------
>>> from context_engineering.main import execute
>>> result = execute()  # doctest: +SKIP
>>> sorted(result.keys())  # doctest: +SKIP
['agent_framework', 'comparativo', 'semantic_kernel']
"""
from __future__ import annotations

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from io import StringIO
from pathlib import Path
from time import perf_counter
from typing import Any, Dict

from context_engineering.maf import run_agent_framework_demo
from context_engineering.sk import run_semantic_kernel_demo
from context_engineering.tools import (
    ContextRepository,
    LOGGER,
    OperationTracker,
    build_comparative_table,
    log_comparative_summary,
)

if hasattr(asyncio, "WindowsSelectorEventLoopPolicy"):
	asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def execute() -> Dict[str, Any]:
	"""Run both demos in parallel threads and collect results.

	Examples
	--------
	>>> callable(execute)
	True
	"""

	repository = ContextRepository()
	tracker = OperationTracker()

	def _run_semantic_kernel() -> Dict[str, Any]:
		return asyncio.run(run_semantic_kernel_demo(repository, tracker))

	def _run_agent_framework() -> Dict[str, Any]:
		return asyncio.run(run_agent_framework_demo(repository, tracker))

	start = perf_counter()
	with ThreadPoolExecutor(max_workers=2) as executor:
		future_sk = executor.submit(_run_semantic_kernel)
		future_maf = executor.submit(_run_agent_framework)
		sk_result = future_sk.result()
		maf_result = future_maf.result()
	elapsed_ms = (perf_counter() - start) * 1000

	log_comparative_summary(tracker)
	LOGGER.info("[Comparativo] Execução paralela concluída em %.2f ms", elapsed_ms)

	comparativo = build_comparative_table(tracker)
	return {
		"semantic_kernel": sk_result,
		"agent_framework": maf_result,
		"comparativo": comparativo,
	}


def _capture_logs() -> tuple[StringIO, logging.Handler]:
	stream = StringIO()
	handler = logging.StreamHandler(stream)
	handler.setLevel(logging.INFO)
	handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
	root_logger = logging.getLogger()
	root_logger.addHandler(handler)
	return stream, handler


def _write_markdown(output: Dict[str, Any], logs: str) -> None:
	target_path = Path(__file__).with_name("comparison_result.md")
	markdown_lines = [
		"# Context Engineering Comparison",
		"",
		"## Output",
		"```json",
		json.dumps(output, ensure_ascii=False, indent=2),
		"```",
		"",
		"## Logs",
		"```text",
		logs.strip(),
		"```",
		"",
	]
	target_path.write_text("\n".join(markdown_lines), encoding="utf-8")


def main() -> None:
	log_stream, handler = _capture_logs()
	try:
		resultado = execute()
	finally:
		logging.getLogger().removeHandler(handler)
	logs = log_stream.getvalue()
	_write_markdown(resultado, logs)
	print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
	main()

