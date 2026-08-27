from __future__ import annotations

import json
from collections import Counter
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
    snapshot_id: str | None = None
    total_row_count: int | None = None


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


class CampaignPlanError(RuntimeError):
    """A collected account set could not produce a publishable campaign."""


@dataclass(frozen=True)
class CollectedRow:
    """A row and its stable position in the accepted paginated result."""

    source_row_id: str
    value: dict[str, Any]


class TargetAccountTool:
    """Deterministic stand-in for the paginated uploaded-account service."""

    def __init__(self, accounts: list[dict[str, Any]]) -> None:
        self._accounts = [dict(account) for account in accounts]
        self._snapshot_id = "target-account-tool-snapshot"

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
            snapshot_id=self._snapshot_id,
            total_row_count=len(self._accounts),
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
    snapshot_id: str | None = None
    total_row_count: int | None = None

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

        if not page.snapshot_id:
            raise PaginationError(
                "missing_snapshot",
                "source did not provide a snapshot identifier",
                pages=evidence,
            )
        if (
            not isinstance(page.total_row_count, int)
            or isinstance(page.total_row_count, bool)
            or page.total_row_count < 0
        ):
            raise PaginationError(
                "invalid_total_row_count",
                "source did not provide a valid non-negative total row count",
                pages=evidence,
            )
        if snapshot_id is None:
            snapshot_id = page.snapshot_id
            total_row_count = page.total_row_count
        elif page.snapshot_id != snapshot_id:
            raise PaginationError(
                "snapshot_changed",
                f"source snapshot changed from {snapshot_id!r} "
                f"to {page.snapshot_id!r}",
                pages=evidence,
            )
        elif page.total_row_count != total_row_count:
            raise PaginationError(
                "total_row_count_changed",
                f"source row total changed from {total_row_count} "
                f"to {page.total_row_count}",
                pages=evidence,
            )

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

        next_cursor = page.next_cursor
        if (
            page.truncated
            and next_cursor in request_counts
            and next_cursor != input_cursor
        ):
            raise PaginationError(
                "cursor_cycle",
                f"next cursor {next_cursor!r} returns to an earlier page",
                pages=evidence,
            )

        page_number = logical_page_number if not replayed else None
        start_position = (
            logical_page_number * page_size if not replayed else None
        )
        if not replayed:
            for page_index, row in enumerate(page.rows):
                source_row_id = str(logical_page_number * page_size + page_index)
                collected.append(CollectedRow(source_row_id, dict(row)))
            logical_page_number += 1

        if total_row_count is not None and len(collected) > total_row_count:
            raise PaginationError(
                "row_count_exceeded",
                f"collected {len(collected)} rows but source declared "
                f"{total_row_count}",
                pages=evidence,
            )

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
                "snapshot_id": page.snapshot_id,
                "total_row_count": page.total_row_count,
                "accepted_row_count": len(collected),
            }
        )
        responses_by_cursor[input_cursor] = (fingerprint, page.next_cursor)
        last_response = (fingerprint, page.next_cursor, input_cursor)

        if not page.truncated:
            if len(collected) != total_row_count:
                raise PaginationError(
                    "incomplete_source",
                    f"source terminated after {len(collected)} of "
                    f"{total_row_count} declared rows",
                    pages=evidence,
                )
            return collected, evidence

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
        for asset_type in REQUIRED_ASSET_TYPES:
            deliverables.append(
                {
                    "source_row_id": collected_row.source_row_id,
                    "company_id": str(account["company_id"]),
                    "company_name": str(account["company_name"]),
                    "asset_type": asset_type,
                    "brand_kit_id": brand_kit_id,
                    "template_id": template_id,
                }
            )
    return deliverables


def _validate_generated_campaign(
    rows: list[CollectedRow],
    deliverables: list[dict[str, str]],
    *,
    brand_kit_id: str,
    template_id: str,
) -> dict[str, Any]:
    """Prove generated output exactly covers the canonical account set."""
    expected = {
        (
            row.source_row_id,
            str(row.value["company_id"]),
            asset_type,
            brand_kit_id,
            template_id,
        )
        for row in rows
        for asset_type in REQUIRED_ASSET_TYPES
    }
    observed = [
        (
            str(item.get("source_row_id")),
            str(item.get("company_id")),
            str(item.get("asset_type")),
            str(item.get("brand_kit_id")),
            str(item.get("template_id")),
        )
        for item in deliverables
    ]
    observed_set = set(observed)
    if len(observed) != len(observed_set):
        raise CampaignPlanError("generated campaign contains duplicate deliverables")
    missing = expected - observed_set
    unexpected = observed_set - expected
    if missing or unexpected:
        raise CampaignPlanError(
            "generated campaign does not exactly cover the canonical accounts: "
            f"{len(missing)} missing and {len(unexpected)} unexpected"
        )
    return {
        "canonical_company_count": len(rows),
        "expected_deliverable_count": len(expected),
        "observed_deliverable_count": len(observed),
        "validated": True,
    }


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
    deliverables = _make_deliverables(
        rows,
        brand_kit_id=brand_kit_id,
        template_id=template_id,
    )
    completion_evidence = _validate_generated_campaign(
        rows,
        deliverables,
        brand_kit_id=brand_kit_id,
        template_id=template_id,
    )
    source_evidence = {
        "snapshot_id": pagination[0]["snapshot_id"],
        "expected_row_count": pagination[0]["total_row_count"],
        "observed_row_count": len(collected_rows),
    }

    return {
        "request": {
            "brand_kit_id": brand_kit_id,
            "template_id": template_id,
        },
        "source_row_ids": [row.source_row_id for row in rows],
        "deliverables": deliverables,
        "skipped_rows": skipped_rows,
        "pagination": pagination,
        "source_evidence": source_evidence,
        "completion_evidence": completion_evidence,
        "complete": True,
    }


def evaluate_campaign_coverage(
    plan: dict[str, Any],
    accounts: list[dict[str, Any]],
) -> tuple[bool, dict[str, Any]]:
    """Compare a plan exactly with expectations derived from source accounts."""

    def result(code: str, message: str, **facts: Any) -> tuple[bool, dict[str, Any]]:
        passed = code == "complete"
        return passed, {"code": code, "message": message, **facts}

    expected_input = [
        CollectedRow(str(index), dict(account))
        for index, account in enumerate(accounts)
    ]
    expected_rows, expected_skipped = resolve_account_identity(expected_input)
    request = plan.get("request")
    if not isinstance(request, dict):
        return result("missing_request", "plan has no request configuration")
    brand_kit_id = request.get("brand_kit_id")
    template_id = request.get("template_id")
    if not isinstance(brand_kit_id, str) or not isinstance(template_id, str):
        return result(
            "invalid_request",
            "plan request must contain string brand_kit_id and template_id",
        )

    expected_source_ids = [row.source_row_id for row in expected_rows]
    observed_source_ids = [str(value) for value in plan.get("source_row_ids", [])]
    expected_source_counter = Counter(expected_source_ids)
    observed_source_counter = Counter(observed_source_ids)
    if observed_source_counter != expected_source_counter:
        missing = list((expected_source_counter - observed_source_counter).elements())
        unexpected = list((observed_source_counter - expected_source_counter).elements())
        duplicated = sorted(
            row_id
            for row_id, count in observed_source_counter.items()
            if count > expected_source_counter.get(row_id, 0)
        )
        return result(
            "source_row_mismatch",
            "plan source rows do not exactly match canonical source rows",
            missing_source_row_ids=missing,
            unexpected_source_row_ids=unexpected,
            duplicated_source_row_ids=duplicated,
        )

    if plan.get("skipped_rows") != expected_skipped:
        return result(
            "skipped_row_mismatch",
            "plan does not account for invalid and duplicate source rows exactly",
            expected_skipped_rows=expected_skipped,
            observed_skipped_rows=plan.get("skipped_rows"),
        )

    deliverables = plan.get("deliverables")
    if not isinstance(deliverables, list):
        return result("invalid_deliverables", "plan deliverables must be a list")

    expected_companies = {str(row.value["company_id"]) for row in expected_rows}
    observed_companies = {str(item.get("company_id")) for item in deliverables}
    missing_companies = sorted(expected_companies - observed_companies)
    unexpected_companies = sorted(observed_companies - expected_companies)
    if missing_companies or unexpected_companies:
        return result(
            "company_mismatch",
            "plan companies do not exactly match canonical companies",
            missing_company_ids=missing_companies,
            unexpected_company_ids=unexpected_companies,
        )

    asset_keys = [
        (str(item.get("company_id")), str(item.get("asset_type")))
        for item in deliverables
    ]
    duplicate_assets = sorted(
        {key for key, count in Counter(asset_keys).items() if count > 1}
    )
    if duplicate_assets:
        return result(
            "duplicate_deliverables",
            "plan contains duplicate company assets",
            duplicate_company_assets=duplicate_assets,
        )

    wrong_configuration = [
        {
            "company_id": item.get("company_id"),
            "asset_type": item.get("asset_type"),
        }
        for item in deliverables
        if item.get("brand_kit_id") != brand_kit_id
        or item.get("template_id") != template_id
    ]
    if wrong_configuration:
        return result(
            "request_configuration_mismatch",
            "deliverables do not use the campaign request configuration",
            mismatched_deliverable_count=len(wrong_configuration),
        )

    expected_deliverables = _make_deliverables(
        expected_rows,
        brand_kit_id=brand_kit_id,
        template_id=template_id,
    )

    def deliverable_key(item: dict[str, Any]) -> tuple[str, ...]:
        return (
            str(item.get("source_row_id")),
            str(item.get("company_id")),
            str(item.get("company_name")),
            str(item.get("asset_type")),
            str(item.get("brand_kit_id")),
            str(item.get("template_id")),
        )

    expected_counter = Counter(map(deliverable_key, expected_deliverables))
    observed_counter = Counter(map(deliverable_key, deliverables))
    if observed_counter != expected_counter:
        missing_count = sum((expected_counter - observed_counter).values())
        unexpected_count = sum((observed_counter - expected_counter).values())
        return result(
            "deliverable_mismatch",
            "plan deliverables do not exactly match expected company assets",
            missing_deliverable_count=missing_count,
            unexpected_deliverable_count=unexpected_count,
        )

    expected_source_evidence = {
        "expected_row_count": len(accounts),
        "observed_row_count": len(accounts),
    }
    source_evidence = plan.get("source_evidence")
    if not isinstance(source_evidence, dict) or any(
        source_evidence.get(key) != value
        for key, value in expected_source_evidence.items()
    ):
        return result(
            "source_evidence_mismatch",
            "plan source-completeness evidence does not match the input",
            expected=expected_source_evidence,
            observed=source_evidence,
        )

    expected_completion_evidence = {
        "canonical_company_count": len(expected_rows),
        "expected_deliverable_count": len(expected_deliverables),
        "observed_deliverable_count": len(deliverables),
        "validated": True,
    }
    if plan.get("completion_evidence") != expected_completion_evidence:
        return result(
            "completion_evidence_mismatch",
            "plan completion evidence does not match observed coverage",
            expected=expected_completion_evidence,
            observed=plan.get("completion_evidence"),
        )
    if plan.get("complete") is not True:
        return result("not_complete", "campaign did not declare completion")

    return result(
        "complete",
        "every canonical company has exactly the requested assets",
        source_row_count=len(accounts),
        canonical_company_count=len(expected_rows),
        skipped_row_count=len(expected_skipped),
        deliverable_count=len(deliverables),
    )
