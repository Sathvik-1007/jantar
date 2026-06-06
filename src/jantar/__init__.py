"""Jantar — Agentic Layer for Indian Government Services.

This package init runs BEFORE any submodule import. It is the only correct
place to configure HuggingFace Hub environment variables, because
``huggingface_hub`` reads ``HF_HUB_OFFLINE`` exactly once — at *its* import
time — into a module constant. Setting that variable later (e.g. inside a
model loader) has no effect, which is why the models would otherwise issue
network calls on every startup even when fully cached.

Behaviour:
- Telemetry and progress bars are always disabled (quiet, deterministic logs).
- If BOTH required models are already present in the local HF cache, fully
  offline mode is enabled so no network calls are made. If a model is missing,
  online mode is left intact so the first-run download still works.
"""

from __future__ import annotations

import os
from pathlib import Path

__all__ = ["__version__"]

__version__ = "1.0.0"

# HuggingFace repos this application loads. Used for the cache-presence check.
_REQUIRED_HF_MODELS: tuple[str, ...] = (
    "BAAI/bge-m3",
    "BAAI/bge-reranker-v2-m3",
)


def _hf_cache_dir() -> Path:
    """Resolve the HuggingFace hub cache directory without importing HF libs.

    Honors ``HF_HUB_CACHE`` then ``HF_HOME`` then the documented default of
    ``~/.cache/huggingface/hub`` (HuggingFace Hub caching spec).
    """
    if os.environ.get("HF_HUB_CACHE"):
        return Path(os.environ["HF_HUB_CACHE"])
    if os.environ.get("HF_HOME"):
        return Path(os.environ["HF_HOME"]) / "hub"
    return Path.home() / ".cache" / "huggingface" / "hub"


def _model_is_cached(repo_id: str) -> bool:
    """Return True if ``repo_id`` has at least one complete snapshot on disk.

    The HF cache layout is ``<cache>/models--<org>--<name>/snapshots/<rev>/``.
    We treat the presence of ``config.json`` in any snapshot as "cached".
    Pure filesystem check — intentionally avoids importing ``huggingface_hub``
    so this can run before the offline env var is set.
    """
    folder = "models--" + repo_id.replace("/", "--")
    snapshots = _hf_cache_dir() / folder / "snapshots"
    if not snapshots.is_dir():
        return False
    for revision in snapshots.iterdir():
        if (revision / "config.json").exists():
            return True
    return False


def _configure_huggingface_env() -> None:
    """Set HF env vars at import time, before any HF library is imported."""
    # Always quiet: no telemetry pings, no tqdm progress bars in logs.
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TRANSFORMERS_NO_ADVISORY_WARNINGS", "1")
    # tokenizers fork-safety: silence the parallelism warning deterministically.
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    # Only force offline when every required model is present locally, so the
    # very first run (cold cache) can still download. setdefault preserves any
    # explicit override the operator already exported.
    if all(_model_is_cached(repo) for repo in _REQUIRED_HF_MODELS):
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


_configure_huggingface_env()
