"""Répare les docstrings mal insérées par l'auto-génération.

Supprime:
- L'en-tête de module auto-généré (bloc triple quotes "Module ... Objectif du module ...").
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
    """Vérifie si une ligne contient un marqueur de docstring.

    Args:
        line: Ligne à vérifier.

    Returns:
        bool: True si la ligne contient un marqueur.
    """
    s = line.lstrip()
    return any(s.startswith(m) for m in MARKERS)


def should_keep(after_sig_open: bool, at_top: bool) -> bool:
    """Détermine si une ligne doit être conservée.

    Args:
        after_sig_open: Si on est après l'ouverture d'une signature.
        at_top: Si on est en haut du fichier.

    Returns:
        bool: True si la ligne doit être conservée.
    """
    if at_top:
        return True
    return after_sig_open


def _is_header_block(lines: list[str], i: int) -> bool:
    """Vérifie si on est dans un bloc d'en-tête auto-généré.

    Args:
        lines: Lignes du fichier.
        i: Index de ligne actuel.

    Returns:
        bool: True si c'est un bloc d'en-tête.
    """
    if i + 1 >= len(lines):
        return False
    nxt = lines[i + 1]
    return HEADER_START in nxt and any(
        HEADER_OBJECTIF in (lines[j] if j < len(lines) else "")
        for j in range(i + 1, min(i + 8, len(lines)))
    )


def _is_generated_block(line: str) -> bool:
    """Vérifie si une ligne commence un bloc auto-généré.

    Args:
        line: Ligne à vérifier.

    Returns:
        bool: True si c'est un bloc auto-généré.
    """
    stripped = line.strip()
    return (stripped.startswith('"""') or stripped.startswith("'''")) and (
        any(line.lstrip().startswith(m) for m in MARKERS) or _is_header_block([line], 0)
    )


def _skip_triple_quoted_block(lines: list[str], i: int) -> int:
    """Saute un bloc triple-quoté complet.

    Args:
        lines: Lignes du fichier.
        i: Index de ligne de début.

    Returns:
        int: Nouvel index après le bloc.
    """
    quote = '"""' if lines[i].strip().startswith('"""') else "'''"
    i += 1
    while i < len(lines):
        if quote in lines[i]:
            i += 1
            break
        i += 1
    return i


def _should_remove_marker_line(line: str, after_sig_open: bool) -> bool:
    """Détermine si une ligne marqueur doit être supprimée.

    Args:
        line: Ligne à vérifier.
        after_sig_open: Si on est après une signature.

    Returns:
        bool: True si la ligne doit être supprimée.
    """
    return is_marker_line(line) and not should_keep(after_sig_open, at_top=False)


def _skip_misplaced_docstring(lines: list[str], i: int) -> int:
    """Saute une docstring mal placée.

    Args:
        lines: Lignes du fichier.
        i: Index de ligne de début.

    Returns:
        int: Nouvel index après la docstring.
    """
    i += 1
    while i < len(lines):
        if ('"""' in lines[i]) or ("'''" in lines[i]):
            i += 1
            break
        i += 1
    return i


def _process_triple_quoted_context(
    lines: list[str], i: int, triple_open: str | None
) -> tuple[int, str | None, bool]:
    """Traite le contexte triple-quoté.

    Args:
        lines: Lignes du fichier.
        i: Index actuel.
        triple_open: Type de guillemets ouverts.

    Returns:
        tuple[int, str | None, bool]: (nouvel index, nouveau triple_open, modifié).
    """
    line = lines[i]
    stripped = line.strip()

    if triple_open is None and (stripped.startswith('"""') or stripped.startswith("'''")):
        if _is_generated_block(line):
            return _skip_triple_quoted_block(lines, i), None, True
        else:
            return i + 1, '"""' if stripped.startswith('"""') else "'''", False

    if triple_open is not None:
        if triple_open in line:
            return i + 1, None, False
        return i + 1, triple_open, False

    return i, triple_open, False


def _process_line_content(
    line: str, stripped: str, after_sig_open: bool, seen_code: bool
) -> tuple[bool, bool, bool]:
    """Traite le contenu d'une ligne.

    Args:
        line: Ligne complète.
        stripped: Ligne sans espaces.
        after_sig_open: Si on est après une signature.
        seen_code: Si on a vu du code.

    Returns:
        tuple[bool, bool, bool]: (modifié, nouveau_after_sig_open, nouveau_seen_code).
    """
    changed = False
    new_seen_code = seen_code

    if not seen_code and stripped:
        new_seen_code = True

    # Supprimer les lignes de tokens internes orphelines
    if stripped.startswith(INTERNAL_TOKENS):
        changed = True
        return changed, after_sig_open, new_seen_code

    # Détecter les docstrings mal placées
    if _should_remove_marker_line(line, after_sig_open):
        changed = True
        return changed, after_sig_open, new_seen_code

    # Suivre le contexte def/class
    new_after_sig_open = after_sig_open
    if stripped.startswith("def ") or stripped.startswith("class "):
        new_after_sig_open = True
    elif stripped and not stripped.startswith("#"):
        new_after_sig_open = False

    return changed, new_after_sig_open, new_seen_code


def repair_file(path: Path) -> bool:
    """Répare les docstrings dans un fichier.

    Args:
        path: Chemin vers le fichier à réparer.

    Returns:
        bool: True si le fichier a été modifié.
    """
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

        # Gérer le contexte triple-quoté et les blocs auto-générés
        new_i, new_triple_open, was_changed = _process_triple_quoted_context(lines, i, triple_open)
        if was_changed:
            changed = True
            i = new_i
            continue

        if new_triple_open != triple_open:
            triple_open = new_triple_open
            if triple_open is not None:
                new_lines.append(line)
            i = new_i
            continue

        # Traiter le contenu de la ligne
        line_changed, new_after_sig_open, new_seen_code = _process_line_content(
            line, stripped, after_sig_open, seen_code
        )
        if line_changed:
            changed = True
            if stripped.startswith(INTERNAL_TOKENS):
                i += 1
                continue
            elif _should_remove_marker_line(line, after_sig_open):
                i = _skip_misplaced_docstring(lines, i)
                continue

        after_sig_open = new_after_sig_open
        seen_code = new_seen_code
        new_lines.append(line)
        i += 1

    if changed:
        path.write_text("".join(new_lines), encoding="utf-8")
    return changed


def main() -> None:
    """Point d'entrée principal pour la réparation des docstrings.

    Parcourt tous les fichiers Python et répare les docstrings en supprimant les marqueurs
    temporaires.
    """
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
