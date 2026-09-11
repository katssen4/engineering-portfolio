#!/usr/bin/env python3
"""Porte anti-invention : une variante ne doit contenir aucun fait absent de son socle.

Dette D1 de `.pilot/STATE.md`. Le contrôle est mécanique et volontairement grossier : il compare
les **nombres** et les **noms propres** du texte visible de la variante à ceux du socle. Il ne
prouve pas qu'une variante est vraie, il prouve qu'elle n'a rien introduit que le socle n'ait déjà.
Un nombre ou un nom en plus est un signalement, pas forcément une faute : il faut alors qu'un
humain tranche, ou que le socle soit amendé par décision.

**Cas des lettres de motivation.** Une lettre se contrôle contre la **table de preuves**, pas
contre le socle : le socle est une sélection propre au CV, et il peut avoir retiré un fait qui
reste vrai. Exemple vécu le 2026-09-10 : la rubrique Harnais a quitté le CV, et « HMAC-SHA256 »
est aussitôt devenu orphelin dans trois lettres alors que P-048 le prouve toujours. Le socle
reste employé ici comme approximation commode ; quand il signale, on vérifie dans la table.

Usage : python3 verifier_variante.py <socle.md> <variante.md>
"""

import re
import sys
from decimal import Decimal, InvalidOperation

# Mots structurels : ouvertures de phrase, de titre et de lettre. Ce ne sont pas des noms
# propres, et ils ne dependent d'aucun dossier.
#
# Un mot echappe au signalement pour deux raisons tres differentes : parce qu'il est
# grammatical, ou parce que le fait qu'il nomme est autorise par le contexte. Fusionner les
# deux categories dans une seule liste globale rend la porte aveugle : « Nantes » et
# « Ariane » y figuraient en dur, donc une variante annoncant « Based in Nantes » alors que
# le socle ne porte aucune localisation passait sans un mot. Le README promet pourtant que
# les elements personnels sont devenus des parametres. Trouve par une revue le 2026-09-11.
#
# Les faits, les lieux, les noms de produit, d'entreprise et de personne entrent
# exclusivement par `--banals`, quand l'appelant declare qu'ils sont autorises.
BANALS = {"The", "A", "An", "In", "It", "Since", "Then", "Built", "How", "What", "Stated",
          "Seven", "Outside", "Technical", "Delivery", "Contributed", "Dedicated", "Server",
          "Access", "Enterprise", "Hybrid", "Designed", "Systems", "Ten", "Native", "French",
          "English", "Professional", "Other", "Skills", "Languages", "Certifications", "Summary",
          "Applied", "Platforms", "Deployed", "Median", "Sustained", "Behaviour", "Recovery", "Le", "La", "Les", "Un", "Une", "Des", "Ce", "Cela", "Depuis",
          "Puis", "Support", "Conduite", "Construction", "Contribution", "Propriétaire", "Sept",
          "Hors", "Recherche", "Contrôle", "Connecteurs", "Chaîne", "Comment", "Dit", "Ingénieur",
          "Compétences", "Certifications", "Langues", "Expérience", "Autres", "Harnais",
          # ouvertures de phrase et de lettre : ce ne sont pas des faits
          "Hello", "Bonjour", "Here", "Before", "Your", "Votre", "That", "Those", "There",
          "After", "About", "With", "For", "You", "Two", "One", "Three", "Deux", "Trois",
          "Sur", "Sept", "Huit", "Mon", "Ma", "Je", "Il", "Elle", "Nous", "Vous", "Cette",
          "Bien", "Sans", "Avant", "Quand", "Aujourd"}


def charger_banals(argv) -> set:
    """Mots supplementaires a ne pas traiter comme des noms propres.

    C'est par ici qu'entrent les noms propres du dossier : lieu, produit, entreprise,
    identite de l'auteur. Ils ne sont pas codes en dur, sinon la porte cesse de voir une
    localisation ou un nom de produit inventes.

    Usage : --banals "Ariane,Alex,Doe" ou --banals fichier.txt (un mot par ligne).
    Sans l'option, seule la liste structurelle BANALS ci-dessus s'applique.
    """
    if "--banals" not in argv:
        return set()
    v = argv[argv.index("--banals") + 1]
    try:
        return {m.strip() for m in open(v, encoding="utf-8").read().split() if m.strip()}
    except OSError:
        return {m.strip() for m in v.split(",") if m.strip()}


def visible(chemin: str) -> str:
    t = open(chemin, encoding="utf-8").read()
    t = re.sub(r"<!--.*?-->", "", t, flags=re.DOTALL)
    return re.sub(r"<!--.*\Z", "", t, flags=re.DOTALL)


# Unites reconnues comme faisant partie du nombre. Liste fermee : « 5 MB » et « 5 GB »
# doivent differer, mais « 48000 events » ne doit pas capturer « even » comme unite.
UNITES = ("%", "B", "KB", "MB", "GB", "TB", "KiB", "MiB", "GiB",
          "TiB", "ms", "s", "min", "h", "j", "€", "$", "£")

# Multiplicateurs colles au nombre : « 48k » vaut 48000. Reconnus seulement quand rien
# ne suit, pour que « 5 MB » reste une unite et non 5 millions de B.
MULTIPLICATEURS = {"k": 1000, "K": 1000, "M": 10**6, "G": 10**9, "T": 10**12}

# Multiplicateurs en toutes lettres, francais et anglais. Sans eux, « 312M » et
# « 312 million » donnaient deux cles differentes : faux positif releve en revue.
MOTS_MULTIPLICATEURS = {
    "thousand": 1000, "thousands": 1000, "millier": 1000, "milliers": 1000,
    "million": 10**6, "millions": 10**6,
    "billion": 10**9, "billions": 10**9, "milliard": 10**9, "milliards": 10**9,
}
_UNITE = "|".join(sorted((re.escape(u) for u in UNITES), key=len, reverse=True))
_MILLIERS = re.compile(r"^\d{1,3}(?:[\u202f\u00a0 .,]\d{3})+$")
_DECIMAL = re.compile(r"^\d+[.,]\d+$")
# Les devises s'ecrivent devant le nombre en anglais, derriere en francais. Sans le
# prefixe, « $5 » et « €5 » se normalisaient tous deux en « 5 » : la porte ne voyait plus la
# difference entre un montant en dollars et le meme chiffre en euros. Releve le 2026-09-11.
_DEVISE_PREFIXE = r"[$£€¥]"
_NOMBRE = re.compile(
    r"(?P<devise>" + _DEVISE_PREFIXE + r")?"
    r"(?P<signe>[-+\u2212])?"
    r"(?P<corps>\d[\d\u202f\u00a0 .,]*\d|\d)"
    r"(?:\s(?P<motmult>" + "|".join(sorted(MOTS_MULTIPLICATEURS, key=len, reverse=True)) + r")\b"
    r"|(?P<mult>[kKMGT])(?![\w])|\s?(?P<unite>" + _UNITE + r"))?(?![\w.,])")


_DEVISE_UNITE = {"$": "USD", "£": "GBP", "€": "EUR", "¥": "JPY",
                 "USD": "USD", "GBP": "GBP", "EUR": "EUR", "JPY": "JPY"}


def _canonique(signe: str, corps: str, unite: str, mult: str = "",
               motmult: str = "", devise: str = "") -> str:
    """Une ecriture par valeur, pour que « 90,000 » et « 90000 » se confondent et que
    « 5.0 » et « 50 » ne se confondent pas.

    Trois formes de corps sont distinguees au lieu d'une seule : les groupes de milliers,
    ou tous les separateurs tombent ; le decimal, ramene a sa valeur numerique ; et le reste,
    laisse tel quel. Le signe et l'unite entrent dans la cle, donc « -10 » differe de « 10 »
    et « 5 MB » differe de « 5 GB ».
    """
    if _MILLIERS.match(corps):
        brut = re.sub(r"[\u202f\u00a0 .,]", "", corps)
    elif _DECIMAL.match(corps):
        brut = corps.replace(",", ".")
    else:
        brut = re.sub(r"[\u202f\u00a0 ]", "", corps)
    try:
        # Decimal et non float : un identifiant de vingt chiffres ne doit pas perdre
        # de precision. normalize() rend « 5.0 » et « 5 » a la meme cle.
        d = Decimal(brut)
        if mult:
            d *= MULTIPLICATEURS[mult]
        elif motmult:
            d *= MOTS_MULTIPLICATEURS[motmult.lower()]
        valeur = str(d.normalize())
    except InvalidOperation:
        valeur = brut
    signe = "-" if signe in ("-", "\u2212") else ""
    # Une devise en prefixe entre dans la cle au meme titre qu'une unite en suffixe, et sous
    # le meme nom : « $5 » et « 5 USD » designent la meme chose, « $5 » et « €5 » non.
    suffixe = _DEVISE_UNITE.get(unite or "", unite or "")
    if devise:
        prefixe = _DEVISE_UNITE[devise]
        if suffixe and suffixe != prefixe:
            return signe + valeur + prefixe + suffixe
        suffixe = prefixe
    return signe + valeur + suffixe


def nombres(t: str) -> dict:
    """Jetons numeriques, une cle par valeur.

    Ce que la cle retient : le signe, la valeur, l'unite quand elle est dans la liste fermee
    ci-dessus. Ce qu'elle ne retient pas : la forme d'ecriture des milliers. Les limites
    connues de cette normalisation sont livrees dans `tests/test_anti_invention.py`.
    """
    cles = {}
    for m in _NOMBRE.finditer(t):
        cle = _canonique(m.group("signe"), m.group("corps"), m.group("unite"),
                         m.group("mult") or "", m.group("motmult") or "",
                         m.group("devise") or "")
        cles.setdefault(cle, m.group(0).strip())
    return cles


def sans_titre(t: str) -> str:
    """Retire la ligne de titre de poste : c'est la zone variable Z1, elle diffère par nature."""
    lignes = t.split("\n")
    return "\n".join(l for i, l in enumerate(lignes)
                     if not (i < 8 and (l.startswith("## ") or re.fullmatch(r"\*\*.+\*\*", l.strip()))))


def noms(t: str) -> set:
    """Noms propres, comparés en minuscules : une capitale de début de puce n'est pas un fait."""
    mots = re.findall(r"\b[A-ZÉÈÀÇ][\wéèêàçôûîï.-]{2,}\b", t)
    return {m.lower() for m in mots if m not in BANALS}


if __name__ == "__main__":
    argv = sys.argv[1:]
    BANALS |= charger_banals(argv)
    positionnels = [a for a in argv if not a.startswith("--")]
    if "--banals" in argv:
        positionnels = [a for a in positionnels if a != argv[argv.index("--banals") + 1]]
    if len(positionnels) < 2:
        sys.exit("usage: anti_invention.py <source_de_verite.md> <derive.md> [--banals mots|fichier]")
    s, v = sans_titre(visible(positionnels[0])), sans_titre(visible(positionnels[1]))
    nv, ns = nombres(v), nombres(s)
    # On compare des cles canoniques, on affiche le texte reellement lu : « 9E+4 » est
    # une bonne cle et un mauvais message.
    nb = {nv[c] for c in nv.keys() - ns.keys()}
    # un nom est absent seulement s'il ne figure nulle part dans le socle, casse comprise
    bas = s.lower()
    nm = {n for n in noms(v) - noms(s) if n not in bas}
    nom_variante = positionnels[1].split("/")[-1]
    if not nb and not nm:
        print(f"OK      {nom_variante} : aucun nombre ni nom propre absent du socle")
        sys.exit(0)
    print(f"SIGNAL  {nom_variante}")
    if nb:
        print(f"        nombres absents du socle : {', '.join(sorted(nb))}")
    if nm:
        print(f"        noms absents du socle    : {', '.join(sorted(nm))}")
    sys.exit(1)
