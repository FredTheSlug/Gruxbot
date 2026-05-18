"""Helpers to interpret Omeda.city JSON shapes defensively."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.I,
)


def looks_like_player_id(s: str) -> bool:
    return bool(UUID_RE.match(s.strip()))


def first_list_of_dicts(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for key in ("players", "results", "data", "matches", "heroes", "items", "nodes"):
            v = payload.get(key)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
        inner = payload.get("players")
        if isinstance(inner, dict):
            for sub in ("data", "nodes", "edges", "results"):
                v = inner.get(sub)
                if isinstance(v, list):
                    return [x for x in v if isinstance(x, dict)]
        if "player" in payload and isinstance(payload["player"], dict):
            return [payload["player"]]
    return []


def extract_player_rows_from_search(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    rows = first_list_of_dicts(payload)
    if rows:
        return rows
    if isinstance(payload, dict):
        inner = payload.get("players")
        if isinstance(inner, dict):
            for sub in ("data", "nodes"):
                v = inner.get(sub)
                if isinstance(v, list):
                    return [x for x in v if isinstance(x, dict)]
    return []


def extract_player_id_from_search(payload: Any) -> str | None:
    for row in extract_player_rows_from_search(payload):
        pid = row.get("id") or row.get("player_id")
        if pid:
            return str(pid)
    return None


def normalize_match_id(match_id: str | None) -> str | None:
    """Canonical form for comparing match UUIDs (Omeda returns lowercase; users may paste mixed case)."""
    if match_id is None:
        return None
    s = str(match_id).strip()
    if not s:
        return None
    return s.casefold()


def match_id_from_row(row: dict[str, Any]) -> str | None:
    """Match id from pred.gg or omeda.city row shapes."""
    for key in ("id", "match_id", "uuid"):
        v = row.get(key)
        if v is not None and str(v).strip():
            return str(v).strip()
    return None


def row_matches_id(row: dict[str, Any], match_id: str | None) -> bool:
    target = normalize_match_id(match_id)
    if target is None:
        return False
    for key in ("id", "match_id", "uuid"):
        v = row.get(key)
        if v is not None and normalize_match_id(str(v)) == target:
            return True
    return False


def extract_match_summaries(payload: Any) -> list[dict[str, Any]]:
    rows = first_list_of_dicts(payload)
    out: list[dict[str, Any]] = []
    for row in rows:
        if match_id_from_row(row):
            out.append(row)
    return out


def get_match_ids_in_order(payload: Any) -> list[str]:
    summaries = extract_match_summaries(payload)
    ids: list[str] = []
    for s in summaries:
        mid = match_id_from_row(s)
        if mid:
            ids.append(mid)
    return ids


def _parse_time_value(v: Any) -> float | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        ts = float(v)
        if ts > 1e12:
            ts /= 1000.0
        return ts
    if isinstance(v, str) and v.strip():
        try:
            s = v.strip().replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except (ValueError, OSError, TypeError):
            return None
    return None


def _match_time_sort_key(m: dict[str, Any]) -> float:
    """Prefer end time, then start (Omeda snake_case or pred.gg camelCase)."""
    for key in (
        "end_time",
        "endTime",
        "start_time",
        "startTime",
        "created_at",
        "createdAt",
    ):
        ts = _parse_time_value(m.get(key))
        if ts is not None:
            return ts
    return 0.0


def get_match_rows_newest_first(payload: Any) -> list[dict[str, Any]]:
    """Match summaries sorted by time, newest first (stable for /follow detection)."""
    if isinstance(payload, dict) and isinstance(payload.get("matches"), list):
        rows = [x for x in payload["matches"] if isinstance(x, dict)]
    else:
        rows = extract_match_summaries(payload)
    rows = [r for r in rows if match_id_from_row(r)]
    return sorted(rows, key=_match_time_sort_key, reverse=True)


def get_match_ids_newest_first(payload: Any) -> list[str]:
    out: list[str] = []
    for s in get_match_rows_newest_first(payload):
        mid = match_id_from_row(s)
        if mid:
            out.append(mid)
    return out


@dataclass(frozen=True)
class NewMatchScan:
    """Result of comparing API match history to a stored last_seen id."""

    status: Literal["no_matches", "init", "unchanged", "new", "rebaseline"]
    newest_match_id: str | None = None
    new_match_ids: tuple[str, ...] = ()
    last_seen_match_id: str | None = None


def find_new_matches_since(payload: Any, last_seen_match_id: str | None) -> NewMatchScan:
    """
    Determine which matches are newer than last_seen.

    Rows are sorted newest-first. When last_seen is missing from the fetched page,
    re-baseline without treating unknown history as new (avoids duplicate pings).
    """
    rows = get_match_rows_newest_first(payload)
    if not rows:
        return NewMatchScan(status="no_matches", last_seen_match_id=last_seen_match_id)

    ids = [mid for r in rows if (mid := match_id_from_row(r))]
    newest = ids[0] if ids else None

    if normalize_match_id(last_seen_match_id) is None:
        return NewMatchScan(status="init", newest_match_id=newest, last_seen_match_id=None)

    if normalize_match_id(newest) == normalize_match_id(last_seen_match_id):
        return NewMatchScan(
            status="unchanged",
            newest_match_id=newest,
            last_seen_match_id=last_seen_match_id,
        )

    last_idx: int | None = None
    last_ts: float | None = None
    for i, row in enumerate(rows):
        if row_matches_id(row, last_seen_match_id):
            last_idx = i
            last_ts = _match_time_sort_key(row)
            break

    if last_idx is None:
        return NewMatchScan(
            status="rebaseline",
            newest_match_id=newest,
            last_seen_match_id=last_seen_match_id,
        )

    new_rows: list[dict[str, Any]] = []
    if last_ts and last_ts > 0:
        for row in rows:
            if row_matches_id(row, last_seen_match_id):
                continue
            ts = _match_time_sort_key(row)
            if ts > last_ts:
                new_rows.append(row)
    else:
        new_rows = rows[:last_idx]

    new_ids = [mid for r in new_rows if (mid := match_id_from_row(r))]
    if not new_ids:
        return NewMatchScan(
            status="unchanged",
            newest_match_id=newest,
            last_seen_match_id=last_seen_match_id,
        )

    return NewMatchScan(
        status="new",
        newest_match_id=newest,
        new_match_ids=tuple(reversed(new_ids)),
        last_seen_match_id=last_seen_match_id,
    )


def pick_str(d: dict[str, Any], *keys: str) -> str | None:
    for k in keys:
        v = d.get(k)
        if v is not None and isinstance(v, str):
            return v
        if v is not None and not isinstance(v, (dict, list)):
            return str(v)
    return None


def find_in_list_by_name(items: list[dict[str, Any]], query: str) -> dict[str, Any] | None:
    q = query.strip().casefold()
    if not q:
        return None

    def name_of(x: dict[str, Any]) -> str | None:
        return pick_str(x, "name", "title", "display_name", "slug")

    for x in items:
        n = name_of(x)
        if n and n.casefold() == q:
            return x
    partial = [x for x in items if (name_of(x) or "").casefold().find(q) >= 0]
    if len(partial) == 1:
        return partial[0]
    if partial:
        partial.sort(key=lambda x: len(name_of(x) or ""))
        return partial[0]
    return None
