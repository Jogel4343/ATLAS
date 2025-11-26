"""
Helpers for querying parsed XBRL fact structures.

Exposes convenience functions to lookup facts by tag, resolve period
aliases to contextRefs, and pick the most relevant fact for a tag.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Sequence


def _coerce_tags(tag_or_tags: Any) -> List[str]:
    if tag_or_tags is None:
        return []
    if isinstance(tag_or_tags, str):
        return [tag_or_tags]
    if isinstance(tag_or_tags, Iterable):
        return [str(tag) for tag in tag_or_tags]
    return [str(tag_or_tags)]


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    clean = value.replace("Z", "").strip()
    if not clean:
        return None
    try:
        return datetime.fromisoformat(clean)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(clean[: len(fmt)], fmt)
        except ValueError:
            continue
    return None


def _context_end_date(context: Dict[str, Any]) -> datetime | None:
    if not context:
        return None
    period_type = (context.get("period_type") or "").lower()
    if period_type == "instant":
        return _parse_date(context.get("period_instant"))
    return _parse_date(context.get("period_end")) or _parse_date(
        context.get("period_instant")
    )


def _context_sort_date(context: Dict[str, Any]) -> datetime | None:
    date = _context_end_date(context)
    if date:
        return date
    return _parse_date(context.get("period_start"))


def _context_duration_days(context: Dict[str, Any]) -> int | None:
    start = _parse_date(context.get("period_start"))
    end = _parse_date(context.get("period_end"))
    if start and end:
        return (end - start).days
    return None


def _sort_context_ids(context_ids: Iterable[str], contexts: Dict[str, Any]) -> List[str]:
    return sorted(
        context_ids,
        key=lambda cid: (_context_sort_date(contexts.get(cid)) or datetime.min),
        reverse=True,
    )


def _preferred_period_type(period_alias: str | None) -> str | None:
    if not period_alias:
        return None
    alias = period_alias.upper()
    if alias.startswith("FY") or alias in {"MRQ", "Q1", "Q2", "Q3", "Q4"}:
        return "duration"
    return None


def _extract_facts_and_contexts(
    facts_or_result: Any,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    if isinstance(facts_or_result, dict):
        return (
            facts_or_result.get("all_facts") or facts_or_result.get("facts") or [],
            facts_or_result.get("contexts") or {},
        )
    return facts_or_result or [], {}


def get_facts_by_tag(facts_or_result: Any, tag_or_tags: Any) -> List[Dict[str, Any]]:
    """
    Return all facts whose tag matches any provided tag.
    """
    facts, _ = _extract_facts_and_contexts(facts_or_result)
    tags = {tag.lower() for tag in _coerce_tags(tag_or_tags)}
    if not tags:
        return []
    return [fact for fact in facts if fact.get("tag", "").lower() in tags]


def resolve_period(contexts: Dict[str, Any], period_alias: str | None) -> List[str]:
    """
    Resolve human-friendly period aliases to matching contextRefs.
    """
    if not contexts or not period_alias:
        return []

    alias = period_alias.strip()
    if not alias:
        return []

    alias_upper = alias.upper()

    if alias in contexts:
        return [alias]

    if alias_upper == "LATEST":
        dated = [
            (cid, _context_sort_date(ctx))
            for cid, ctx in contexts.items()
            if _context_sort_date(ctx)
        ]
        if not dated:
            return []
        max_date = max(date for _, date in dated if date)
        return [cid for cid, date in dated if date == max_date]

    if alias_upper == "MRQ":
        durations = []
        for cid, ctx in contexts.items():
            if (ctx.get("period_type") or "").lower() != "duration":
                continue
            date = _context_sort_date(ctx)
            if not date:
                continue
            length = _context_duration_days(ctx)
            durations.append((date, length, cid))
        durations.sort(reverse=True)
        quarter_like = [
            cid for _, length, cid in durations if length is not None and 70 <= length <= 120
        ]
        targets = quarter_like or [cid for _, _, cid in durations]
        return _sort_context_ids(targets, contexts)

    quarter_months = {"Q1": 3, "Q2": 6, "Q3": 9, "Q4": 12}
    if alias_upper in quarter_months:
        target_month = quarter_months[alias_upper]
        matches = []
        for cid, ctx in contexts.items():
            if (ctx.get("period_type") or "").lower() != "duration":
                continue
            end = _context_end_date(ctx)
            if end and end.month == target_month:
                matches.append(cid)
        return _sort_context_ids(matches, contexts)

    if alias_upper.startswith("FY"):
        try:
            year = int(alias_upper[2:])
        except ValueError:
            year = None
        matches = []
        if year:
            for cid, ctx in contexts.items():
                if (ctx.get("period_type") or "").lower() != "duration":
                    continue
                end = _context_end_date(ctx)
                if end and end.year == year:
                    matches.append(cid)
            return _sort_context_ids(matches, contexts)

    return []


def _fact_sort_key(
    fact: Dict[str, Any],
    contexts: Dict[str, Any],
    preferred_period_type: str | None,
) -> tuple[int, int, float]:
    has_numeric = fact.get("numeric_value") is not None
    context = contexts.get(fact.get("contextRef"))
    period_rank = 0
    if preferred_period_type:
        period_rank = (
            0 if (context and (context.get("period_type") or "").lower() == preferred_period_type) else 1
        )
    date = _context_sort_date(context or {})
    date_rank = -date.timestamp() if date else float("inf")
    return (0 if has_numeric else 1, period_rank, date_rank)


def get_fact(
    facts_or_result: Any,
    tag_or_tags: Any,
    period: str | None = None,
) -> Dict[str, Any] | None:
    """
    Return the best matching fact for a tag and optional period alias.
    """
    facts, contexts = _extract_facts_and_contexts(facts_or_result)
    candidates = get_facts_by_tag(facts, tag_or_tags)
    if not candidates:
        return None

    allowed_contexts: Sequence[str] = ()
    if period and contexts:
        allowed_contexts = resolve_period(contexts, period) or ()
        if allowed_contexts:
            candidates = [
                fact for fact in candidates if fact.get("contextRef") in allowed_contexts
            ]
            if not candidates:
                return None

    preferred_type = _preferred_period_type(period)
    candidates.sort(
        key=lambda fact: _fact_sort_key(fact, contexts, preferred_type),
    )
    return candidates[0] if candidates else None


def get_numeric(
    facts_or_result: Any,
    tag_or_tags: Any,
    period: str | None = None,
) -> float | None:
    """
    Convenience helper returning the numeric value of a fact if available.
    """
    fact = get_fact(facts_or_result, tag_or_tags, period=period)
    if not fact:
        return None
    return fact.get("numeric_value")


def get_latest(facts_or_result: Any, tag_or_tags: Any) -> Dict[str, Any] | None:
    """
    Return the newest fact for the requested tag(s).
    """
    return get_fact(facts_or_result, tag_or_tags, period="latest")

