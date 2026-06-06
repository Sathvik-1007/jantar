"""Plan-and-Execute agent with adaptive replanning.

For multi-step queries, the LLM decomposes into sub-steps upfront, then
executes each step through the existing RAG/tool infrastructure. After each
step, evaluates whether to continue, replan, or synthesize.

Design: Plan-and-Execute hybrid (LangChain 2026 recommendation):
- Fewer LLM calls than pure ReAct (plan upfront, not per-step)
- Adaptive: can replan if a step returns unexpected data
- Capped at MAX_STEPS to prevent runaway loops
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from json_repair import repair_json

from jantar.llm.gateway import llm
from jantar.rag.tool_rag import select_tool
from jantar.rag.knowledge_rag import retrieve_knowledge
from jantar.tools.adapters import execute_tool

logger = logging.getLogger(__name__)

MAX_STEPS = 5

_PLAN_PROMPT = """You are a planning agent for Indian government services.
Break this query into sequential steps. Each step should be ONE atomic action.

Step types:
- "tool_search": search for and call an API (weather, prices, IFSC, pincode, etc.)
- "knowledge_search": find information from stored government documents
- "synthesize": combine all previous results into a final answer

Rules:
- Max {max_steps} steps total
- Last step MUST be "synthesize"
- Only use tool_search when live data is needed
- Extract relevant params (commodity, city, state, pincode, etc.)

{memory_context}

Query: {query}

Return ONLY valid JSON array:
[
  {{"step": 1, "type": "knowledge_search", "query": "...", "reason": "..."}},
  {{"step": 2, "type": "tool_search", "query": "...", "params": {{}}, "reason": "..."}},
  {{"step": 3, "type": "synthesize", "reason": "combine results"}}
]"""

_SHOULD_CONTINUE_PROMPT = """Given the plan and results so far, should we:
1. "continue" - proceed to next step
2. "replan" - the results changed what we need to do
3. "synthesize" - we have enough to answer

Plan: {plan}
Completed steps with results: {results}
Next planned step: {next_step}

Return ONE word: continue, replan, or synthesize."""

_SYNTHESIZE_PROMPT = """You are Jantar, an AI assistant for Indian government services.
Synthesize all the information below into a single, comprehensive answer.
- Answer in the SAME language as the user's original query.
- Cite sources: [Source: title, section].
- Be concise and factual.
- If API data AND documents are both available, combine them.

{memory_context}

User query: {query}

Gathered information:
{results}"""


@dataclass
class StepResult:
    step_num: int
    step_type: str
    query: str
    result: str = ""
    citations: list[dict] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)


async def create_plan(query: str, memory_context: str = "") -> list[dict[str, Any]]:
    """Ask LLM to decompose query into steps."""
    prompt = _PLAN_PROMPT.format(query=query, max_steps=MAX_STEPS, memory_context=memory_context)
    try:
        raw = await llm.chat_structured([{"role": "user", "content": prompt}])
        result = repair_json(raw, return_objects=True)
        if isinstance(result, list) and len(result) > 0:
            # Ensure last step is synthesize and cap at MAX_STEPS
            steps = result[:MAX_STEPS]
            if steps[-1].get("type") != "synthesize":
                steps.append({"step": len(steps) + 1, "type": "synthesize", "reason": "combine results"})
            return steps[:MAX_STEPS]
    except Exception as e:
        logger.error("Plan creation failed: %s", e)
    # Fallback: simple 2-step plan (search + synthesize)
    return [
        {"step": 1, "type": "knowledge_search", "query": query, "reason": "find relevant info"},
        {"step": 2, "type": "synthesize", "reason": "answer the query"},
    ]


async def execute_step(step: dict[str, Any], domain: str | None = None) -> StepResult:
    """Execute a single step from the plan."""
    step_num = step.get("step", 0)
    step_type = step.get("type", "knowledge_search")
    step_query = step.get("query", "")
    params = step.get("params", {})

    result = StepResult(step_num=step_num, step_type=step_type, query=step_query)
    t0 = time.perf_counter()

    if step_type == "tool_search":
        try:
            selected = await select_tool(step_query, domain=domain, top_k=1)
            if selected and selected[0].get("score", 0) >= 0.05:
                tool = selected[0]
                tool_name = tool.get("tool_name") or tool.get("api_id", "unknown")
                exec_params = dict(params) if isinstance(params, dict) else {}
                if tool.get("source") == "data.gov.in" and tool.get("api_id"):
                    exec_params["resource_id"] = tool["api_id"]
                    tool_name = "data_gov_dynamic"
                tool_result = await execute_tool(tool_name, exec_params)
                result.result = json.dumps(tool_result, ensure_ascii=False)[:1000]
                result.tools_used.append(tool.get("title", tool_name)[:60])
            else:
                result.result = "No relevant API found for this query."
        except Exception as e:
            result.result = f"Tool execution error: {e}"

    elif step_type == "knowledge_search":
        try:
            knowledge = await retrieve_knowledge(step_query, domain=domain, top_k=3)
            parts = []
            for k in knowledge:
                parts.append(f"[{k['citation']['title']} — {k['citation']['section']}]: {k['content'][:300]}")
                result.citations.append(k["citation"])
            result.result = "\n".join(parts) if parts else "No relevant documents found."
        except Exception as e:
            result.result = f"Knowledge retrieval error: {e}"

    logger.info("Step %d (%s) | elapsed=%.2fs", step_num, step_type, time.perf_counter() - t0)
    return result


async def run_plan(
    query: str,
    original_text: str,
    domain: str | None = None,
    memory_context: str = "",
) -> tuple[str, list[dict], list[str], list[dict]]:
    """Execute the full plan-and-execute loop.

    Returns: (answer, citations, tools_used, audit_trail)
    """
    audit_trail = []
    all_citations = []
    all_tools = []

    # 1. Create plan
    t0 = time.perf_counter()
    steps = await create_plan(query, memory_context)
    logger.info("Plan created | steps=%d elapsed=%.2fs", len(steps), time.perf_counter() - t0)
    audit_trail.append({"step": "plan_created", "plan": [s.get("reason", "") for s in steps]})

    # 2. Execute steps (except synthesize)
    results: list[StepResult] = []
    for step in steps:
        if step.get("type") == "synthesize":
            break

        step_result = await execute_step(step, domain=domain)
        results.append(step_result)
        all_citations.extend(step_result.citations)
        all_tools.extend(step_result.tools_used)
        audit_trail.append({
            "step": f"executed_step_{step_result.step_num}",
            "type": step_result.step_type,
            "query": step_result.query[:60],
        })

    # 3. Synthesize
    gathered = "\n\n".join(
        f"Step {r.step_num} ({r.step_type}): {r.query}\nResult: {r.result}"
        for r in results
    )
    synth_prompt = _SYNTHESIZE_PROMPT.format(
        query=original_text,
        results=gathered,
        memory_context=memory_context,
    )
    t0 = time.perf_counter()
    answer = await llm.chat([{"role": "user", "content": synth_prompt}])
    logger.info("Synthesis | elapsed=%.2fs", time.perf_counter() - t0)
    audit_trail.append({"step": "synthesized"})

    return answer, all_citations, all_tools, audit_trail
