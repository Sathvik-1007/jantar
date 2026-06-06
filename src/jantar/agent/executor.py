from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Any

from jantar.agent.classifier import classify_request
from jantar.llm.gateway import llm
from jantar.models import AgentRequest, AgentResponse
from jantar.rag.tool_rag import select_tool
from jantar.rag.knowledge_rag import retrieve_knowledge
from jantar.tools.adapters import execute_tool

logger = logging.getLogger(__name__)


ANSWER_PROMPT = """You are Jantar, an AI assistant for Indian government services.
Given the context below, compose a helpful answer for the citizen.
- If API data is provided, include the specific numbers/facts.
- If knowledge documents are provided, cite them: [Source: title, section].
- Answer in the SAME language as the user's query.
- Be concise and factual.

Context:
{context}

User query: {query}
"""

LANG_MAP = {
    "hi": "hi-IN", "en": "en-IN", "ta": "ta-IN", "te": "te-IN",
    "bn": "bn-IN", "mr": "mr-IN", "gu": "gu-IN", "kn": "kn-IN",
    "ml": "ml-IN", "pa": "pa-IN", "od": "od-IN", "or": "od-IN",
    "as": "as-IN", "ur": "ur-IN", "sa": "sa-IN", "ne": "ne-IN",
    "sd": "sd-IN", "ks": "ks-IN", "doi": "doi-IN", "kok": "kok-IN",
    "mai": "mai-IN", "brx": "brx-IN", "sat": "sat-IN", "mni": "mni-IN",
    "auto": "auto",
}

# Minimum reranker score to consider a tool relevant.
# BGE-reranker-v2-m3 sigmoid scores: >0.5 = strong match, 0.05-0.5 = possible match,
# <0.05 = irrelevant. Against a large catalog (137K+), 0.05 prevents spurious calls.
TOOL_SCORE_THRESHOLD = 0.05


async def _detect_and_translate(text: str) -> tuple[str, str]:
    """Detect language AND translate to English in a single API call.

    Sarvam's translate endpoint with source_language_code='auto' both detects
    the source language and translates in one request. No need for two calls.

    Returns:
        (english_text, detected_language_code) e.g. ("What is wheat price?", "hi")
    """
    try:
        import httpx
        from jantar.config import settings
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{settings.sarvam_base_url}/translate",
                headers={"api-subscription-key": settings.sarvam_api_key},
                json={
                    "input": text,
                    "source_language_code": "auto",
                    "target_language_code": "en-IN",
                    "model": "mayura:v1",
                    "enable_preprocessing": True,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                translated = data.get("translated_text", text)
                src = data.get("source_language_code", "en-IN")
                lang = src.split("-")[0] if "-" in src else src
                # If already English, source == translated
                if lang == "en":
                    return text, "en"
                return translated, lang
    except Exception:
        pass
    return text, "en"


async def run_agent(request: AgentRequest, memory_context: str = "") -> AgentResponse:
    """Main agent execution pipeline."""
    run_id = str(uuid.uuid4())[:8]
    t_start = time.perf_counter()
    logger.info("[%s] Agent run started | text=%r lang=%s", run_id, request.text[:80], request.language)
    audit_trail = []
    tools_used = []
    citations = []
    context_parts = []

    # 1. Detect language + translate in ONE call (not two)
    t0 = time.perf_counter()
    if request.language == "auto":
        working_query, user_lang = await _detect_and_translate(request.text)
        logger.info("[%s] Language detected=%s | elapsed=%.2fs", run_id, user_lang, time.perf_counter() - t0)
        audit_trail.append({"step": "detect_and_translate", "detected": user_lang})
    elif request.language != "en":
        user_lang = request.language
        src = LANG_MAP.get(user_lang, f"{user_lang}-IN")
        try:
            from jantar.tools.adapters.sarvam import sarvam
            working_query = await sarvam.translate(request.text, src, "en-IN")
            logger.info("[%s] Translated from %s | elapsed=%.2fs", run_id, user_lang, time.perf_counter() - t0)
            audit_trail.append({"step": "translate_input", "from": user_lang, "to": "en"})
        except Exception:
            working_query = request.text
            logger.warning("[%s] Translation failed, using raw text", run_id)
            audit_trail.append({"step": "translate_skipped", "reason": "failed"})
    else:
        user_lang = "en"
        working_query = request.text

    # 2. Classify + extract params
    t0 = time.perf_counter()
    classification = await classify_request(working_query)
    logger.info("[%s] Classified type=%s | elapsed=%.2fs", run_id, classification.get("type"), time.perf_counter() - t0)
    audit_trail.append({"step": "classify", "result": classification})

    # 3. Execute based on classification
    extracted_params = classification.get("params", {})
    domain = classification.get("domain")

    # Multi-step: delegate to planner for complex queries
    if classification["type"] == "multi_step":
        from jantar.agent.planner import run_plan
        t0 = time.perf_counter()
        answer, plan_citations, plan_tools, plan_audit = await run_plan(
            working_query, request.text, domain=domain, memory_context=memory_context,
        )
        citations = plan_citations
        tools_used = plan_tools
        audit_trail.extend(plan_audit)
        logger.info("[%s] Multi-step complete | elapsed=%.2fs steps=%d", run_id, time.perf_counter() - t0, len(plan_audit))
        total_elapsed = time.perf_counter() - t_start
        logger.info("[%s] Agent run complete | total=%.2fs tools=%s citations=%d", run_id, total_elapsed, tools_used, len(citations))
        return AgentResponse(
            answer=answer, citations=citations, tools_used=tools_used,
            plan=[classification], audit_trail=audit_trail, run_id=run_id,
        )

    if classification["type"] in ("tool_action", "hybrid"):
        tool_query = classification.get("tool_query", working_query)
        t0 = time.perf_counter()
        try:
            selected = await select_tool(tool_query, domain=domain, top_k=1)
            if selected and selected[0].get("score", 0) >= TOOL_SCORE_THRESHOLD:
                tool = selected[0]
                # Catalog entries have 'tool_name' (custom tools) or 'api_id' (data.gov.in)
                tool_name = tool.get("tool_name") or tool.get("name") or tool.get("api_id", "unknown")
                tool_title = tool.get("title", tool_name)
                tools_used.append(tool_name)
                logger.info("[%s] Tool selected=%s score=%.4f | elapsed=%.2fs", run_id, tool_title[:60], tool.get("score", 0), time.perf_counter() - t0)
                audit_trail.append({"step": "tool_selected", "tool": tool_name, "title": tool_title, "score": tool.get("score", 0)})
                t1 = time.perf_counter()
                # For data.gov.in catalog entries, pass the api_id as resource_id
                exec_params = dict(extracted_params) if isinstance(extracted_params, dict) else {}
                if tool.get("source") == "data.gov.in" and tool.get("api_id"):
                    exec_params["resource_id"] = tool["api_id"]
                    tool_name = "data_gov_dynamic"  # Route to dynamic adapter
                tool_result = await execute_tool(tool_name, exec_params)
                logger.info("[%s] Tool executed=%s | elapsed=%.2fs", run_id, tool_name, time.perf_counter() - t1)
                context_parts.append(f"API Result ({tool_title}):\n{json.dumps(tool_result, indent=2, ensure_ascii=False)}")
                audit_trail.append({"step": "tool_executed", "tool": tool_name})
            elif selected:
                rejected_name = selected[0].get("tool_name") or selected[0].get("title", "")[:60]
                logger.info("[%s] Tool rejected=%s score=%.6f < threshold %.4f", run_id, rejected_name, selected[0].get("score", 0), TOOL_SCORE_THRESHOLD)
                audit_trail.append({"step": "tool_below_threshold", "tool": rejected_name, "score": selected[0].get("score", 0)})
        except Exception as e:
            logger.error("[%s] Tool execution error: %s", run_id, e, exc_info=True)
            audit_trail.append({"step": "tool_error", "error": str(e)})

    if classification["type"] in ("knowledge_query", "hybrid"):
        knowledge_query = classification.get("knowledge_query", working_query)
        t0 = time.perf_counter()
        try:
            knowledge = await retrieve_knowledge(knowledge_query, domain=domain, top_k=3)
            for k in knowledge:
                context_parts.append(f"Document [{k['citation']['title']} — {k['citation']['section']}]:\n{k['content']}")
                citations.append(k["citation"])
            logger.info("[%s] Knowledge retrieved=%d docs | elapsed=%.2fs", run_id, len(knowledge), time.perf_counter() - t0)
            audit_trail.append({"step": "knowledge_retrieved", "count": len(knowledge)})
        except Exception as e:
            logger.error("[%s] Knowledge retrieval error: %s", run_id, e, exc_info=True)
            audit_trail.append({"step": "knowledge_error", "error": str(e)})

    # 4. Generate answer
    context = "\n\n---\n\n".join(context_parts) if context_parts else "No relevant information found."
    full_context = f"{memory_context}\n\n{context}" if memory_context else context
    messages = [
        {"role": "system", "content": ANSWER_PROMPT.format(context=full_context, query=request.text)},
        {"role": "user", "content": request.text},
    ]
    t0 = time.perf_counter()
    answer = await llm.chat(messages)
    logger.info("[%s] Answer generated | elapsed=%.2fs", run_id, time.perf_counter() - t0)
    audit_trail.append({"step": "answer_generated"})

    total_elapsed = time.perf_counter() - t_start
    logger.info("[%s] Agent run complete | total=%.2fs tools=%s citations=%d", run_id, total_elapsed, tools_used, len(citations))

    return AgentResponse(
        answer=answer,
        citations=citations,
        tools_used=tools_used,
        plan=[classification],
        audit_trail=audit_trail,
        run_id=run_id,
    )
