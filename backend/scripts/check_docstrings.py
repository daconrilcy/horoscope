"""Script de vérification des docstrings manquantes.

Ce script analyse le code source pour identifier les modules et fonctions sans docstrings et génère
un rapport de conformité.
"""

from __future__ import annotations

import ast
from pathlib import Path

from backend.core.constants import SCRIPT_PREVIEW_LIMIT


def main() -> None:
    """Point d'entrée principal pour la vérification des docstrings.

    Parcourt tous les fichiers Python du projet et identifie les modules et fonctions sans
    docstring.
    """
    root = Path(__file__).resolve().parents[1]
    missing_module: list[Path] = []
    missing_fn: dict[Path, list[str]] = {}
    for p in sorted(root.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        try:
            src = p.read_text(encoding="utf-8")
            tree = ast.parse(src)
        except Exception:
            print(f"[skip:syntax] {p.relative_to(root)}")
            continue
        if ast.get_docstring(tree, clean=False) is None:
            missing_module.append(p)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
                and ast.get_docstring(node, clean=False) is None
            ):
                missing_fn.setdefault(p, []).append(node.name)

    print("\nModules sans docstring:", len(missing_module))
    for p in missing_module:
        print(" -", p.relative_to(root))
    print("\nFonctions/méthodes sans docstring:")
    for p, names in missing_fn.items():
        sorted_names = sorted(set(names))
        preview = ", ".join(sorted_names[:SCRIPT_PREVIEW_LIMIT])
        suffix = " ..." if len(sorted_names) > SCRIPT_PREVIEW_LIMIT else ""
        msg = f" - {p.relative_to(root)}: {len(sorted_names)} -> {preview}{suffix}"
        print(msg)


if __name__ == "__main__":
    main()
