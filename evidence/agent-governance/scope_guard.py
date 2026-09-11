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

import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
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


_ITEM_CHEMIN = re.compile(r"^\s*(?:[-*+]\s+)?`?([\w.<>*?\-/]+)`?\s*$")


def _patterns_ancien_format_stricts(bloc: str) -> list[str]:
    """Ancien format : le bloc entier vaut perimetre d'ecriture, et uniquement s'il ne
    contient QUE des chemins. Toute autre ligne rend une liste vide, donc un refus.

    Le correctif du 2026-09-11 filtrait les en-tetes par liste noire de mots-cles
    (`INTERDIT`, `HORS SCOPE`, ...). Une liste noire laisse passer par construction tout
    nom qu'elle ne connait pas, et deux revues ont montre le lendemain quatre formulations
    qui traversaient : `## Interdit`, `INTERDIT :` seul sur sa ligne, `<read>`, `<read-only>`.
    Dans les quatre, les chemins en lecture seule devenaient des autorisations d'ecriture.

    Une liste blanche inverse la charge : ce que le garde ne sait pas classer, il le refuse.
    """
    chemins: list[str] = []
    for brut in bloc.splitlines():
        ligne = brut.strip()
        if not ligne:
            continue
        if ligne.startswith(("#", "<")) or ligne.endswith(":"):
            return []
        m = _ITEM_CHEMIN.match(ligne)
        if not m:
            return []
        chemin = m.group(1)
        if "/" not in chemin and "." not in chemin:
            return []
        chemins.append(chemin)
    return chemins


def extract_forbidden_patterns(prompt_path: str | Path) -> list[str]:
    """Chemins des sections <interdit> et <exclus>. Ils refusent, quelle que soit l'ecriture.

    Une section nommee « interdit » etait seulement absente des autorisations, jamais
    appliquee comme un refus. Un perimetre ecrivant `<écriture>src/ingestion/</écriture>` et
    `<interdit>src/ingestion/secrets/</interdit>` laissait donc passer `secrets/keys.py` :
    le chemin tombait sous l'autorisation, et l'interdiction ne servait a rien. C'est la
    facon naturelle d'ecrire une exception de perimetre, et le mot « interdit » ne peut pas
    se lire comme un commentaire.
    """
    try:
        bloc = _extract_scope_block(Path(prompt_path).read_text(encoding="utf-8"))
    except PerimetreAmbiguError:
        return []
    if not bloc:
        return []
    sections = re.findall(r"<(interdit|exclus)\b[^>]*>(.*?)</\1\s*>", bloc,
                          re.IGNORECASE | re.DOTALL)
    return [c for _, corps in sections for c in _parse_path_patterns(corps)]


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
    direct = _patterns_ancien_format_stricts(bloc)
    if direct:
        return direct, "xml-direct"
    return [], "no-writing-section"


def _regex_de_motif(pattern: str) -> re.Pattern:
    """Compile un motif de perimetre en regex ou aucun joker ne franchit un `/`.

    `fnmatch` traduit `*` en « n'importe quoi », separateurs compris : le perimetre
    `reports/W3_<TS>.json` acceptait alors `reports/W3_x/nested/any.json`. Le correctif du
    2026-09-11 avait ferme ce cas pour les seuls placeholders ; deux revues ont montre le
    lendemain que `reports/*.json` acceptait toujours `reports/private/secret.json`, par le
    meme `fnmatch`. La regle vaut pour les deux, et elle est la meme partout dans ce fichier :

        `*`  -> un fragment de nom, jamais une arborescence   -> [^/]*
        `?`  -> un caractere, jamais un separateur            -> [^/]
        `**` -> la traversee de repertoires, explicitement    -> .*

    Un joker qui traverse une arborescence doit s'ecrire. Sinon un perimetre nomme
    « les rapports » se lit « les rapports et tout ce qu'on peut ranger dessous ».
    """
    morceaux = _PLACEHOLDER_PATTERN.split(pattern)
    compiles = []
    for m in morceaux:
        # Ordre impose : `**` avant `*`, sinon le second consomme le premier.
        bout = re.escape(m).replace(r"\*\*", "\x00").replace(r"\*", "[^/]*")
        bout = bout.replace("\x00", ".*").replace(r"\?", "[^/]")
        compiles.append(bout)
    return re.compile("[^/]*".join(compiles))


def file_matches_scope(filepath: str, patterns: list[str]) -> bool:
    """Chemin exact, prefixe de repertoire, ou motif dont aucun joker ne franchit un `/`."""
    for pattern in patterns:
        norme = pattern.rstrip("/")
        if filepath == norme or filepath.startswith(norme + "/"):
            return True
        if _PLACEHOLDER_PATTERN.search(norme) or any(c in norme for c in "*?"):
            motif = _regex_de_motif(norme)
            if motif.fullmatch(filepath) or motif.fullmatch(filepath.split("/")[0]):
                return True
    return False


class StagedFilesUnavailableError(RuntimeError):
    """L'ensemble des fichiers stages n'a pas pu etre etabli.

    Distinct d'un ensemble vide observe avec succes. Sans cette distinction, un `git diff`
    qui echoue rendait une liste vide, et le garde declarait conforme un commit qu'il
    n'avait jamais inspecte.
    """


@dataclass(frozen=True)
class StagedMutation:
    """Une mutation indexee. `ancien` et `nouveau` sont tous deux renseignes pour un
    renommage ou une copie ; l'un des deux est None pour un ajout ou une suppression."""

    statut: str
    ancien: str | None
    nouveau: str | None

    @property
    def chemins(self) -> list[str]:
        """Les chemins que cette mutation touche. Un renommage en touche deux."""
        return [c for c in (self.ancien, self.nouveau) if c]


def get_staged_mutations(repo: Path | None = None) -> list[StagedMutation]:
    """Mutations reellement dans l'index, source et destination nommees.

    Un commit n'est pas une liste de chemins de destination. `git diff --cached --name-only`
    detecte les renommages par defaut et n'affiche alors que la destination : un agent
    deplacant `src/auth/session.py` vers un chemin autorise supprimait un fichier hors
    perimetre, et le garde declarait conforme. Deux revues independantes ont trouve ce
    contournement le 2026-09-11, sur le meme commit et par le meme chemin.

    Pour une porte de permission, supprimer, deplacer et renommer sont des ecritures au meme
    titre qu'ajouter. Les deux cotes d'un renommage doivent donc passer par la politique.

    `-z` en second lieu : sans lui, git met les chemins non ASCII entre guillemets et les
    echappe en octal, et un fichier legitimement dans le perimetre mais accentue etait refuse
    a tort. Un refus sans danger, mais bruyant dans un code en francais.

    Leve `StagedFilesUnavailableError` si l'enumeration echoue.
    """
    try:
        r = subprocess.run(["git", "diff", "--cached", "--name-status", "-z"],
                           capture_output=True, text=True, cwd=repo or Path.cwd())
    except OSError as exc:
        # git introuvable, repertoire de travail absent : le garde n'a pas pu regarder.
        # Sans ce cas, l'appel mourait sur une trace Python, ce qui se lit comme un silence.
        raise StagedFilesUnavailableError(f"git n'a pas pu etre lance : {exc}") from exc
    if r.returncode != 0:
        raise StagedFilesUnavailableError(
            f"git diff --cached a rendu {r.returncode} : {r.stderr.strip() or 'sans message'}")
    champs = [c for c in r.stdout.split("\0") if c]
    mutations: list[StagedMutation] = []
    i = 0
    while i < len(champs):
        statut = champs[i]
        # R et C portent un score de similarite accole : R100, C75.
        if statut[:1] in ("R", "C"):
            if i + 2 >= len(champs):
                raise StagedFilesUnavailableError(
                    f"statut {statut} sans ses deux chemins dans la sortie de git diff")
            mutations.append(StagedMutation(statut, champs[i + 1], champs[i + 2]))
            i += 3
            continue
        if i + 1 >= len(champs):
            raise StagedFilesUnavailableError(
                f"statut {statut} sans chemin dans la sortie de git diff")
        chemin = champs[i + 1]
        ancien = chemin if statut[:1] == "D" else None
        nouveau = None if statut[:1] == "D" else chemin
        mutations.append(StagedMutation(statut, ancien, nouveau))
        i += 2
    return mutations


def get_staged_files(repo: Path | None = None) -> list[str]:
    """Tous les chemins que le commit indexe touche, les deux cotes d'un renommage compris.

    Les modifications hors index ne comptent pas : elles appartiennent souvent a un autre
    agent qui travaille en parallele.

    Leve `StagedFilesUnavailableError` si l'enumeration echoue.
    """
    vus: list[str] = []
    for mutation in get_staged_mutations(repo):
        for chemin in mutation.chemins:
            if chemin not in vus:
                vus.append(chemin)
    return vus


def run_check(prompt_path: str | Path, staged: list[str]) -> tuple[int, list[str], str]:
    """Rend (code de sortie, fichiers hors perimetre, niveau d'extraction).

    Aucun perimetre declare rend 2 et non 0 : un prompt sans perimetre n'est pas un
    prompt qui autorise tout, c'est un prompt qu'on ne peut pas verifier.
    """
    patterns, niveau = extract_scope_patterns(prompt_path)
    if not patterns:
        return EXIT_SANS_PERIMETRE, [], niveau
    interdits = extract_forbidden_patterns(prompt_path)
    hors = [f for f in staged
            if not file_matches_scope(f, patterns) or file_matches_scope(f, interdits)]
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
