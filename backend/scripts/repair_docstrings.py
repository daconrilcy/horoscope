"""
Répare les docstrings mal insérées par l’auto-génération.

Supprime:
- L’en-tête de module auto-généré (bloc triple quotes "Module ... Objectif du module ...").
- Les blocs de docstrings auto-générés pour fonctions/classes ("Fonction ", "Classe ",
  "Modèle Pydantic ") quand ils ne suivent pas immédiatement un def/class.
- Les lignes orphelines internes (Paramètres:/Retour:/TODO:/bullets) hors de tout bloc string.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


MARKERS = (
    '"""Fonction ',
    '"""Classe ',
    '"""Modèle Pydantic ',
)
HEADER_START = "Module "
HEADER_OBJECTIF = "Objectif du module"
INTERNAL_TOKENS = (
    "Paramètres:",
    "Retour:",
    "TODO:",
    "- Préciser le rôle exact",
    "- Décrire le comportement, contraintes et erreurs.",
    "- Compléter la description et les invariants.",
)


def is_marker_line(line: str) -> bool:
    s = line.lstrip()
    return any(s.startswith(m) for m in MARKERS)


def should_keep(after_sig_open: bool, at_top: bool) -> bool:
    if at_top:
        return True
    return after_sig_open


def repair_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    new_lines: list[str] = []
    i = 0
    changed = False
    after_sig_open = False
    seen_code = False
    triple_open: str | None = None

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # manage triple-quoted context and potential auto-generated blocks
        if triple_open is None and (stripped.startswith('"""') or stripped.startswith("'''")):
            # Peek for header or generated block
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            header_like = HEADER_START in nxt and any(
                HEADER_OBJECTIF in (lines[j] if j < len(lines) else "") for j in range(i + 1, i + 8)
            )
            if any(line.lstrip().startswith(m) for m in MARKERS) or header_like:
                # Skip full block
                quote = '"""' if stripped.startswith('"""') else "'''"
                i += 1
                while i < len(lines):
                    if quote in lines[i]:
                        i += 1
                        break
                    i += 1
                changed = True
                continue
            else:
                triple_open = '"""' if stripped.startswith('"""') else "'''"
                new_lines.append(line)
                i += 1
                continue

        if triple_open is not None:
            new_lines.append(line)
            if triple_open in line:
                triple_open = None
            i += 1
            continue

        if not seen_code and stripped:
            seen_code = True

        # Remove stray internal token lines that leaked into code
        if stripped.startswith(INTERNAL_TOKENS):
            changed = True
            i += 1
            continue

        # Detect misplaced generated docstring (without opening quotes on same line)
        if is_marker_line(line):
            keep = should_keep(after_sig_open, at_top=False)
            if not keep:
                # Remove current line and subsequent until a closing triple quote if any
                i += 1
                while i < len(lines):
                    if ('"""' in lines[i]) or ("'''" in lines[i]):
                        i += 1
                        break
                    i += 1
                changed = True
                continue

        # Track def/class context window
        if stripped.startswith("def ") or stripped.startswith("class "):
            after_sig_open = True
        elif stripped and not stripped.startswith("#"):
            after_sig_open = False

        new_lines.append(line)
        i += 1

    if changed:
        path.write_text("".join(new_lines), encoding="utf-8")
    return changed


def main() -> None:
    total = 0
    fixed = 0
    for p in ROOT.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        if p.name == Path(__file__).name:
            continue
        total += 1
        try:
            if repair_file(p):
                print(f"[repair] fixed {p.relative_to(ROOT)}")
                fixed += 1
        except Exception as e:
            print(f"[repair] error on {p}: {e}")
    print(f"Repaired: {fixed} / {total}")


if __name__ == "__main__":
    main()
