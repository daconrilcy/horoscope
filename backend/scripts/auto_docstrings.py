"""
Script utilitaire pour documenter automatiquement le projet.

Actions:
- Ajouter/mettre à jour l'en-tête de module pour chaque fichier Python
- Ajouter/mettre à jour les docstrings des fonctions, méthodes et classes
- Nettoyer les chaînes littérales orphelines (faux "docstrings" mal placés)
- Ajouter un en-tête de commentaire aux fichiers non-Python (sh, ps1, yml, toml, ini, txt)

Les docstrings générées sont en français et incluent: description courte,
signature (paramètres, types, retour) et une section TODO.
"""

from __future__ import annotations

import argparse
import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parents[0]
SELF_PATH = Path(__file__).resolve()


@dataclass
class Insertion:
    index: int
    lines: list[str]


def list_py_files(root: Path) -> Iterable[Path]:
    for p in root.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        if p.resolve() == SELF_PATH:
            continue  # ne pas s'auto-modifier
        yield p


def has_module_docstring(module: ast.Module) -> bool:
    return ast.get_docstring(module, clean=False) is not None


def get_shebang_and_encoding_prefix_len(lines: list[str]) -> int:
    i = 0
    if i < len(lines) and lines[i].startswith("#!"):
        i += 1
    while i < len(lines) and lines[i].lstrip().startswith("#"):
        i += 1
    if i < len(lines) and lines[i].strip() == "":
        i += 1
    return i


def guess_module_purpose(path: Path) -> str:
    name = path.stem.lower()
    parent = path.parent.name.lower()
    if "schema" in name:
        return "Définit les schémas Pydantic de l'API."
    if parent == "api" or "route" in name:
        return "Expose les routes et structures de l'API."
    if parent == "domain":
        return "Logique métier et entités du domaine."
    if parent == "infra":
        return "Accès aux données et intégrations d'infrastructure."
    if parent == "core":
        return "Configuration et composants de base de l'application."
    if parent == "middlewares":
        return "Middlewares ASGI/Starlette pour l'API."
    return "Objectif du module à préciser."


def make_module_docstring(path: Path) -> list[str]:
    rel = path.as_posix()
    title = f"Module {rel}"
    purpose = guess_module_purpose(path)
    doc = (
        f'"""\n{title}\n\n'
        f"Objectif du module: {purpose}\n\n"
        "TODO:\n- Préciser le rôle exact et exemples d'utilisation.\n"
        '"""\n\n'
    )
    return [doc]


def _ann_to_str(node: ast.AST|None) -> str:
    if node is None:
        return "Any"
    try:
        return ast.unparse(node)
    except Exception:
        return "Any"


def _format_params(args: ast.arguments) -> list[tuple[str, str]]:
    params: list[tuple[str, str]] = []
    for a in args.posonlyargs + args.args:
        if a.arg == "self":
            continue
        params.append((a.arg, _ann_to_str(a.annotation)))
    if args.vararg:
        params.append(("*" + args.vararg.arg, _ann_to_str(args.vararg.annotation)))
    for a in args.kwonlyargs:
        params.append((a.arg, _ann_to_str(a.annotation)))
    if args.kwarg:
        params.append(("**" + args.kwarg.arg, _ann_to_str(args.kwarg.annotation)))
    return params


def _pydantic_fields(cls: ast.ClassDef) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for stmt in cls.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            out.append((stmt.target.id, _ann_to_str(stmt.annotation)))
    return out


def _is_pydantic_model(cls: ast.ClassDef) -> bool:
    for b in cls.bases:
        try:
            name = ast.unparse(b)
        except Exception:
            name = ""
        if name.endswith("BaseModel") or name == "BaseModel":
            return True
    return False


def generate_entity_docstring_for_function(fn: ast.AST, indent: str) -> list[str]:
    assert isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
    params = _format_params(fn.args)
    ret = _ann_to_str(fn.returns)
    lines: list[str] = []
    lines.append(indent + '"""' + f"Fonction {fn.name}." + "\n")
    if params:
        lines.append(indent + "\n" + indent + "Paramètres:\n")
        for n, t in params:
            lines.append(indent + f"- {n}: {t}\n")
    if ret and ret != "Any":
        lines.append(indent + "\n" + indent + f"Retour: {ret}\n")
    lines.append(indent + "\n" + indent + "TODO:\n")
    lines.append(indent + "- Décrire le comportement, contraintes et erreurs.\n")
    lines.append(indent + '"""\n')
    return lines


def generate_entity_docstring_for_class(cls: ast.ClassDef, indent: str) -> list[str]:
    pydantic = _is_pydantic_model(cls)
    fields = _pydantic_fields(cls) if pydantic else []
    lines: list[str] = []
    title = f"Modèle Pydantic {cls.name}" if pydantic else f"Classe {cls.name}"
    lines.append(indent + '"""' + title + ".\n")
    if fields:
        lines.append(indent + "\n" + indent + "Champs:\n")
        for n, t in fields:
            lines.append(indent + f"- {n}: {t}\n")
    lines.append(indent + "\n" + indent + "TODO:\n")
    lines.append(indent + "- Compléter la description et les invariants.\n")
    lines.append(indent + '"""\n')
    return lines


def first_body_indent(lines: list[str], lineno: int) -> str:
    idx = max(0, min(len(lines) - 1, lineno - 1))
    line = lines[idx]
    return line[: len(line) - len(line.lstrip(" \t"))]


def insert_module_docstring(lines: list[str], path: Path, module: ast.Module) -> list[str]:
    if has_module_docstring(module):
        return lines
    ins_at = get_shebang_and_encoding_prefix_len(lines)
    header = make_module_docstring(path)
    return lines[:ins_at] + header + lines[ins_at:]


def collect_docstring_insertions(tree: ast.AST, lines: list[str]) -> list[Insertion]:
    insertions: list[Insertion] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.body:
                continue
            # Always place docstring strictly at the first line of the body
            if not ast.get_docstring(node, clean=False):
                first_stmt = node.body[0]
                indent = first_body_indent(lines, first_stmt.lineno)
                doc_lines = generate_entity_docstring_for_function(node, indent)
                insertions.append(Insertion(index=first_stmt.lineno - 1, lines=doc_lines))
        elif isinstance(node, ast.ClassDef):
            if not ast.get_docstring(node, clean=False):
                indent = first_body_indent(lines, node.lineno + 1)
                doc_lines = generate_entity_docstring_for_class(node, indent)
                insertions.append(Insertion(index=node.lineno, lines=doc_lines))
    insertions.sort(key=lambda ins: ins.index, reverse=True)
    return insertions


def apply_insertions(lines: list[str], insertions: list[Insertion]) -> list[str]:
    for ins in insertions:
        lines = lines[: ins.index] + ins.lines + lines[ins.index :]
    return lines


def _is_placeholder_docstring(s: str) -> bool:
    t = s.strip().lower()
    keys = ["compl", "objecti", "classe", "methode", "méthode", "fonction"]
    return any(k in t for k in keys)


def _remove_stray_string_exprs(lines: list[str], tree: ast.AST) -> tuple[list[str], int]:
    to_remove: list[tuple[int, int]] = []

    def record_span(n: ast.AST):
        ln = getattr(n, "lineno", None)
        eln = getattr(n, "end_lineno", ln)
        if ln is None:
            return
        to_remove.append((ln - 1, (eln or ln) - 1))

    valid_ids = set()
    if isinstance(tree, ast.Module) and tree.body:
        if isinstance(tree.body[0], ast.Expr) \
              and isinstance(getattr(tree.body[0], "value", None), ast.Constant) \
        and isinstance(tree.body[0].value.value, str):
            valid_ids.add(id(tree.body[0]))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(getattr(first, "value", None), 
                                                          ast.Constant) \
                                                            and isinstance(first.value.value, str):
                valid_ids.add(id(first))

    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(getattr(node, "value", None), ast.Constant) \
            and isinstance(node.value.value, str):
            if id(node) not in valid_ids:
                record_span(node)

    if not to_remove:
        return lines, 0
    to_remove.sort(key=lambda x: x[0], reverse=True)
    new_lines = lines[:]
    removed = 0
    for start, end in to_remove:
        del new_lines[start : end + 1]
        removed += (end - start + 1)
    return new_lines, removed


def _replace_placeholder_docstrings(lines: list[str], tree: ast.AST, path: Path) -> tuple[list[str], int, bool]:  # noqa: E501
    new_lines = lines[:]
    replaced = 0
    module_replaced = False
    replacements: list[tuple[int, int, list[str]]] = []

    # Module docstring
    if isinstance(tree, ast.Module) and tree.body:
        n0 = tree.body[0]
        if isinstance(n0, ast.Expr) and isinstance(getattr(n0, "value", None), ast.Constant) \
            and isinstance(n0.value.value, str):
            if _is_placeholder_docstring(n0.value.value) or "Objectif du module" in n0.value.value:
                header = make_module_docstring(path)
                start = n0.lineno - 1
                end = getattr(n0, "end_lineno", n0.lineno) - 1
                replacements.append((start, end, header))
                module_replaced = True

    # Classes and functions
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                and isinstance(first.value.value, str):
                if _is_placeholder_docstring(first.value.value):
                    indent = first_body_indent(new_lines, first.lineno)
                    gen = generate_entity_docstring_for_function(node, indent)
                    start = first.lineno - 1
                    end = getattr(first, "end_lineno", first.lineno) - 1
                    replacements.append((start, end, gen))
        elif isinstance(node, ast.ClassDef) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) \
                and isinstance(first.value.value, str):
                if _is_placeholder_docstring(first.value.value):
                    indent = first_body_indent(new_lines, node.lineno + 1)
                    gen = generate_entity_docstring_for_class(node, indent)
                    start = first.lineno - 1
                    end = getattr(first, "end_lineno", first.lineno) - 1
                    replacements.append((start, end, gen))

    for start, end, gen in sorted(replacements, key=lambda t: t[0], reverse=True):
        del new_lines[start : end + 1]
        for i, line in enumerate(gen):
            new_lines.insert(start + i, line)
        replaced += 1

    return new_lines, replaced, module_replaced


def process_py_file(path: Path) -> tuple[bool, str]:
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    try:
        tree = ast.parse(original)
    except SyntaxError:
        return False, "skipped (syntax error)"

    new_lines = insert_module_docstring(lines, path, tree)

    updated_source = "".join(new_lines)
    try:
        tree2 = ast.parse(updated_source)
    except SyntaxError:
        tree2 = tree

    insertions = collect_docstring_insertions(tree2, new_lines)
    interim_lines = apply_insertions(new_lines, insertions) if insertions else new_lines

    try:
        tree3 = ast.parse("".join(interim_lines))
    except SyntaxError:
        tree3 = tree2
    cleaned_lines, removed = _remove_stray_string_exprs(interim_lines, tree3)

    try:
        tree4 = ast.parse("".join(cleaned_lines))
    except SyntaxError:
        tree4 = tree3
    enriched_lines, replaced, _module_rep = _replace_placeholder_docstrings(cleaned_lines, tree4, path)  # noqa: E501

    final_lines = enriched_lines
    if final_lines == lines:
        return False, "unchanged"
    path.write_text("".join(final_lines), encoding="utf-8")
    return True, f"updated (+{len(insertions)} insertions, -{removed} stray, ~{replaced} enriched)"


def _process_py_file_insert_only(path: Path) -> tuple[bool, str]:
    """
    Variant sûre: insère module docstring et docstrings entités uniquement.

    Pas de suppression ni remplacement, pour éviter les risques sur la syntaxe.
    """
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)
    try:
        tree = ast.parse(original)
    except SyntaxError:
        return False, "skipped (syntax error)"

    new_lines = insert_module_docstring(lines, path, tree)
    updated_source = "".join(new_lines)
    try:
        tree2 = ast.parse(updated_source)
    except SyntaxError:
        tree2 = tree
    insertions = collect_docstring_insertions(tree2, new_lines)
    final_lines = apply_insertions(new_lines, insertions) if insertions else new_lines
    if final_lines == lines:
        return False, "unchanged"
    path.write_text("".join(final_lines), encoding="utf-8")
    return True, f"updated (+{len(insertions)} insertions)"


def _add_header_comment(text: str, purpose: str) -> str:
    lines = text.splitlines(keepends=True)
    ins = 0
    if lines and lines[0].startswith("#!"):
        ins = 1
    header = [f"# Objectif du fichier: {purpose}\n", "# TODO: compléter cette description.\n", "\n"]
    return "".join(lines[:ins] + header + lines[ins:])


def process_non_python_files() -> list[Path]:
    exts = {".sh", ".ps1", ".yml", ".yaml", ".toml", ".ini", ".txt"}
    changed: list[Path] = []
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in exts:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except Exception:
            continue
        first_nonblank = next((ln for ln in content.splitlines() if ln.strip()), "")
        if first_nonblank.strip().startswith("# Objectif du fichier"):
            continue
        purpose = f"Décrire l'objectif de {path.name}"
        updated = _add_header_comment(content, purpose)
        if updated != content:
            path.write_text(updated, encoding="utf-8")
            changed.append(path)
    return changed


def run_for_root(root: Path, do_clean: bool, include_non_python: bool) -> None:
    changed = 0
    processed = 0
    for py in list_py_files(root):
        ok, msg = process_py_file(py) if do_clean else _process_py_file_insert_only(py)
        processed += 1
        if ok:
            changed += 1
        rel = py.relative_to(root)
        print(f"[auto-doc] {rel} -> {msg}")
    print(f"Fichiers traités: {processed}, modifiés: {changed}")
    

def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-docstring pour backend")
    parser.add_argument("--path", type=str, default=str(BACKEND_ROOT), help="Chemin à traiter (par défaut: backend)")  # noqa: E501
    parser.add_argument("--include-non-python", action="store_true", help="Ajouter des en-têtes aux fichiers non-Python")  # noqa: E501
    parser.add_argument("--no-clean", action="store_true", help="N'effectuer que l'insertion (pas de nettoyage/enrichissement)")  # noqa: E501
    args = parser.parse_args()

    root = Path(args.path).resolve()
    run_for_root(root, do_clean=(not args.no_clean), include_non_python=args.include_non_python)

    if args.include_non_python:
        other_changed = process_non_python_files()
        if other_changed:
            print(f"Fichiers non-Python mis à jour: {len(other_changed)}")


if __name__ == "__main__":
    main()
