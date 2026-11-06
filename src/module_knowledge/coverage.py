"""Validate and tally a private, manually curated atomic-coverage ledger."""

from __future__ import annotations

from collections import Counter


def score_ledger(ledger: list[dict], evidence: list[dict], draft: dict) -> dict:
    official = {(block["source_id"], block["locator"]): block for block in evidence}
    items = {item["id"]: item for item in draft["items"]}
    counts: Counter[str] = Counter()
    importance: Counter[str] = Counter()
    for atom in ledger:
        key = (atom["source_id"], atom["locator"])
        block = official.get(key)
        if block is None or " ".join(atom["source_quote"].split()) not in " ".join(block["text"].split()):
            raise ValueError(f"Source quote missing at {key}")
        status = atom["candidate_status"]
        if status not in {"present", "partial", "missing", "unreviewed"}:
            raise ValueError(f"Invalid candidate status: {status}")
        if status in {"present", "partial"} and not atom["candidate_item_ids"]:
            raise ValueError("Reviewed candidate status needs a linked candidate item")
        for item_id in atom["candidate_item_ids"]:
            item = items.get(item_id)
            if item is None or (item["source_id"], item["locator"]) != key:
                raise ValueError(f"Linked candidate item does not match source: {item_id}")
        counts[status] += 1
        importance[atom["importance"]] += 1
    return {
        "total_atoms": len(ledger),
        "candidate_statuses": dict(counts),
        "importance": dict(importance),
        "reviewers": sorted({atom["reviewer"] for atom in ledger}),
        "gate": "not_passed_user_review_pending",
        "scope": "curated sample only; not the complete module denominator",
    }
