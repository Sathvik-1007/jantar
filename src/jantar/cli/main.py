import asyncio
import json
import sys

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from jantar.agent.executor import run_agent
from jantar.agent.memory import ConversationMemory
from jantar.models import AgentRequest

app = typer.Typer(name="jantar", help="Jantar — Agentic Layer for Indian Government Services")
console = Console()


def _warmup():
    """Pre-load ML models so first query is fast."""
    from jantar.rag.embeddings import warmup_embeddings
    from jantar.rag.reranker import warmup_reranker

    console.print("[dim]Loading models...[/dim]")
    warmup_embeddings()
    warmup_reranker()
    console.print("[dim]Models ready.[/dim]")


@app.command()
def ask(
    query: str = typer.Argument(None, help="Your question in any language (omit for interactive mode)"),
    language: str = typer.Option("auto", "--lang", "-l", help="Language code (auto, hi, en, ta, bn, etc.)"),
):
    """Ask Jantar a question about government services. Omit query for interactive mode."""
    _warmup()
    if query:
        asyncio.run(_ask(query, language, None))
    else:
        asyncio.run(_interactive(language))


async def _interactive(default_lang: str):
    """Interactive REPL mode with conversation memory."""
    memory = ConversationMemory()
    console.print(Panel(
        "[bold]Jantar[/bold] — Ask anything about Indian government services\n"
        "Type in any Indian language. Type 'quit' or Ctrl+C to exit.\n"
        "[dim]Conversation memory active — follow-up questions work.[/dim]",
        border_style="blue",
    ))
    while True:
        try:
            query = console.input("[bold blue]> [/bold blue]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye.[/dim]")
            break
        query = query.strip()
        if not query or query.lower() in ("quit", "exit", "q"):
            break
        response = await _ask(query, default_lang, memory)
        if response:
            memory.add(query, response.answer, default_lang)
            await memory.maybe_summarize()
        console.print()


async def _ask(query: str, language: str, memory: ConversationMemory | None = None):
    console.print(Panel(f"[bold]{query}[/bold]", title="Query", border_style="blue"))

    try:
        with console.status("[bold green]Processing..."):
            request = AgentRequest(text=query, language=language)
            memory_ctx = memory.get_context() if memory else ""
            response = await run_agent(request, memory_context=memory_ctx)
    except Exception as e:
        error_type = type(e).__name__
        console.print(Panel(f"[red]{error_type}: {e}[/red]", title="Error", border_style="red"))
        return None

    # Answer
    console.print(Panel(response.answer, title="Answer", border_style="green"))

    # Citations
    if response.citations:
        table = Table(title="Citations")
        table.add_column("Source", style="cyan")
        table.add_column("Section")
        table.add_column("Date")
        for c in response.citations:
            table.add_row(c.get("title", ""), c.get("section", ""), c.get("effective_date", ""))
        console.print(table)

    # Tools used
    if response.tools_used:
        console.print(f"[dim]Tools used: {', '.join(response.tools_used)}[/dim]")

    # Audit trail (compact)
    if response.audit_trail:
        steps = " → ".join(s.get("step", "") for s in response.audit_trail)
        console.print(f"[dim]Pipeline: {steps}[/dim]")

    return response


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Host"),
    port: int = typer.Option(8000, help="Port"),
):
    """Start the FastAPI server."""
    import uvicorn
    uvicorn.run("jantar.api.app:create_app", host=host, port=port, factory=True)


if __name__ == "__main__":
    app()
