from __future__ import annotations


def normalize(nb, stem: str):
    for i, cell in enumerate(nb.cells):
        cell["id"] = f"{stem}-{i}"
        cell.get("metadata", {}).pop("execution", None)
    return nb
