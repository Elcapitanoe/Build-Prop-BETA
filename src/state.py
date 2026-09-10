"""State management for Android OTA Tracker with atomic file operations."""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


def get_current_utc_iso() -> str:
    """Return the current UTC time in ISO 8601 format."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ActiveTarget(BaseModel):
    """Active target Android version and download URL."""

    model_config = ConfigDict(populate_by_name=True)

    major: int
    qpr: int | None = None
    url: str

    @property
    def target_version(self) -> str:
        """Formatted human-readable target version."""
        if self.qpr is not None:
            return f"Android {self.major} QPR{self.qpr}"
        return f"Android {self.major} Beta"


class Fingerprint(BaseModel):
    """Fingerprint representing a specific Android OTA release build."""

    model_config = ConfigDict(populate_by_name=True)

    build_id: str
    security_patch: str
    checksum_sha256: str


class TrackerState(BaseModel):
    """Overall tracker state model matching data/state.json schema."""

    model_config = ConfigDict(populate_by_name=True)

    schema_version: str = Field(default="1.0.0", alias="$schema_version")
    last_synced_at: str
    active_target: ActiveTarget
    fingerprint: Fingerprint


def load_state(path: Path | str) -> TrackerState:
    """Load and validate tracker state from JSON file."""
    state_file = Path(path)
    if not state_file.is_file():
        raise FileNotFoundError(f"State file not found at: {state_file}")

    with open(state_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    return TrackerState.model_validate(data)


def save_state_atomic(state: TrackerState, path: Path | str) -> None:
    """Write tracker state atomically using a temp file in the same directory."""
    target_path = Path(path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    serialized = state.model_dump_json(by_alias=True, indent=2) + "\n"

    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=target_path.parent,
        prefix="state_",
        suffix=".tmp",
        delete=False,
    ) as tmp:
        tmp.write(serialized)
        tmp.flush()
        os.fsync(tmp.fileno())
        temp_file_name = tmp.name

    os.replace(temp_file_name, target_path)
