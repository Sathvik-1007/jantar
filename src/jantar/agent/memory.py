"""Progressive Summary Buffer for conversation memory.

Keeps last N turns in full fidelity. When buffer overflows, the oldest turns
are compressed into a running summary via a single LLM call. This gives the
agent conversational context while keeping prompt size bounded.

Design based on LangChain's ConversationSummaryBufferMemory pattern (2026)
and Mem0's research on 80-90% token savings via progressive summarization.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from jantar.llm.gateway import llm

logger = logging.getLogger(__name__)

_SUMMARIZE_PROMPT = """Compress the following conversation history into a concise summary.
Preserve: key facts, user preferences, resolved questions, active thread of inquiry.
Drop: filler, repetition, pleasantries. Max 150 words.

Existing summary (if any):
{existing_summary}

Older messages to compress:
{messages}

Updated summary:"""

MAX_BUFFER = 4  # Keep last 4 full turns before summarizing


@dataclass
class Turn:
    query: str
    answer: str
    language: str = "en"


@dataclass
class ConversationMemory:
    """Within-session memory with progressive summarization."""

    summary: str = ""
    buffer: list[Turn] = field(default_factory=list)

    def add(self, query: str, answer: str, language: str = "en") -> None:
        self.buffer.append(Turn(query=query, answer=answer, language=language))

    def needs_summarization(self) -> bool:
        return len(self.buffer) > MAX_BUFFER

    async def maybe_summarize(self) -> None:
        """Compress oldest turns into summary if buffer overflows."""
        if not self.needs_summarization():
            return
        # Move oldest 2 turns into the summarization input
        to_summarize = self.buffer[:2]
        self.buffer = self.buffer[2:]
        msgs = "\n".join(f"User: {t.query}\nAssistant: {t.answer}" for t in to_summarize)
        prompt = _SUMMARIZE_PROMPT.format(existing_summary=self.summary or "(none)", messages=msgs)
        try:
            self.summary = await llm.chat(
                [{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=300,
            )
            logger.info("Memory summarized | buffer=%d summary_len=%d", len(self.buffer), len(self.summary))
        except Exception as e:
            logger.warning("Summarization failed: %s", e)
            # Fallback: just concatenate as raw text
            self.summary += f"\n{msgs}"

    def get_context(self) -> str:
        """Return formatted memory context for injection into prompts."""
        if not self.summary and not self.buffer:
            return ""
        parts = []
        if self.summary:
            parts.append(f"Conversation summary: {self.summary}")
        if self.buffer:
            recent = "\n".join(f"User: {t.query}\nAssistant: {t.answer[:200]}" for t in self.buffer[-3:])
            parts.append(f"Recent messages:\n{recent}")
        return "\n\n".join(parts)

    def is_empty(self) -> bool:
        return not self.summary and not self.buffer
