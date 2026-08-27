from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


REQUIRED_ASSET_TYPES = (
    "landing_page",
    "linkedin_ad_1",
    "linkedin_ad_2",
    "linkedin_ad_3",
)


@dataclass(frozen=True)
class ToolPage:
    rows: list[dict[str, Any]]
    next_cursor: str | None
    truncated: bool


class AccountPageLoader(Protocol):
    def load_page(
        self,
        *,
        cursor: str | None = None,
        page_size: int = 25,
    ) -> ToolPage: ...


class TargetAccountTool:
    """Deterministic stand-in for the paginated uploaded-account service."""

    def __init__(self, accounts: list[dict[str, Any]]) -> None:
        self._accounts = [dict(account) for account in accounts]

    def load_page(
        self,
        *,
        cursor: str | None = None,
        page_size: int = 25,
    ) -> ToolPage:
        start = int(cursor or "0")
        rows = self._accounts[start : start + page_size]
        next_index = start + len(rows)
        next_cursor = (
            str(next_index) if next_index < len(self._accounts) else None
        )
        return ToolPage(
            rows=rows,
            next_cursor=next_cursor,
            truncated=next_cursor is not None,
        )


def _collapse_page(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse rows that name the same company.

    The uploaded list can name a company more than once, so the page is
    reduced to one row per company before anything downstream sees it.
    """
    kept: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        company_id = str(row["company_id"])
        if company_id in seen:
            continue
        seen.add(company_id)
        kept.append(row)
    return kept


def _make_deliverables(
    accounts: list[dict[str, Any]],
    *,
    brand_kit_id: str,
    template_id: str,
) -> list[dict[str, str]]:
    deliverables: list[dict[str, str]] = []
    for account in accounts:
        effective_brand_kit = str(
            account.get("saved_brand_kit_id", brand_kit_id)
        )
        effective_template = str(
            account.get("saved_template_id", template_id)
        )
        for asset_type in REQUIRED_ASSET_TYPES:
            deliverables.append(
                {
                    "source_row_id": str(account["id"]),
                    "company_id": str(account["company_id"]),
                    "company_name": str(account["company_name"]),
                    "asset_type": asset_type,
                    "brand_kit_id": effective_brand_kit,
                    "template_id": effective_template,
                }
            )
    return deliverables


def build_campaign_plan(
    tool: AccountPageLoader,
    *,
    brand_kit_id: str,
    template_id: str,
    page_size: int = 25,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    cursor: str | None = None
    while True:
        page = tool.load_page(cursor=cursor, page_size=page_size)
        rows.extend(_collapse_page(page.rows))
        if not page.truncated:
            break
        cursor = page.next_cursor

    return {
        "source_row_ids": [str(row["id"]) for row in rows],
        "deliverables": _make_deliverables(
            rows,
            brand_kit_id=brand_kit_id,
            template_id=template_id,
        ),
        "complete": True,
    }


def evaluate_campaign_coverage(
    plan: dict[str, Any],
    accounts: list[dict[str, Any]],
) -> tuple[bool, str]:
    """The currently deployed check. The customer disputes its result."""
    observed_rows = {str(value) for value in plan.get("source_row_ids", [])}
    deliverables = plan.get("deliverables", [])

    for row_id in sorted(observed_rows):
        observed_types = {
            str(item.get("asset_type"))
            for item in deliverables
            if str(item.get("source_row_id")) == row_id
        }
        if observed_types != set(REQUIRED_ASSET_TYPES):
            return False, f"source row {row_id} has the wrong asset set"

    if plan.get("complete") is not True:
        return False, "campaign did not declare completion"
    return True, f"all {len(observed_rows)} campaigned rows have the requested asset types"
