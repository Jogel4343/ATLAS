"""
Semantic resolver to pick the best fact among multiple XBRL candidates.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional


PREFERRED_DURATION = {"revenue", "operating_income", "gross_profit", "net_income"}

STATEMENT_RANK = {
    "incomestatement": 0,
    "cashflowstatement": 1,
    "balancesheet": 2,
}

ROLE_RANK = {
    "statementofincome": 0,
    "statementofcashflows": 1,
    "statementofchangesinfinancialposition": 1,
    "statementofchangesinownersequity": 2,
    "balancesheet": 2,
    "statementsoffinancialposition": 2,
    "footnotes": 3,
}


def _parse_date(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    txt = value.replace("Z", "").strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(txt[: len(fmt)], fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(txt)
    except ValueError:
        return None


def _context_end_date(context: Dict[str, Any]) -> Optional[datetime]:
    period_type = (context.get("period_type") or "").lower()
    if period_type == "instant":
        return _parse_date(context.get("period_instant"))
    return _parse_date(context.get("period_end")) or _parse_date(context.get("period_instant"))


def _duration_days(context: Dict[str, Any]) -> Optional[int]:
    start = _parse_date(context.get("period_start"))
    end = _parse_date(context.get("period_end"))
    if start and end:
        return (end - start).days
    return None


def _is_consolidated(context: Dict[str, Any]) -> bool:
    segment = context.get("segment") or context.get("segments")
    dimensions = context.get("entity_dimensions") or context.get("dimensions")
    return not segment and not dimensions


def _statement_rank(fact: Dict[str, Any]) -> int:
    st = (fact.get("statement_type") or "").replace(" ", "").lower()
    return STATEMENT_RANK.get(st, 3)


def _role_rank(fact: Dict[str, Any]) -> int:
    role = (fact.get("role") or "").replace(" ", "").lower()
    return ROLE_RANK.get(role, 4)


def _period_rank(context: Dict[str, Any], preferred: Optional[str]) -> int:
    period_type = (context.get("period_type") or "").lower()
    if preferred in PREFERRED_DURATION:
        if period_type == "duration":
            return 0
        if period_type == "instant":
            return 1
        return 2
    return 0


def _duration_rank(context: Dict[str, Any]) -> float:
    days = _duration_days(context)
    if days is None:
        return float("inf")
    return -days


def _date_rank(context: Dict[str, Any]) -> float:
    end = _context_end_date(context)
    if not end:
        return float("inf")
    return -end.timestamp()


def _magnitude_rank(fact: Dict[str, Any]) -> float:
    num = fact.get("numeric_value")
    if num is None:
        return float("inf")
    return -abs(num)


def _sort_key(fact: Dict[str, Any], contexts: Dict[str, Any], preferred: Optional[str]):
    ctx = contexts.get(fact.get("contextRef") or "", {})
    consolidated_rank = 0 if _is_consolidated(ctx) else 1
    period_rank = _period_rank(ctx, preferred)
    duration_rank = _duration_rank(ctx)
    statement_rank = _statement_rank(fact)
    role_rank = _role_rank(fact)
    date_rank = _date_rank(ctx)
    magnitude_rank = _magnitude_rank(fact)
    return (
        consolidated_rank,
        period_rank,
        duration_rank,
        statement_rank,
        role_rank,
        date_rank,
        magnitude_rank,
    )


def resolve_semantic(
    facts: List[Dict[str, Any]],
    contexts: Dict[str, Any],
    tag: str,
    preferred: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Pick the best fact for a given tag using semantic ranking rules.
    """
    tag_lower = tag.lower()
    candidates = [f for f in facts if (f.get("tag") or "").lower() == tag_lower]
    if not candidates:
        return None

    candidates.sort(key=lambda f: _sort_key(f, contexts, preferred))
    return candidates[0] if candidates else None


def pick_best(facts: List[Dict[str, Any]], contexts: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Simple helper: pick the single best fact among given candidates.
    """
    if not facts:
        return None
    facts.sort(key=lambda f: _sort_key(f, contexts, None))
    return facts[0]


def resolve_revenue(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return resolve_semantic(
        data.get("all_facts", []),
        data.get("contexts", {}),
        "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
        preferred="revenue",
    )


def resolve_operating_income(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return resolve_semantic(
        data.get("all_facts", []),
        data.get("contexts", {}),
        "us-gaap:OperatingIncomeLoss",
        preferred="operating_income",
    )


def resolve_net_income(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return resolve_semantic(
        data.get("all_facts", []),
        data.get("contexts", {}),
        "us-gaap:NetIncomeLoss",
        preferred="net_income",
    )


def resolve_gross_profit(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return resolve_semantic(
        data.get("all_facts", []),
        data.get("contexts", {}),
        "us-gaap:GrossProfit",
        preferred="gross_profit",
    )


def resolve_eps_basic(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return resolve_semantic(
        data.get("all_facts", []),
        data.get("contexts", {}),
        "us-gaap:EarningsPerShareBasic",
        preferred="eps_basic",
    )


def resolve_eps_diluted(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return resolve_semantic(
        data.get("all_facts", []),
        data.get("contexts", {}),
        "us-gaap:EarningsPerShareDiluted",
        preferred="eps_diluted",
    )


def resolve_assets(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return resolve_semantic(
        data.get("all_facts", []),
        data.get("contexts", {}),
        "us-gaap:Assets",
        preferred="assets",
    )


def resolve_liabilities(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return resolve_semantic(
        data.get("all_facts", []),
        data.get("contexts", {}),
        "us-gaap:Liabilities",
        preferred="liabilities",
    )


def resolve_equity(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return resolve_semantic(
        data.get("all_facts", []),
        data.get("contexts", {}),
        "us-gaap:StockholdersEquity",
        preferred="equity",
    )
