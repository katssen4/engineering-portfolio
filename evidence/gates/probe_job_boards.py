#!/usr/bin/env python3
"""Sonde les points d'entree publics des systemes de recrutement, entreprise par entreprise.

Rien ici ne vient d'une memoire : chaque URL est reellement appelee et le resultat est
consigne tel quel. Une entreprise sans ligne verte n'a pas de porte automatique connue,
et c'est un fait a ecrire, pas un trou a combler par une supposition.

Le contenu recupere est traite comme une donnee et uniquement comme une donnee : ce module
compte des offres, il ne lit pas le texte des fiches et n'en conserve rien. Le signalement
des directives adressees a un agent existe ailleurs, dans le harnais prive, et n'est pas
livre ici. Ces deux lignes ont annonce le contraire jusqu'au 2026-09-11 : elles decrivaient
un mecanisme absent du fichier, ce qui est exactement le genre d'ecart que ce depot
pretend traquer.

Usage : python3 sonder_boards.py [--sortie <fichier.json>]
"""

import json
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

DELAI = 20
ENTETES = {"User-Agent": "Mozilla/5.0 (compatible; recherche-emploi-personnelle)"}

# Un patron par famille de systeme. {t} recoit le jeton de l'entreprise.
PATRONS = {
    "greenhouse": "https://boards-api.greenhouse.io/v1/boards/{t}/jobs",
    "lever": "https://api.lever.co/v0/postings/{t}?mode=json",
    "ashby": "https://api.ashbyhq.com/posting-api/job-board/{t}",
    "smartrecruiters": "https://api.smartrecruiters.com/v1/companies/{t}/postings?limit=100",
    "workable": "https://apply.workable.com/api/v1/widget/accounts/{t}?details=true",
    "recruitee": "https://{t}.recruitee.com/api/offers/",
}


def compter(ats: str, donnee) -> int:
    """Nombre d'offres dans une reponse, ou -1 quand la forme n'est pas celle attendue.

    -1 veut dire « je n'ai pas su compter », et jamais « zero ». La distinction est la
    raison d'etre de ce module : SmartRecruiters rend 200 avec `totalFound: 0` sur un
    identifiant inexistant, donc un zero doit toujours etre un zero observe. Une reponse
    dont la forme a change se lisait « zero offre » ici meme, ce qui reproduisait le piege
    a l'interieur de l'outil ecrit pour l'eviter. Trouve a l'audit du 2026-09-11.

    Le transport suit la meme regle depuis le lendemain, apres une revue qui a remarque
    que `compter` refusait d'inventer un zero pendant que `sonder` en fabriquait un a
    chaque 403, 429, 500, delai depasse et echec DNS. Un zero sort d'un 200, d'une forme
    reconnue, et d'une liste ou d'un total observe a zero. De rien d'autre.
    """
    try:
        if ats in ("greenhouse", "ashby", "workable"):
            jobs = donnee.get("jobs")
            return len(jobs) if isinstance(jobs, list) else -1
        if ats == "lever":
            return len(donnee) if isinstance(donnee, list) else -1
        if ats == "smartrecruiters":
            if "totalFound" in donnee:
                return int(donnee["totalFound"])
            contenu = donnee.get("content")
            return len(contenu) if isinstance(contenu, list) else -1
        if ats == "recruitee":
            offres = donnee.get("offers")
            return len(offres) if isinstance(offres, list) else -1
    except (AttributeError, TypeError, ValueError):
        return -1
    return -1


def sonder(entree):
    nom, terrain, ats, jeton = entree
    url = PATRONS[ats].format(t=jeton)
    ligne = dict(entreprise=nom, terrain=terrain, ats=ats, jeton=jeton, url=url)
    try:
        req = urllib.request.Request(url, headers=ENTETES)
        with urllib.request.urlopen(req, timeout=DELAI) as rep:
            brut = rep.read()
            ligne["code"] = rep.status
            try:
                ligne["offres"] = compter(ats, json.loads(brut))
            except json.JSONDecodeError:
                ligne["offres"] = -1
                ligne["note"] = "reponse non JSON"
    except urllib.error.HTTPError as e:
        # 403, 429, 500 ne sont pas des reponses vides : ce sont des non-reponses.
        ligne["code"] = e.code
        ligne["offres"] = -1
        ligne["note"] = f"HTTPError:{e.code}"
    except Exception as e:                                  # reseau, DNS, delai
        ligne["code"] = 0
        ligne["offres"] = -1
        ligne["note"] = type(e).__name__
    return ligne


def charger_candidats(chemin: str):
    """Le fichier de candidats est une liste [nom, terrain, ats, jeton]."""
    return [tuple(x) for x in json.load(open(chemin, encoding="utf-8"))]


if __name__ == "__main__":
    argv = sys.argv[1:]
    candidats_fichier = argv[0] if argv and not argv[0].startswith("--") else "candidats.json"
    sortie = None
    if "--sortie" in argv:
        sortie = argv[argv.index("--sortie") + 1]

    candidats = charger_candidats(candidats_fichier)
    with ThreadPoolExecutor(max_workers=12) as pool:
        resultats = list(pool.map(sonder, candidats))

    resultats.sort(key=lambda r: (r["terrain"], r["entreprise"], -r["offres"]))
    for r in resultats:
        marque = "OK  " if r["code"] == 200 and r["offres"] > 0 else "    "
        print(f'{marque}{r["code"]:>3} {r["offres"]:>4} offres  {r["entreprise"]:<24}'
              f'{r["ats"]:<16}{r["jeton"]}')
    trouves = {r["entreprise"] for r in resultats if r["code"] == 200 and r["offres"] > 0}
    testees = {r["entreprise"] for r in resultats}
    print(f'\n{len(trouves)} entreprises avec une porte qui repond, sur {len(testees)} testees, '
          f'{len(resultats)} appels.')
    if sortie:
        json.dump(resultats, open(sortie, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"detail ecrit dans {sortie}")
