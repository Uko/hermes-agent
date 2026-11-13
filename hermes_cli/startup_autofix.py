"""Operator control for implicit startup maintenance (stdlib-only)."""
import os


def startup_autofix_disabled() -> bool:
    """Only explicit truthy values disable autofix; the upstream default is on."""
    # health: allow HX002 -- Must apply before profile config or dependencies load.
    return os.environ.get("HERMES_DISABLE_AUTOFIX", "").strip().lower() in {"1", "true", "yes", "on"}
