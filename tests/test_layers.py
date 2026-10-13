import ast
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent / "waldean"
RANK = {"core": 0, "analysis": 1, "checks": 2, "llm": 3, "runtime": 4,
        "repair": 5, "experiment": 5, "bench": 5, "api": 6, "report": 7, "cli": 8}


def layer(parts: tuple[str, ...]) -> str:
    return parts[0].removesuffix(".py")


def imported_layers(path: Path):
    here = path.relative_to(PKG).parts
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.ImportFrom):
            if node.level:
                base = list(here[:-1])[: len(here) - node.level]
                target = base + (node.module.split(".") if node.module else [])
                names = [target] if node.module else [target + [a.name] for a in node.names]
            elif node.module and node.module.startswith("waldean."):
                names = [node.module.split(".")[1:]]
            else:
                continue
        elif isinstance(node, ast.Import):
            names = [a.name.split(".")[1:] for a in node.names if a.name.startswith("waldean.")]
        else:
            continue
        for n in names:
            if n:
                yield n[0], node.lineno


def test_layers_import_only_downward():
    bad = []
    for path in sorted(PKG.rglob("*.py")):
        rel = path.relative_to(PKG).parts
        if rel == ("__init__.py",):
            continue
        src = layer(rel)
        for dst, line in imported_layers(path):
            if dst != src and RANK[dst] >= RANK[src]:
                bad.append(f"{'/'.join(rel)}:{line} {src} -> {dst}")
    assert not bad, "\n".join(bad)


def test_every_module_has_a_layer():
    tops = {layer(p.relative_to(PKG).parts) for p in PKG.rglob("*.py")} - {"__init__"}
    assert tops <= set(RANK), tops - set(RANK)
