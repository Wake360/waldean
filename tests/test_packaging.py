import re
from pathlib import Path

import yaml

REPO = Path(__file__).parent.parent


def test_action_version_matches_package():
    # pyproject.toml's version is a plain `version = "x.y.z"` line; a regex
    # keeps this test dependency-free rather than requiring tomllib (py3.11+)
    # or a tomli backport for the py3.10 CI leg.
    pyproject = (REPO / "pyproject.toml").read_text()
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject)
    assert match, "no version found in pyproject.toml"
    pkg_version = match.group(1)

    action = yaml.safe_load((REPO / "action.yml").read_text())
    action_version = action["inputs"]["version"]["default"]

    assert action_version == pkg_version


def test_init_version_matches_package():
    pyproject = (REPO / "pyproject.toml").read_text()
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject)
    assert match, "no version found in pyproject.toml"
    pkg_version = match.group(1)

    init_text = (REPO / "waldean" / "__init__.py").read_text()
    init_match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    assert init_match, "no __version__ in waldean/__init__.py"
    assert init_match.group(1) == pkg_version


def test_readme_version_references_match_package():
    pyproject = (REPO / "pyproject.toml").read_text()
    pkg_version = re.search(r'(?m)^version\s*=\s*"([^"]+)"', pyproject).group(1)
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    refs = re.findall(r"Wake360/waldean@v([0-9][^\s`]*)", readme)
    refs += re.findall(r"rev:\s*v([0-9][^\s`]*)", readme)
    assert refs
    assert set(refs) == {pkg_version}


def test_readme_sample_matches_golden():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    golden = (REPO / "tests" / "golden" / "leaky.md").read_text(encoding="utf-8")
    assert golden.strip() in readme


def test_readme_names_status_sections():
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    for label in ("Experimental", "Known limitations"):
        assert label in readme
