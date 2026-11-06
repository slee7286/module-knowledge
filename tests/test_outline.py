from module_knowledge import outline
from module_knowledge.outline import (
    deduplicate_items,
    merge_sections,
    normalize_sections,
    separate_repeated_items,
)


def _item(identifier, text, page):
    return {
        "id": identifier,
        "text": text,
        "source_id": f"slide-{page}",
        "relative_path": "source/lectures/lecture1.pdf",
        "locator": f"p. {page}",
        "visual_unreviewed": False,
    }


def test_exact_duplicate_points_collapse_without_losing_source_items():
    first = _item("a", "Demand falls when price rises.", 3)
    repeated = _item("b", "Demand falls when price rises.", 4)
    other = _item("c", "Revenue depends on price and quantity.", 5)

    unique = deduplicate_items([first, repeated, other])

    assert len(unique) == 2
    assert unique[0]["text"] == first["text"]
    assert unique[0]["items"] == [first, repeated]
    assert unique[1]["items"] == [other]


def test_exact_repeated_bullets_merge_across_topic_headings_with_both_sources():
    first = _item("a", "The present value of a perpetuity is C/r.", 11)
    repeated = _item("b", "The present value of a perpetuity is C/r.", 12)
    unique = _item("c", "A growing perpetuity discounts at r minus g.", 13)
    sections = [
        {"heading": "Perpetuities", "bullets": [{
            "text": first["text"], "support_items": [first], "children": [],
        }]},
        {"heading": "General formulas", "bullets": [
            {"text": repeated["text"], "support_items": [repeated], "children": []},
            {"text": unique["text"], "support_items": [unique], "children": []},
        ]},
    ]

    result = merge_sections(sections)

    assert len(result) == 2
    repeated_bullet = result[0]["bullets"][0]
    assert repeated_bullet["support_items"] == [first, repeated]
    assert [bullet["text"] for bullet in result[1]["bullets"]] == [unique["text"]]


def test_duplicate_child_of_parent_is_removed_without_losing_its_details():
    parent = _item("a", "The choice is constrained by the budget.", 1)
    duplicate = _item("b", "The choice is constrained by the budget.", 2)
    detail = _item("c", "The budget limits affordable combinations.", 3)
    sections = [{"heading": "Choice", "bullets": [{
        "text": parent["text"],
        "support_items": [parent],
        "children": [{
            "text": duplicate["text"],
            "support_items": [duplicate],
            "children": [{"text": detail["text"], "support_items": [detail], "children": []}],
        }],
    }]}]

    result = merge_sections(sections)

    assert result[0]["bullets"][0]["support_items"] == [parent, duplicate]
    assert [child["text"] for child in result[0]["bullets"][0]["children"]] == [detail["text"]]


def test_outline_fallback_preserves_input_the_model_did_not_assign():
    first = _item("a", "Demand falls when price rises.", 3)
    repeated = _item("b", "Demand falls when price rises.", 4)
    other = _item("c", "Revenue depends on price and quantity.", 5)
    unique = deduplicate_items([first, repeated, other])
    response = [{
        "heading": "Demand",
        "bullets": [{
            "text": f"{unique[0]['id']}: A higher price lowers demand.",
            "item_ids": [unique[0]["id"]],
            "children": [],
        }],
    }]

    sections, fallback_count = normalize_sections(response, unique)

    assert fallback_count == 1
    assert sections[0]["bullets"][0]["text"] == "A higher price lowers demand."
    assert sections[0]["bullets"][0]["support_items"] == [first, repeated]
    fallback = next(section for section in sections if section["heading"] == "Additional points")
    assert fallback["bullets"][0]["text"] == other["text"]
    supported = [item["id"] for section in sections for bullet in section["bullets"]
                 for node in [bullet, *bullet["children"]] for item in node["support_items"]]
    assert sorted(supported) == ["a", "b", "c"]


def test_outline_normalizer_removes_second_pass_ids_from_bullet_text():
    item = _item("a", "A present value is discounted by time.", 4)
    node = {"id": "r1-000001", "text": item["text"], "items": [item]}
    raw_sections = [{"heading": "Present value", "bullets": [{
        "text": f"{node['id']}: A present value is discounted by time.",
        "item_ids": [node["id"]],
        "children": [],
    }]}]

    sections, fallback_count = normalize_sections(raw_sections, [node])

    assert fallback_count == 0
    assert sections[0]["bullets"][0]["text"] == "A present value is discounted by time."


def test_id_only_outline_bullets_restore_the_input_text_and_keep_nesting():
    first = _item("a", "The regression slope measures the conditional association.", 4)
    second = _item("b", "A causal interpretation requires additional assumptions.", 5)
    nodes = [
        {"id": "r1-000001", "text": first["text"], "items": [first]},
        {"id": "r1-000002", "text": second["text"], "items": [second]},
    ]
    raw = [{"heading": "Regression", "bullets": [{
        "text": "r1-000001", "item_ids": ["r1-000001"],
        "children": [{"text": "r1-000002", "item_ids": ["r1-000002"]}],
    }]}]

    sections, restored_count = normalize_sections(raw, nodes)

    assert sections[0]["bullets"][0]["text"] == first["text"]
    assert sections[0]["bullets"][0]["children"][0]["text"] == second["text"]
    assert restored_count == 2


def test_ids_embedded_in_model_prose_fall_back_to_the_original_point():
    item = _item("a", "Expected value is a probability-weighted mean.", 7)
    nodes = [{"id": "u000001", "text": item["text"], "items": [item]}]
    raw = [{"heading": "Expectation", "bullets": [{
        "text": "See u000001 for the definition.", "item_ids": ["u000001"], "children": [],
    }]}]

    sections, fallback_count = normalize_sections(raw, nodes)

    assert fallback_count == 1
    assert sections[0]["bullets"][0]["text"] == item["text"]


def test_local_model_error_is_reported_while_source_points_are_retained(monkeypatch, tmp_path):
    item = _item("a", "Demand falls when price rises.", 3)

    def fail_request(*args, **kwargs):
        raise OSError("local model unavailable")

    monkeypatch.setattr(outline, "_request_outline", fail_request)
    result = outline.consolidate_items(
        [item],
        context="test note",
        endpoint="http://127.0.0.1:11435",
        model="qwen3:8b",
        checkpoint_dir=tmp_path,
    )

    assert result["stats"]["fallback_items"] == 1
    assert result["stats"]["batch_errors"] == [{"pass": 1, "batch": 1, "error_type": "OSError"}]
    assert result["sections"][0]["bullets"][0]["text"] == item["text"]



def test_repeated_points_are_removed_across_groups_but_exact_tutorial_items_stay():
    covered = {}
    first_group_items = [
        _item("a", "Demand falls when price rises.", 3),
        _item("b", "Demand falls when price rises.", 4),
        _item("c", "Supply rises when price rises.", 5),
    ]
    first_kept, first_repeats = separate_repeated_items(first_group_items, covered, "Lecture 1")

    repeated = _item("d", "Demand falls when price rises.", 7)
    new_point = _item("e", "Equilibrium occurs where supply equals demand.", 8)
    exact_question = {"id": "q", "text": "Question 1", "exact_source_text": True}
    second_kept, second_repeats = separate_repeated_items(
        [repeated, new_point, exact_question], covered, "Tutorial 1"
    )

    assert first_kept == first_group_items
    assert first_repeats == {}
    assert second_kept == [new_point, exact_question]
    assert second_repeats == {"Lecture 1": [repeated]}


def test_second_pass_merges_points_across_initial_outline_batches(monkeypatch, tmp_path):
    items = [_item(f"item-{index}", f"Point {index} is important.", index) for index in range(1, 42)]
    calls = []

    def respond(nodes, **kwargs):
        calls.append((nodes, kwargs["context"]))
        bullets = []
        if "pass 1" in kwargs["context"]:
            bullets.append({
                "text": "Combined first two points.",
                "item_ids": [nodes[0]["id"], nodes[1]["id"]],
                "children": [],
            })
            bullets.extend({"text": node["text"], "item_ids": [node["id"]], "children": []} for node in nodes[2:])
        else:
            target_ids = [nodes[1]["id"], nodes[-1]["id"]]
            bullets.append({
                "text": "Combined points from separate first-pass batches.",
                "item_ids": target_ids,
                "children": [],
            })
            bullets.extend(
                {"text": node["text"], "item_ids": [node["id"]], "children": []}
                for index, node in enumerate(nodes)
                if index not in {1, len(nodes) - 1}
            )
        return [{"heading": "Topic", "bullets": bullets}]

    monkeypatch.setattr(outline, "_request_outline", respond)
    result = outline.consolidate_items(
        items,
        context="test cross-batch consolidation",
        endpoint="http://127.0.0.1:11435",
        model="qwen3:8b",
        checkpoint_dir=tmp_path,
    )

    assert result["stats"]["passes"] == 2
    assert len(calls) == 3
    merged = next(
        bullet for section in result["sections"] for bullet in section["bullets"]
        if len(bullet["support_items"]) == 2
    )
    assert {item["id"] for item in merged["support_items"]} == {"item-3", "item-41"}
    supported = [item["id"] for section in result["sections"] for bullet in section["bullets"]
                 for node in [bullet, *bullet["children"]] for item in node["support_items"]]
    assert sorted(supported) == sorted(item["id"] for item in items)


def test_second_pass_runs_for_large_notes_even_without_first_pass_reduction(monkeypatch, tmp_path):
    items = [_item(f"item-{index}", f"Unique point {index}.", index) for index in range(1, 42)]
    calls = []

    def respond(nodes, **kwargs):
        calls.append((len(nodes), kwargs["context"]))
        return [{"heading": "Topic", "bullets": [
            {"text": node["text"], "item_ids": [node["id"]], "children": []}
            for node in nodes
        ]}]

    monkeypatch.setattr(outline, "_request_outline", respond)
    result = outline.consolidate_items(
        items,
        context="test pass sequencing",
        endpoint="http://127.0.0.1:11435",
        model="qwen3:8b",
        checkpoint_dir=tmp_path,
    )

    assert result["stats"]["passes"] == 2
    assert [count for count, _ in calls] == [40, 1, 41]
    assert result["stats"]["fallback_items"] == 0


def test_invalid_large_response_is_retried_with_smaller_batches(monkeypatch, tmp_path):
    items = [_item(f"item-{index}", f"Point {index}.", index) for index in range(1, 22)]
    calls = []

    def respond(nodes, **kwargs):
        calls.append(len(nodes))
        if len(nodes) > 10:
            raise ValueError("response could not be parsed")
        return [{"heading": "Topic", "bullets": [
            {"text": node["text"], "item_ids": [node["id"]], "children": []}
            for node in nodes
        ]}]

    monkeypatch.setattr(outline, "_request_outline", respond)
    result = outline.consolidate_items(
        items,
        context="test retry",
        endpoint="http://127.0.0.1:11435",
        model="qwen3:8b",
        checkpoint_dir=tmp_path,
    )

    assert calls[0] == 21
    assert sorted(calls[1:]) == [5, 6, 10, 11]
    assert result["stats"]["fallback_items"] == 0
    assert result["stats"]["batch_errors"] == [
        {"pass": 1, "batch": 1, "error_type": "ValueError", "recovered": True},
        {"pass": 1, "batch": 1, "error_type": "ValueError", "recovered": True},
    ]
    assert result["stats"]["consolidated_bullets"] == len(items)
    supported = [
        item["id"] for section in result["sections"] for bullet in section["bullets"]
        for node in [bullet, *bullet["children"]] for item in node["support_items"]
    ]
    assert sorted(supported) == sorted(item["id"] for item in items)


def test_failed_small_batch_preserves_every_source_item(monkeypatch, tmp_path):
    items = [_item(f"item-{index}", f"Point {index}.", index) for index in range(1, 22)]
    calls = []

    def fail(nodes, **kwargs):
        calls.append(len(nodes))
        raise ValueError("invalid response")

    monkeypatch.setattr(outline, "_request_outline", fail)
    result = outline.consolidate_items(
        items, context="exhausted retries", endpoint="http://127.0.0.1:11435",
        model="qwen3:8b", checkpoint_dir=tmp_path,
    )

    assert sorted(calls) == [5, 6, 10, 11, 21]
    assert result["stats"]["fallback_items"] == len(items)
    assert all(not error.get("recovered") for error in result["stats"]["batch_errors"])
    supported = [item["id"] for section in result["sections"] for bullet in section["bullets"]
                 for item in bullet["support_items"]]
    assert sorted(supported) == sorted(item["id"] for item in items)


def test_transport_error_does_not_trigger_smaller_batch_retries(monkeypatch, tmp_path):
    items = [_item(f"item-{index}", f"Point {index}.", index) for index in range(1, 22)]
    calls = []

    def fail(nodes, **kwargs):
        calls.append(len(nodes))
        raise OSError("model unavailable")

    monkeypatch.setattr(outline, "_request_outline", fail)
    result = outline.consolidate_items(
        items, context="transport error", endpoint="http://127.0.0.1:11435",
        model="qwen3:8b", checkpoint_dir=tmp_path,
    )

    assert calls == [21]
    assert result["stats"]["fallback_items"] == len(items)
