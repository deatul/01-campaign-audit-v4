from __future__ import annotations

import argparse
import json
from pathlib import Path

from repair_lab import (
    TargetAccountTool,
    build_campaign_plan,
    evaluate_campaign_coverage,
)

PAGE_SIZES = (10, 25, 100)


def _run(accounts: list[dict], request: dict, page_size: int) -> dict:
    plan = build_campaign_plan(
        TargetAccountTool(accounts),
        brand_kit_id=request["brand_kit"]["id"],
        template_id=request["template"]["id"],
        page_size=page_size,
    )
    deliverables = plan["deliverables"]
    kits: dict[str, int] = {}
    for item in deliverables:
        kits[item["brand_kit_id"]] = kits.get(item["brand_kit_id"], 0) + 1
    return {
        "rows campaigned": len(plan["source_row_ids"]),
        "deliverables": len(deliverables),
        "distinct company_id in plan": len(
            {item["company_id"] for item in deliverables}
        ),
        "complete flag": plan["complete"],
        "_kits": kits,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", default="fixtures/target_accounts.json")
    args = parser.parse_args()

    accounts = json.loads(Path(args.list).read_text())
    request = json.loads(Path("fixtures/request.json").read_text())

    results = {size: _run(accounts, request, size) for size in PAGE_SIZES}

    print(f"list                          : {args.list}")
    print(f"uploaded rows                 : {len(accounts)}")
    print(f"brand kit selected on request : {request['brand_kit']['id']}")
    print(f"template selected on request  : {request['template']['id']}")
    print()

    header = "".join(f"{f'page_size={s}':>16}" for s in PAGE_SIZES)
    print(f"{'':30}{header}")
    for field in (
        "rows campaigned",
        "deliverables",
        "distinct company_id in plan",
        "complete flag",
    ):
        cells = "".join(f"{str(results[s][field]):>16}" for s in PAGE_SIZES)
        print(f"{field:30}{cells}")

    print()
    print("deliverables by brand kit (page_size=25):")
    for kit, count in sorted(results[25]["_kits"].items()):
        print(f"  {kit:32} {count:>6}")

    plan = build_campaign_plan(
        TargetAccountTool(accounts),
        brand_kit_id=request["brand_kit"]["id"],
        template_id=request["template"]["id"],
    )
    passed, detail = evaluate_campaign_coverage(plan, accounts)
    print()
    print(f"shipped check returned        : {passed}")
    print(f"shipped check said            : {detail}")


if __name__ == "__main__":
    main()
