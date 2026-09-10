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

# Mots qui commencent une phrase ou un titre et ne sont pas des noms propres.
BANALS = {"The", "A", "An", "In", "It", "Since", "Then", "Built", "How", "What", "Stated",
          "Seven", "Outside", "Technical", "Delivery", "Contributed", "Dedicated", "Server",
          "Access", "Enterprise", "Hybrid", "Designed", "Systems", "Ten", "Native", "French",
          "English", "Professional", "Other", "Skills", "Languages", "Certifications", "Summary",
          "Applied", "Platforms", "Deployed", "Median", "Sustained", "Behaviour", "Recovery", "Le", "La", "Les", "Un", "Une", "Des", "Ce", "Cela", "Depuis",
          "Puis", "Support", "Conduite", "Construction", "Contribution", "Propriétaire", "Sept",
          "Hors", "Recherche", "Contrôle", "Connecteurs", "Chaîne", "Comment", "Dit", "Ingénieur",
          "Nantes", "Compétences", "Certifications", "Langues", "Expérience", "Autres", "Harnais",
          # Noms propres du domaine et identite de l'auteur : a renseigner par l'appelant,
          # via --banals, plutot qu'a coder en dur. Les trois ci-dessous sont un exemple.
          "Ariane", "Alex", "Doe",
          # ouvertures de phrase et de lettre : ce ne sont pas des faits
          "Hello", "Bonjour", "Here", "Before", "Your", "Votre", "That", "Those", "There",
          "After", "About", "With", "For", "You", "Two", "One", "Three", "Deux", "Trois",
          "Sur", "Sept", "Huit", "Mon", "Ma", "Je", "Il", "Elle", "Nous", "Vous", "Cette",
          "Bien", "Sans", "Avant", "Quand", "Aujourd"}


def charger_banals(argv) -> set:
    """Mots supplementaires a ne pas traiter comme des noms propres.

    Usage : --banals "Ariane,Alex,Doe" ou --banals fichier.txt (un mot par ligne).
    Sans l'option, seule la liste BANALS ci-dessus s'applique.
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


def nombres(t: str) -> set:
    """Nombres, espaces fines et virgules de milliers normalisées."""
    bruts = re.findall(r"\d[\d  .,]*\d|\d", t)
    return {re.sub(r"[  .,]", "", n) for n in bruts}


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
    nb = nombres(v) - nombres(s)
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
