#!/usr/bin/env python3
"""Garde de perimetre d'ecriture : un agent ne commite que ce que son prompt declare.

EXTRAIT REDUIT du garde en service, pas le garde. Ce qui est conserve : la lecture du
bloc `<scope>` d'un prompt, l'extraction des chemins autorises, la correspondance avec
les fichiers stages, et le refus en code 1 sur depassement. Ce qui est retire : quatre
niveaux de repli sur des formats de prompt anciens, la piste d'audit des derogations, et
le controle d'allowlist des imports.

Le garde en service porte cinq niveaux d'extraction du perimetre au lieu d'un seul. Ce
n'est pas de la sur-ingenierie : chaque niveau a ete ajoute apres qu'un agent a trouve un
format de prompt que le niveau precedent ne voyait pas. Le cas le plus tenace, dix
recidives sur six sessions, etait un bloc `<scope>` melangeant lecture et ecriture dans une
section Markdown : le garde lisait les deux et laissait passer les ecritures hors
perimetre. Un garde vit contre ce qu'il garde.

    python3 scope_guard.py --prompt <prompt.md> --staged <f1> <f2> ...
    python3 scope_guard.py --prompt <prompt.md> --staged-from-git

Codes de sortie : 0 conforme, 1 depassement, 2 aucun perimetre declare.
"""
from __future__ import annotations

import fnmatch
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# Prefixes de ligne a ignorer : une section « INTERDIT » liste des chemins qui ne
# sont pas des autorisations. Les lire comme telles inverserait le sens du garde.
_SKIP_PREFIXES = ("HORS SCOPE", "INTERDIT", "NOTE", "ATTENTION", "EXCLUS")

# Un perimetre peut nommer un fichier dont le nom n'est pas connu a l'avance.
_PLACEHOLDER_PATTERN = re.compile(r"<(?:TS|TIMESTAMP|DATE|HASH|SESSION|RUN|ID)>", re.IGNORECASE)

# Sections d'un bloc <scope> structure. Leur seule presence interdit le repli global.
_SECTIONS_CONNUES = r"<(?:lecture|interdit|exclus|[ÉéEe]criture)\b"

EXIT_CONFORME = 0
EXIT_DEPASSEMENT = 1
EXIT_SANS_PERIMETRE = 2


class PerimetreAmbiguError(RuntimeError):
    """Le prompt porte plusieurs blocs <scope> et rien ne dit lequel fait foi.

    Choisir le plus long etait une heuristique : une duplication de prompt ou un ancien
    perimetre laisse en place suffisait a designer le mauvais. Pour un controle de
    permission, une ambiguite doit refuser.
    """


def _extract_scope_block(content: str) -> str | None:
    """Contenu de l'unique bloc <scope>...</scope>. Leve si le prompt en porte plusieurs."""
    strict = list(re.finditer(r"^<scope>(.*?)^</scope>", content, re.DOTALL | re.MULTILINE))
    if len(strict) > 1:
        raise PerimetreAmbiguError(f"{len(strict)} blocs <scope> dans le prompt")
    if strict:
        return strict[0].group(1)
    inline = list(re.finditer(r"<scope>(.*?)</scope>", content, re.DOTALL | re.IGNORECASE))
    if len(inline) > 1:
        raise PerimetreAmbiguError(f"{len(inline)} blocs <scope> dans le prompt")
    if inline:
        return inline[0].group(1)
    return None


def _element_full_text(elem: ET.Element) -> str:
    parts = [elem.text or ""]
    for sub in elem:
        parts.append(_element_full_text(sub))
        parts.append(sub.tail or "")
    return "".join(parts)


def _extract_xml_writing_section(scope_block: str) -> str | None:
    """Sous-balise <écriture> du bloc, tolerante a la casse et a l'accent."""
    try:
        tree = ET.fromstring(f"<root>{scope_block}</root>")
    except ET.ParseError:
        return None
    for elem in tree.iter():
        if elem.tag.lower() in ("écriture", "ecriture"):
            return _element_full_text(elem)
    return None


def _extract_regex_writing_section(scope_block: str) -> str | None:
    """Repli quand le XML ne parse pas : la sous-balise <écriture> par expression reguliere.

    Ce repli n'est pas decoratif. Un perimetre contient souvent un nom de fichier avec un
    placeholder, `reports/W3_<TS>.json`, et `<TS>` est une balise ouvrante que le parseur
    XML refuse. Sans ce niveau, le garde tombe sur le repli suivant, lit le bloc entier, et
    prend les chemins de <lecture> et de <interdit> pour des autorisations d'ecriture. Le
    garde laisse alors passer exactement ce qu'il devait bloquer.
    """
    m = re.search(r"<[ÉéEe]criture[^>]*>(.*?)</[ÉéEe]criture>", scope_block,
                  re.DOTALL | re.IGNORECASE)
    return m.group(1) if m else None


def _parse_path_patterns(section: str) -> list[str]:
    """Chemins d'une section a puces. Une ligne sans `/` ni `.` n'est pas un chemin."""
    patterns: list[str] = []
    for raw in section.splitlines():
        ligne = raw.strip()
        if not ligne or ligne.startswith("#"):
            continue
        if any(ligne.upper().startswith(kw) for kw in _SKIP_PREFIXES):
            continue
        if ligne[:2] in ("- ", "* ", "+ "):
            ligne = ligne[2:].strip()
        chemin = re.split(r"[\s(]", ligne, maxsplit=1)[0].strip().strip("`").strip()
        if not chemin or chemin.startswith("**"):
            continue
        if "/" not in chemin and "." not in chemin:
            continue
        patterns.append(chemin)
    return patterns


def extract_scope_patterns(prompt_path: str | Path) -> tuple[list[str], str]:
    """Rend (chemins autorises, niveau d'extraction). Liste vide = aucun perimetre."""
    contenu = Path(prompt_path).read_text(encoding="utf-8")
    try:
        bloc = _extract_scope_block(contenu)
    except PerimetreAmbiguError:
        return [], "perimetre-ambigu"
    if bloc is None:
        return [], "no-scope"
    section = _extract_xml_writing_section(bloc)
    if section is not None:
        return _parse_path_patterns(section), "xml-strict"
    section = _extract_regex_writing_section(bloc)
    if section is not None:
        return _parse_path_patterns(section), "xml-regex"
    # Le repli sur le bloc entier ne s'applique QUE si le bloc n'est pas structure du tout.
    # Des qu'une section connue apparait, lire le bloc entier reviendrait a promouvoir les
    # chemins de <lecture> et de <interdit> en autorisations d'ecriture. Une revue exterieure
    # a montre le 2026-09-11 qu'un scope portant <lecture> et <interdit> sans <écriture>
    # passait par ce chemin : `src/auth/` devenait ecrivable alors qu'il etait en lecture.
    if re.search(r"<[ÉéEe]criture", bloc, re.IGNORECASE):
        return [], "ecriture-illisible"
    if re.search(_SECTIONS_CONNUES, bloc, re.IGNORECASE):
        return [], "scope-structure-sans-section-ecriture"
    direct = _parse_path_patterns(bloc)
    if direct:
        return direct, "xml-direct"
    return [], "no-writing-section"


def _regex_de_placeholder(pattern: str) -> re.Pattern:
    """Compile un motif a placeholder en regex ou le placeholder ne franchit pas un `/`.

    `fnmatch` traduit `*` en « n'importe quoi », separateurs compris : le perimetre
    `reports/W3_<TS>.json` acceptait alors `reports/W3_x/nested/any.json`. Un placeholder
    designe un fragment de nom, pas une arborescence.
    """
    morceaux = _PLACEHOLDER_PATTERN.split(pattern)
    return re.compile("[^/]*".join(re.escape(m) for m in morceaux))


def file_matches_scope(filepath: str, patterns: list[str]) -> bool:
    """Chemin exact, prefixe de repertoire, glob explicite, ou placeholder dans son segment."""
    for pattern in patterns:
        norme = pattern.rstrip("/")
        if filepath == norme or filepath.startswith(norme + "/"):
            return True
        if _PLACEHOLDER_PATTERN.search(norme):
            motif = _regex_de_placeholder(norme)
            if motif.fullmatch(filepath) or motif.fullmatch(filepath.split("/")[0]):
                return True
            continue
        if "*" in norme and (fnmatch.fnmatch(filepath, norme)
                             or fnmatch.fnmatch(filepath, norme + "/*")):
            return True
    return False


class StagedFilesUnavailableError(RuntimeError):
    """L'ensemble des fichiers stages n'a pas pu etre etabli.

    Distinct d'un ensemble vide observe avec succes. Sans cette distinction, un `git diff`
    qui echoue rendait une liste vide, et le garde declarait conforme un commit qu'il
    n'avait jamais inspecte.
    """


def get_staged_files(repo: Path | None = None) -> list[str]:
    """Fichiers reellement dans l'index. Les modifications hors index ne comptent pas :
    elles appartiennent souvent a un autre agent qui travaille en parallele.

    Leve `StagedFilesUnavailableError` si l'enumeration echoue.
    """
    r = subprocess.run(["git", "diff", "--cached", "--name-only"],
                       capture_output=True, text=True, cwd=repo or Path.cwd())
    if r.returncode != 0:
        raise StagedFilesUnavailableError(
            f"git diff --cached a rendu {r.returncode} : {r.stderr.strip() or 'sans message'}")
    return [l.strip() for l in r.stdout.splitlines() if l.strip()]


def run_check(prompt_path: str | Path, staged: list[str]) -> tuple[int, list[str], str]:
    """Rend (code de sortie, fichiers hors perimetre, niveau d'extraction).

    Aucun perimetre declare rend 2 et non 0 : un prompt sans perimetre n'est pas un
    prompt qui autorise tout, c'est un prompt qu'on ne peut pas verifier.
    """
    patterns, niveau = extract_scope_patterns(prompt_path)
    if not patterns:
        return EXIT_SANS_PERIMETRE, [], niveau
    hors = [f for f in staged if not file_matches_scope(f, patterns)]
    return (EXIT_DEPASSEMENT if hors else EXIT_CONFORME), hors, niveau


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--prompt" not in args:
        print(__doc__, file=sys.stderr)
        return EXIT_SANS_PERIMETRE
    prompt = args[args.index("--prompt") + 1]
    if "--staged-from-git" in args:
        try:
            staged = get_staged_files()
        except StagedFilesUnavailableError as exc:
            print(f"[scope_guard] REFUS : {exc}", file=sys.stderr)
            return EXIT_SANS_PERIMETRE
    elif "--staged" in args:
        staged = [a for a in args[args.index("--staged") + 1:] if not a.startswith("--")]
    else:
        # Ne pas savoir quoi controler n'est pas la meme chose que n'avoir rien a controler.
        print("[scope_guard] REFUS : aucune source de fichiers stages. "
              "Passer --staged <f...> ou --staged-from-git.", file=sys.stderr)
        return EXIT_SANS_PERIMETRE
    code, hors, niveau = run_check(prompt, staged)
    if code == EXIT_SANS_PERIMETRE:
        print(f"[scope_guard] REFUS : aucun perimetre d'ecriture declare ({niveau})", file=sys.stderr)
    elif code == EXIT_DEPASSEMENT:
        print(f"[scope_guard] COMMIT REFUSE : {len(hors)} fichier(s) hors perimetre", file=sys.stderr)
        for f in hors:
            print(f"    {f}", file=sys.stderr)
    else:
        print(f"[scope_guard] OK : {len(staged)} fichier(s) dans le perimetre ({niveau})")
    return code


if __name__ == "__main__":
    sys.exit(main())
