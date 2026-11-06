import pytest

from module_knowledge.coverage import score_ledger


def test_curated_ledger_checks_verbatim_source_and_linked_candidate():
    evidence = [{"source_id": "slide", "locator": "slide 8", "text": "Prepared after the sales budget. Production includes desired ending inventory."}]
    draft = {"items": [{"id": "i1", "source_id": "slide", "locator": "slide 8", "text": "Production after sales budget."}]}
    ledger = [{"id": "a1", "source_id": "slide", "locator": "slide 8", "source_quote": "Prepared after the sales budget.", "importance": "essential", "gold_status": "present", "candidate_status": "present", "candidate_item_ids": ["i1"], "reviewer": "assistant_provisional"}]

    result = score_ledger(ledger, evidence, draft)

    assert result["total_atoms"] == 1
    assert result["candidate_statuses"] == {"present": 1}
    assert result["gate"] == "not_passed_user_review_pending"


def test_curated_ledger_rejects_invented_quote_or_wrong_item():
    evidence = [{"source_id": "slide", "locator": "slide 8", "text": "Sales budget comes first."}]
    draft = {"items": [{"id": "i1", "source_id": "another", "locator": "p.1", "text": "Unknown"}]}
    base = {"id": "a1", "source_id": "slide", "locator": "slide 8", "importance": "essential", "gold_status": "unknown", "candidate_status": "present", "candidate_item_ids": ["i1"], "reviewer": "assistant_provisional"}
    with pytest.raises(ValueError, match="quote"):
        score_ledger([{**base, "source_quote": "Not on the slide"}], evidence, draft)
    with pytest.raises(ValueError, match="candidate"):
        score_ledger([{**base, "source_quote": "Sales budget comes first."}], evidence, draft)
