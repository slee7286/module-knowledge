import pytest

import module_knowledge.latex as latex


def test_question_precedes_its_answer_before_the_next_question():
    assemble = getattr(latex, "assemble_practice_pairs", None)
    assert callable(assemble), "A reusable question/answer pairing renderer is required"
    question = "Question A\n\\begin{verbatim}\n  source = 'unchanged'\n\\end{verbatim}"
    rendered = assemble([
        {"id": "a", "question": question, "answer": "Answer A",
         "answer_label": "Worked answer — not official"},
        {"id": "b", "question": "Question B", "answer": "Answer B",
         "answer_label": "Provided official solution"},
    ])
    assert question in rendered
    assert rendered.index("Question A") < rendered.index("Answer A") < rendered.index("Question B") < rendered.index("Answer B")
    assert "Provided official solution" in rendered
    assert "not official" in rendered


@pytest.mark.parametrize("invalid", [
    {"id": "a", "question": "", "answer": "Answer", "answer_label": "Worked answer"},
    {"id": "a", "question": "Question", "answer": "Answer"},
    {"id": "a", "question": "Question", "answer": None, "answer_label": "Worked answer"},
])
def test_practice_pair_rejects_incomplete_material(invalid):
    with pytest.raises(ValueError, match="practice pair"):
        latex.assemble_practice_pairs([invalid])


def test_practice_pair_rejects_duplicate_identity():
    pair = {"id": "same", "question": "Question", "answer": "Answer", "answer_label": "Worked answer"}
    with pytest.raises(ValueError, match="Duplicate"):
        latex.assemble_practice_pairs([pair, pair])
