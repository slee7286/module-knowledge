from module_knowledge.baseline import extractive_baseline


def test_extractive_floor_keeps_exact_official_text_and_skips_visual_pages():
    frozen = {"module": "Accounting", "slice": "development", "sources": [{"id": "s", "sha256": "abc", "role": "lecture_slides", "relative_path": "Lecture 2/s.pptx"}]}
    blocks = [
        {"source_id": "s", "source_sha256": "abc", "relative_path": "Lecture 2/s.pptx", "locator": "slide 1", "role": "lecture_slides", "text": "Budgets are financial plans.\nThey guide decisions.", "quality_flags": []},
        {"source_id": "s", "source_sha256": "abc", "relative_path": "Lecture 2/s.pptx", "locator": "slide 2", "role": "lecture_slides", "text": "Sales | £1,500", "quality_flags": ["needs_visual_review"]},
    ]

    candidate = extractive_baseline(frozen, blocks)

    assert candidate["model"] == "extractive-floor"
    assert [item["text"] for item in candidate["items"]] == ["Budgets are financial plans.", "They guide decisions."]
    assert candidate["skipped"][0]["locator"] == "slide 2"
