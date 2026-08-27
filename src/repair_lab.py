from __future__ import annotations

import json
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


class PaginationError(RuntimeError):
    """The account source could not be traversed safely to completion."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        pages: list[dict[str, Any]],
    ) -> None:
        super().__init__(message)
        self.code = code
        self.pages = list(pages)


@dataclass(frozen=True)
class CollectedRow:
    """A row and its stable position in the accepted paginated result."""

    source_row_id: str
    value: dict[str, Any]


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


def _page_fingerprint(rows: list[dict[str, Any]]) -> str:
    """Return a deterministic representation used to recognize page replay."""
    return json.dumps(rows, sort_keys=True, separators=(",", ":"), default=str)


def collect_account_rows(
    tool: AccountPageLoader,
    *,
    page_size: int = 25,
    page_budget: int = 400,
) -> tuple[list[CollectedRow], list[dict[str, Any]]]:
    """Read a finite cursor traversal and suppress exact page replays.

    ``source_row_id`` is the zero-based result position calculated as
    ``logical_page_number * page_size + index_within_page``. Logical page
    numbers advance only for accepted pages, not replay responses.
    """
    if page_size <= 0:
        raise ValueError("page_size must be greater than zero")
    if page_budget <= 0:
        raise ValueError("page_budget must be greater than zero")

    collected: list[CollectedRow] = []
    evidence: list[dict[str, Any]] = []
    cursor: str | None = None
    logical_page_number = 0
    request_counts: dict[str | None, int] = {}
    responses_by_cursor: dict[str | None, tuple[str, str | None]] = {}
    last_response: tuple[str, str | None, str | None] | None = None

    for request_number in range(page_budget):
        request_counts[cursor] = request_counts.get(cursor, 0) + 1
        if request_counts[cursor] > 2:
            raise PaginationError(
                "cursor_cycle",
                f"cursor {cursor!r} was requested more than twice",
                pages=evidence,
            )

        input_cursor = cursor
        page = tool.load_page(cursor=input_cursor, page_size=page_size)
        fingerprint = _page_fingerprint(page.rows)
        previous_for_cursor = responses_by_cursor.get(input_cursor)

        if page.truncated and page.next_cursor is None:
            raise PaginationError(
                "missing_cursor",
                "source reported a truncated page without a next cursor",
                pages=evidence,
            )

        replayed = False
        if previous_for_cursor is not None:
            previous_fingerprint, _ = previous_for_cursor
            if fingerprint != previous_fingerprint:
                raise PaginationError(
                    "cursor_conflict",
                    f"cursor {input_cursor!r} returned different rows on retry",
                    pages=evidence,
                )
            if page.truncated and page.next_cursor == input_cursor:
                raise PaginationError(
                    "stalled_cursor",
                    f"cursor {input_cursor!r} did not advance on retry",
                    pages=evidence,
                )
            replayed = True
        elif (
            last_response is not None
            and last_response[2] is None
            and input_cursor == "0"
            and last_response[1] == input_cursor
            and last_response[0] == fingerprint
            and page.next_cursor != input_cursor
        ):
            # Some service retries expose the replayed page's starting cursor
            # only on the replay response (for example None -> "0" -> "25").
            replayed = True

        page_number = logical_page_number if not replayed else None
        start_position = (
            logical_page_number * page_size if not replayed else None
        )
        if not replayed:
            for page_index, row in enumerate(page.rows):
                source_row_id = str(logical_page_number * page_size + page_index)
                collected.append(CollectedRow(source_row_id, dict(row)))
            logical_page_number += 1

        evidence.append(
            {
                "request_number": request_number,
                "input_cursor": input_cursor,
                "next_cursor": page.next_cursor,
                "row_count": len(page.rows),
                "truncated": page.truncated,
                "replayed": replayed,
                "page_number": page_number,
                "start_position": start_position,
            }
        )
        responses_by_cursor[input_cursor] = (fingerprint, page.next_cursor)
        last_response = (fingerprint, page.next_cursor, input_cursor)

        if not page.truncated:
            return collected, evidence

        next_cursor = page.next_cursor
        if next_cursor in request_counts and next_cursor != input_cursor:
            raise PaginationError(
                "cursor_cycle",
                f"next cursor {next_cursor!r} returns to an earlier page",
                pages=evidence,
            )
        cursor = next_cursor

    raise PaginationError(
        "page_budget_exhausted",
        f"page budget of {page_budget} was exhausted",
        pages=evidence,
    )


def resolve_account_identity(
    rows: list[CollectedRow],
) -> tuple[list[CollectedRow], list[dict[str, Any]]]:
    """Keep the first valid row per company and explain every skipped row."""
    retained: list[CollectedRow] = []
    skipped: list[dict[str, Any]] = []
    companies: dict[str, CollectedRow] = {}

    for collected_row in rows:
        row = collected_row.value
        raw_company_id = row.get("company_id")
        if raw_company_id is None or not str(raw_company_id).strip():
            skipped.append(
                {
                    "source_row_id": collected_row.source_row_id,
                    "reason": "missing_company_id",
                }
            )
            continue

        company_id = str(raw_company_id)
        existing = companies.get(company_id)
        if existing is not None:
            differing_fields = sorted(
                key
                for key in set(existing.value) | set(row)
                if existing.value.get(key) != row.get(key)
            )
            skipped.append(
                {
                    "source_row_id": collected_row.source_row_id,
                    "reason": "duplicate_company_id",
                    "company_id": company_id,
                    "retained_source_row_id": existing.source_row_id,
                    "differing_fields": differing_fields,
                }
            )
            continue

        companies[company_id] = collected_row
        retained.append(collected_row)

    return retained, skipped


def _make_deliverables(
    accounts: list[CollectedRow],
    *,
    brand_kit_id: str,
    template_id: str,
) -> list[dict[str, str]]:
    deliverables: list[dict[str, str]] = []
    for collected_row in accounts:
        account = collected_row.value
        effective_brand_kit = str(
            account.get("saved_brand_kit_id", brand_kit_id)
        )
        effective_template = str(
            account.get("saved_template_id", template_id)
        )
        for asset_type in REQUIRED_ASSET_TYPES:
            deliverables.append(
                {
                    "source_row_id": collected_row.source_row_id,
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
    page_budget: int = 400,
) -> dict[str, Any]:
    collected_rows, pagination = collect_account_rows(
        tool,
        page_size=page_size,
        page_budget=page_budget,
    )
    rows, skipped_rows = resolve_account_identity(collected_rows)

    return {
        "source_row_ids": [row.source_row_id for row in rows],
        "deliverables": _make_deliverables(
            rows,
            brand_kit_id=brand_kit_id,
            template_id=template_id,
        ),
        "skipped_rows": skipped_rows,
        "pagination": pagination,
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
