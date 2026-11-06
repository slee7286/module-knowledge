import json
from pathlib import Path


def test_four_user_selected_modules_are_configured_for_the_shared_latex_note_form():
    config_path = Path(__file__).parents[1] / "config" / "module-formats.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert config["default_format"] == "latex"
    formats = {entry["name"]: entry["format"] for entry in config["modules"]}
    assert formats == {
        "Econometrics 1": "latex",
        "Machine Learning": "latex",
        "Microeconomics 2": "latex",
        "Corporate Finance and Capital Markets": "latex",
    }
    assert config["template"] == "module-notes"
