import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_skill_frontmatter_and_plugin_manifests_agree():
    text = (ROOT / "skills" / "waldean" / "SKILL.md").read_text()
    front = yaml.safe_load(text.split("---")[1])
    plugin = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    assert front["name"] == plugin["name"] == market["plugins"][0]["name"] == "waldean"
    assert front["description"]
    assert "waldean check" in text
