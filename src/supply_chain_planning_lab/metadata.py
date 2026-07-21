"""Safe setup and handoff information."""

from pathlib import Path

from . import __version__


def project_info(*, api_key_configured: bool, output_dir: Path) -> str:
    """Return setup information without exposing a key or calling FRED."""

    key_status = "configured" if api_key_configured else "not configured"
    return "\n".join(
        [
            f"Supply Chain Planning Lab {__version__}",
            "API: FRED series PERMIT",
            f"FRED_API_KEY: {key_status}",
            f"Raw output: {output_dir / 'raw'}",
            f"Processed output: {output_dir / 'processed'}",
            "Checks: uv run pytest",
        ]
    )
