import sys

from jantar.cli.main import app

# Allow `python -m jantar "question"` without the `ask` subcommand
if len(sys.argv) > 1 and sys.argv[1] not in ("ask", "serve", "--help", "--install-completion", "--show-completion"):
    sys.argv.insert(1, "ask")

app()
