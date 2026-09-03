from __future__ import annotations

from pathlib import Path
import sysconfig


PACKAGE_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PACKAGE_ROOT.parents[1]
INSTALLED_SHARE_ROOT = (
    Path(sysconfig.get_path("data"))
    / "share"
    / "responder-readiness-forecaster"
)


def data_root() -> Path:
    """Locate data in a source checkout or a normal wheel installation."""

    source_data = SOURCE_ROOT / "data"
    if source_data.is_dir():
        return source_data
    installed_data = INSTALLED_SHARE_ROOT / "data"
    if installed_data.is_dir():
        return installed_data
    raise FileNotFoundError(
        "forecaster_data_not_found: reinstall the package or run it from the repository root"
    )


def default_memory_path(filename: str = "audit_memory.sqlite3") -> Path:
    """Keep source runs in the ignored project folder and installed runs in user storage."""

    source_data = SOURCE_ROOT / "data"
    if source_data.is_dir():
        return SOURCE_ROOT / ".local" / filename
    return Path.home() / ".responder-readiness-forecaster" / filename
