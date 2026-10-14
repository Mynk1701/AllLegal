"""
Loads track configs from `app/drafting/tracks/<key>/track.yaml`.

A track is a configuration, not code (LLD S.1): this module is the only
place that reads `track.yaml` files, and it stays generic — no track-specific
knowledge lives here. The one exception is `ENABLED_TRACKS`, the explicit
allow-list for what the API will actually serve (LLD S.9: "only cheque_bounce
enabled" for Phase 1), kept separate from "config files that happen to
exist" so a half-finished track folder can sit in the repo without becoming
reachable.
"""
from __future__ import annotations

import functools
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

TRACKS_DIR = Path(__file__).parent / "tracks"

# Phase 1 scope (LLD S.13 build order). Add a key here only once that
# track's config, fact model and templates are reviewed and merged.
ENABLED_TRACKS = {"cheque_bounce"}


@dataclass(frozen=True)
class StageConfig:
    key: str
    label: str
    sections: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class DocumentConfig:
    key: str
    template: str
    title: str
    requires: List[str] = field(default_factory=list)
    stage: Optional[str] = None
    feature_flag: Optional[str] = None
    conditional_note: Optional[str] = None


@dataclass(frozen=True)
class ResearchSlotConfig:
    key: str
    label: str


@dataclass(frozen=True)
class TrackConfig:
    key: str
    title: str
    facts_model: str
    stages: List[StageConfig]
    deadlines: List[str]
    documents: List[DocumentConfig]
    research_slots: List[ResearchSlotConfig]
    raw: Dict[str, Any]

    def document(self, document_key: str) -> Optional[DocumentConfig]:
        return next((d for d in self.documents if d.key == document_key), None)


class TrackNotFoundError(KeyError):
    pass


class TrackNotEnabledError(KeyError):
    pass


def _track_yaml_path(track_key: str) -> Path:
    return TRACKS_DIR / track_key / "track.yaml"


def _load_yaml(track_key: str) -> Dict[str, Any]:
    path = _track_yaml_path(track_key)
    if not path.exists():
        raise TrackNotFoundError(track_key)
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@functools.lru_cache(maxsize=None)
def get_track(track_key: str) -> TrackConfig:
    """Load and parse one track's config. Raises TrackNotFoundError if no
    track.yaml exists for that key — callers that must respect the
    enabled-tracks allow-list should check `is_enabled()` first."""
    raw = _load_yaml(track_key)
    stages = [StageConfig(key=s["key"], label=s["label"], sections=s.get("sections", [])) for s in raw.get("stages", [])]
    documents = [
        DocumentConfig(
            key=d["key"],
            template=d["template"],
            title=d.get("title", d["key"]),
            requires=d.get("requires", []),
            stage=d.get("stage"),
            feature_flag=d.get("feature_flag"),
            conditional_note=d.get("conditional_note"),
        )
        for d in raw.get("documents", [])
    ]
    research_slots = [ResearchSlotConfig(key=r["key"], label=r["label"]) for r in raw.get("research_slots", [])]
    return TrackConfig(
        key=raw["key"],
        title=raw["title"],
        facts_model=raw["facts_model"],
        stages=stages,
        deadlines=raw.get("deadlines", []),
        documents=documents,
        research_slots=research_slots,
        raw=raw,
    )


def list_available_track_keys() -> List[str]:
    """Every track with a track.yaml on disk, enabled or not (useful for
    internal tooling/tests — the API uses list_enabled_tracks())."""
    if not TRACKS_DIR.exists():
        return []
    return sorted(p.parent.name for p in TRACKS_DIR.glob("*/track.yaml"))


def is_enabled(track_key: str) -> bool:
    return track_key in ENABLED_TRACKS


def list_enabled_tracks() -> List[TrackConfig]:
    return [get_track(k) for k in sorted(ENABLED_TRACKS) if k in list_available_track_keys()]


def get_enabled_track(track_key: str) -> TrackConfig:
    if not is_enabled(track_key):
        raise TrackNotEnabledError(track_key)
    return get_track(track_key)
