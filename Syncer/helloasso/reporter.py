"""
Progress reporting for the syncer pipeline.

The pipeline calls a ``Reporter`` instead of printing directly, so the same
core logic can drive the CLI (default ``Reporter``, which prints) and the
Qt GUI (a subclass that emits signals). The default implementation
reproduces the console output of the original script.
"""

from pathlib import Path
from typing import List

class Reporter:
    """Default reporter: prints to the console (used by the CLI)."""

    def log(self, message: str) -> None:
        """Log a free-form message."""
        print(message)

    def form_started(self, slug: str, index: int, total: int) -> None:
        """A form's processing is starting."""
        print(f"\n{'='*60}")
        print(f"Traitement de la billetterie: {slug}")
        print(f"{'='*60}")

    def payment_progress(self, slug: str, completed: int, total: int) -> None:
        """One more order detail has been fetched for ``slug``."""
        # Overwrite the same line while in progress, finalize with a newline.
        end = "\n" if completed >= total else "\r"
        print(f"\t[{completed}/{total}] Commandes traitées ({slug})...", end=end, flush=True)

    def form_finished(self, slug: str, path: Path) -> None:
        """A form has been fully processed (``path`` is empty when no data)."""

    def run_finished(self, files: List[str]) -> None:
        """The whole run is done; ``files`` are the generated CSV paths."""

    def should_cancel(self) -> bool:
        """Cooperative cancellation hook (checked between forms)."""
        return False
