"""Reporting harness. Prints facts, reaches no conclusion.

Two sections.

The first runs whatever `build_campaign_plan` currently does against every
paging shape in `src/sources.py`. Those shapes are all things the account
service has actually done in production.

The second calls the shipped coverage check against a clean plan and against
four damaged copies of that same plan, and prints what it returned each time.
Reading down that column tells you whether the check can tell the difference
between them.

Neither section decides anything. Both are here so you can see the behaviour
instead of reasoning about it.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Callable

import repair_lab
import sources
from repair_lab import TargetAccountTool, build_campaign_plan

SHAPE_TIMEOUT_SECONDS = 20

CHECK_NAMES = (
    "evaluate_campaign_coverage",
    "evaluate_coverage",
    "check_campaign_coverage",
    "verify_campaign_coverage",
    "audit_campaign_coverage",
    "evaluate_plan",
    "verify_plan",
    "check_plan",
    "check_coverage",
    "verify_coverage",
    "audit_plan",
)


def _timeboxed(work: Callable[[], Any]) -> tuple[str, Any]:
    """Run `work`, giving up rather than hanging on a shape that never ends."""
    box: dict[str, Any] = {}

    def target() -> None:
        try:
            box["value"] = work()
        except BaseException as error:  # noqa: BLE001 - reported, not handled
            box["error"] = error

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(SHAPE_TIMEOUT_SECONDS)
    if thread.is_alive():
        return "timeout", f"still running after {SHAPE_TIMEOUT_SECONDS}s"
    if "error" in box:
        return "raised", box["error"]
    return "returned", box["value"]


def _describe(plan: dict[str, Any]) -> dict[str, Any]:
    deliverables = plan.get("deliverables", [])
    skipped_rows = plan.get("skipped_rows", [])
    return {
        "raw": plan.get("source_evidence", {}).get("observed_row_count"),
        "invalid": sum(
            row.get("reason") == "missing_company_id" for row in skipped_rows
        ),
        "duplicates": sum(
            row.get("reason") == "duplicate_company_id" for row in skipped_rows
        ),
        "companies": len({str(d.get("company_id")) for d in deliverables}),
        "deliverables": len(deliverables),
    }


def paging_shapes(accounts: list[dict], request: dict) -> None:
    print("=" * 100)
    print("A. every paging shape in src/sources.py")
    print("=" * 100)
    print()
    print(
        f"{'shape':30}{'status':11}{'raw':>7}{'invalid':>9}"
        f"{'duplicate':>11}{'companies':>11}{'assets':>9}"
    )

    loaders: list[tuple[str, Any]] = [("TargetAccountTool", TargetAccountTool)]
    loaders += [(cls.__name__, cls) for cls in sources.ALL_SOURCES]

    for name, loader_class in loaders:
        outcome, value = _timeboxed(
            lambda cls=loader_class: build_campaign_plan(
                cls(accounts),
                brand_kit_id=request["brand_kit"]["id"],
                template_id=request["template"]["id"],
            )
        )
        if outcome != "returned":
            if isinstance(value, repair_lab.PaginationError):
                status = "rejected"
                reason = f"{value.code}: {value}"
            else:
                status = "failed"
                reason = f"{type(value).__name__}: {value}"
            print(f"{name:30}{status:11}{reason[:58]}")
            continue
        facts = _describe(value)
        print(
            f"{name:30}{'complete':11}{facts['raw']:>7}"
            f"{facts['invalid']:>9}{facts['duplicates']:>11}"
            f"{facts['companies']:>11}{facts['deliverables']:>9}"
        )

    print()
    print(f"uploaded rows in the list: {len(accounts)}")
    print()


def _damaged_copies(plan: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Four plans that are each wrong in a way a customer would notice."""
    deliverables = plan.get("deliverables", [])
    companies = sorted({str(d.get("company_id")) for d in deliverables})

    dropped = set(companies[: max(len(companies) // 5, 1)])
    missing = [
        d for d in deliverables if str(d.get("company_id")) not in dropped
    ]

    duplicated = list(deliverables)
    if companies:
        first = companies[0]
        duplicated += [
            dict(d) for d in deliverables if str(d.get("company_id")) == first
        ]

    rekitted = [dict(d) for d in deliverables]
    for item in rekitted:
        item["brand_kit_id"] = "brand-kit-not-the-one-they-picked"

    short = [d for d in deliverables]
    if companies:
        target = companies[-1]
        for index, item in enumerate(short):
            if str(item.get("company_id")) == target:
                short = short[:index] + short[index + 1 :]
                break

    return [
        (f"{len(dropped)} companies deleted", {**plan, "deliverables": missing}),
        ("one company campaigned twice", {**plan, "deliverables": duplicated}),
        ("every brand kit wrong", {**plan, "deliverables": rekitted}),
        ("one company short an asset", {**plan, "deliverables": short}),
    ]


def _resolve_check() -> tuple[str, Callable[..., Any]] | None:
    for name in CHECK_NAMES:
        function = getattr(repair_lab, name, None)
        if callable(function):
            return name, function
    return None


def check_discrimination(accounts: list[dict], request: dict) -> None:
    print("=" * 78)
    print("B. what the coverage check returns for a clean plan and four broken ones")
    print("=" * 78)
    print()

    resolved = _resolve_check()
    if resolved is None:
        print("No coverage check found in src/repair_lab.py under any of:")
        print("  " + ", ".join(CHECK_NAMES))
        print("If yours has a different name, add it to CHECK_NAMES in audit.py.")
        print()
        return

    name, check = resolved
    print(f"calling repair_lab.{name}\n")

    plan = build_campaign_plan(
        TargetAccountTool(accounts),
        brand_kit_id=request["brand_kit"]["id"],
        template_id=request["template"]["id"],
    )

    cases = [("clean plan, untouched", plan)] + _damaged_copies(plan)

    for label, variant in cases:
        outcome, value = _timeboxed(lambda v=variant: check(v, accounts))
        if outcome == "raised" and "positional argument" in str(value):
            outcome, value = _timeboxed(lambda v=variant: check(v))
        if outcome != "returned":
            rendered = f"<{outcome}: {value}>"
        else:
            rendered = json.dumps(value, default=str)
        print(f"  {label:32} -> {rendered[:150]}")

    print()


def main() -> None:
    accounts = json.loads(Path("fixtures/target_accounts.json").read_text())
    request = json.loads(Path("fixtures/request.json").read_text())
    paging_shapes(accounts, request)
    check_discrimination(accounts, request)
    print("This command reports. It does not grade, and it is not a test suite.")


if __name__ == "__main__":
    main()
