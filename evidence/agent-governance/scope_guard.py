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

# Les memes, mais comme marqueurs d'interdiction : ceux-la nomment une intention, et une
# intention reconnue que la grammaire ne sait pas placer doit refuser, pas disparaitre.
_MARQUEURS_INTERDICTION = ("HORS SCOPE", "INTERDIT", "EXCLUS", "FORBIDDEN", "READ-ONLY",
                           "READ ONLY", "LECTURE SEULE", "NE PAS TOUCHER", "DO NOT")


def _est_marqueur_interdiction(ligne: str) -> bool:
    """Vrai si la ligne annonce une interdiction, titre Markdown compris."""
    nue = ligne.lstrip("#*-+ ").strip().upper()
    return any(nue.startswith(kw) for kw in _MARQUEURS_INTERDICTION)

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
    """Contenu de l'unique bloc <scope>...</scope>. Leve si le prompt en porte plusieurs.

    Un seul comptage, et il est canonique. Le comptage precedent se faisait en deux passes :
    d'abord les blocs en debut de ligne et sensibles a la casse, et seulement si cette passe
    ne trouvait rien, les blocs en ligne et insensibles a la casse. Un prompt portant
    `<scope>` puis `<SCOPE>` sortait donc de la premiere passe avec un seul bloc trouve, et
    le second n'etait jamais compte : l'ambiguite que le garde promet de refuser passait a
    cause de la casse. Releve le 2026-09-11.

    La propriete doit etre independante de la casse, de la mise en forme et du caractere
    en ligne ou multiligne, puisque chacune de ces variantes est acceptee isolement.
    """
    blocs = list(re.finditer(r"<scope\b[^>]*>(.*?)</scope\s*>", content,
                             re.DOTALL | re.IGNORECASE))
    if len(blocs) > 1:
        raise PerimetreAmbiguError(f"{len(blocs)} blocs <scope> dans le prompt")
    if blocs:
        return blocs[0].group(1)
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


class InterdictionNonStructureeError(RuntimeError):
    """Le perimetre nomme une interdiction dans une forme que la grammaire ne porte pas.

    La grammaire structuree a une seule facon d'ecrire une interdiction, la balise
    `<interdit>`. Un prompt qui ecrit `## Interdit` a cote d'une section `<écriture>`, ou
    `INTERDIT :` a l'interieur de celle-ci, exprime la meme intention dans une forme que le
    garde ne sait pas rattacher. Elle etait alors simplement sautee, ce qui produisait deux
    resultats et les deux sont mauvais : l'interdiction disparaissait, et dans le second cas
    les chemins qui la suivaient devenaient des autorisations d'ecriture.

    C'est le cas que le docstring de ce module decrit comme le plus tenace du garde en
    service, dix recidives sur six sessions. Il etait ferme pour l'ancien format en meme
    temps que la liste blanche, et restait ouvert a l'interieur de la grammaire structuree.
    Trouve le 2026-09-11 en instruisant une revue qui signalait le premier des deux cas.

    Une intention reconnue et non placable refuse. Le prompt se reecrit avec `<interdit>`.
    """


class CheminAmbiguError(RuntimeError):
    """Une ligne de perimetre ne dit pas sans ambiguite ou finit le chemin.

    Le decoupage precedent coupait la ligne au premier espace. `docs/my file.md` devenait
    donc la permission `docs/my`, qui est un **prefixe plus large** que ce que le prompt
    accordait : `docs/my/secret.txt` et tout son sous-arbre passaient, alors que le prompt
    n'avait donne qu'un fichier. Une ambiguite d'analyse se resolvait en elargissement de
    privilege, ce qui est l'inverse de ce qu'un garde doit faire. Releve le 2026-09-11.
    """


def _chemin_de_ligne(ligne: str) -> str | None:
    """Le chemin d'une ligne de puce, ou None si la ligne n'en porte pas.

    Trois formes, dans cet ordre, et rien d'autre :

    1. entre accents graves, `docs/my file.md`, et alors les espaces appartiennent au
       chemin, c'est la seule facon de declarer un chemin qui en contient ;
    2. nu, suivi d'un commentaire entre parentheses, `src/foo/ (le connecteur)`, ou le
       commentaire tombe ;
    3. nu, sans espace du tout.

    Toute autre ligne leve `CheminAmbiguError`. Un chemin nu contenant un espace n'est pas
    tronque : le garde ne sait pas ou il finit, donc il refuse tout le perimetre.
    """
    if (m := re.fullmatch(r"`([^`]+)`(?:\s+.*)?", ligne)):
        return m.group(1).strip()
    tete, _, reste = ligne.partition(" ")
    if reste and not reste.lstrip().startswith("("):
        raise CheminAmbiguError(
            f"« {ligne} » : espace dans un chemin non encadre par des accents graves. "
            f"Ecrire `{ligne}` si l'espace fait partie du chemin.")
    return tete.strip("`").strip() or None


def _parse_path_patterns(section: str, *, section_ecriture: bool = False) -> list[str]:
    """Chemins d'une section a puces. Une ligne sans `/` ni `.` n'est pas un chemin.

    Leve `CheminAmbiguError` sur une ligne dont le chemin n'a pas de fin determinable, et
    `InterdictionNonStructureeError` sur un marqueur d'interdiction trouve dans une section
    d'ecriture, ou il n'a aucun sens que le garde puisse appliquer.
    """
    patterns: list[str] = []
    for raw in section.splitlines():
        ligne = raw.strip()
        if not ligne or (ligne.startswith("#") and not section_ecriture):
            continue
        if _est_marqueur_interdiction(ligne):
            if section_ecriture:
                raise InterdictionNonStructureeError(
                    f"« {ligne} » dans la section d'ecriture : une interdiction s'ecrit "
                    f"<interdit>, sinon les chemins qui la suivent deviennent des "
                    f"autorisations.")
            continue
        if ligne.startswith("#"):
            continue
        if ligne[:2] in ("- ", "* ", "+ "):
            ligne = ligne[2:].strip()
        chemin = _chemin_de_ligne(ligne)
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
    try:
        return [c for _, corps in sections for c in _parse_path_patterns(corps)]
    except CheminAmbiguError:
        # Une interdiction illisible ne s'evapore pas : `extract_scope_patterns` refuse
        # le perimetre entier sur la meme ligne, et le commit ne passera pas.
        return []


def _refuser_interdiction_hors_grammaire(bloc: str, section_ecriture: str) -> None:
    """Leve si le bloc nomme une interdiction ailleurs que dans une balise <interdit>.

    On retire du bloc les sections XML, qui ont leur grammaire, ainsi que la section
    d'ecriture deja parsee. Ce qui reste est du texte libre : un `## Interdit` qui s'y
    trouve exprime une intention que le garde ne sait pas appliquer, et la sauter revient
    a accorder l'ecriture large qui est declaree juste au-dessus.
    """
    reste = re.sub(r"<([A-Za-zÉéÈèÀàÇç][\w-]*)\b[^>]*>.*?</\1\s*>", "", bloc,
                   flags=re.DOTALL | re.IGNORECASE)
    reste = reste.replace(section_ecriture, "")
    for ligne in reste.splitlines():
        ligne = ligne.strip()
        if ligne and _est_marqueur_interdiction(ligne):
            raise InterdictionNonStructureeError(
                f"« {ligne} » hors de toute balise : une interdiction s'ecrit <interdit>.")


def extract_scope_patterns(prompt_path: str | Path) -> tuple[list[str], str]:
    """Rend (chemins autorises, niveau d'extraction). Liste vide = aucun perimetre.

    Aucune exception ne sort d'ici : une ligne illisible rend une liste vide et un niveau
    qui la nomme, donc un code 2. Une trace Python sortirait avant la premiere ligne de
    resultat et se lirait comme un silence, ce qui est le defaut que l'audit interne du
    2026-09-11 a trouve dans le verificateur.
    """
    contenu = Path(prompt_path).read_text(encoding="utf-8")
    try:
        bloc = _extract_scope_block(contenu)
    except PerimetreAmbiguError:
        return [], "perimetre-ambigu"
    if bloc is None:
        return [], "no-scope"
    try:
        section = _extract_xml_writing_section(bloc)
        niveau = "xml-strict"
        if section is None:
            section = _extract_regex_writing_section(bloc)
            niveau = "xml-regex"
        if section is not None:
            patterns = _parse_path_patterns(section, section_ecriture=True)
            _refuser_interdiction_hors_grammaire(bloc, section)
            return patterns, niveau
    except CheminAmbiguError:
        return [], "chemin-ambigu"
    except InterdictionNonStructureeError:
        return [], "interdiction-hors-grammaire"
    # Le repli sur le bloc entier ne s'applique QUE si le bloc n'est pas structure du tout.
    # Des qu'une section connue apparait, lire le bloc entier reviendrait a promouvoir les
    # chemins de <lecture> et de <interdit> en autorisations d'ecriture. Une revue exterieure
    # a montre le 2026-09-11 qu'un scope portant <lecture> et <interdit> sans <écriture>
    # passait par ce chemin : `src/auth/` devenait ecrivable alors qu'il etait en lecture.
    if re.search(r"<[ÉéEe]criture", bloc, re.IGNORECASE):
        return [], "ecriture-illisible"
    if re.search(_SECTIONS_CONNUES, bloc, re.IGNORECASE):
        return [], "scope-structure-sans-section-ecriture"
    try:
        direct = _patterns_ancien_format_stricts(bloc)
    except CheminAmbiguError:
        return [], "chemin-ambigu"
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
    """Trois formes de permission, distinguees par leur ecriture et non devinees.

        `src/foo/`          repertoire, recursif        -> src/foo/ et tout ce qu'il contient
        `reports/*.json`    motif, borne au segment     -> reports/a.json, pas reports/x/a.json
        `config/s.json`     chemin exact, et rien d'autre

    La troisieme forme est la correction du 2026-09-11. Un motif sans barre finale etait
    traite a la fois comme un fichier et comme un repertoire : `config/settings.json`
    autorisait `config/settings.json/evil.py`, puisque le chemin commence bien par
    `config/settings.json/`. Rien n'interdit a un repertoire de s'appeler `settings.json`,
    et une permission de fichier devenait donc une permission de sous-arbre.

    Une meme chaine ne peut pas signifier deux choses dans une porte de permission. Un
    repertoire s'ecrit avec sa barre finale ; sans elle, la permission porte sur ce chemin
    et sur lui seul.
    """
    for pattern in patterns:
        if pattern.endswith("/"):
            repertoire = pattern.rstrip("/")
            if filepath == repertoire or filepath.startswith(repertoire + "/"):
                return True
            continue
        if _PLACEHOLDER_PATTERN.search(pattern) or any(c in pattern for c in "*?"):
            motif = _regex_de_motif(pattern)
            if motif.fullmatch(filepath) or motif.fullmatch(filepath.split("/")[0]):
                return True
            continue
        if filepath == pattern:
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
