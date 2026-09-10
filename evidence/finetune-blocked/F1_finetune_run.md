# F1 — Fine-tuning en domaine de l'encodeur en place (ADR-0012) — **ARRÊT SUR CONTRÔLE F7**

> **Ce qui est mesuré ici, et ce que cela ne vaut pas.** L'expérience porte sur **GitBugs**
> (collection B) : des rapports de bogues **en anglais**, tirés de dépôts GitHub. **Le chiffre est
> jetable par construction ; seule la méthode se transporte.** Ce lot n'établit **rien** sur le
> français, **rien** sur les tickets ITSM, **rien** sur la collection A et **rien** sur la réserve
> « porté par Cassandra » qui accompagne le moteur en place. C'est le cadrage de l'ADR-0012 dans son
> paragraphe d'ouverture, pas une note de bas de page ajoutée après coup.

**Lot :** `S28_F1_RESUME` (reprise de `S28_F1_RUN`) · **Spécification :** ADR-0012, *Accepted* (opérateur, S27)
**Date :** 2026-09-04 · **Statut :** `fail` — **branche d'arrêt `F7` (contrôle positif manqué)**

---

## 1. Le résultat en une phrase

**Le contrôle positif F7 a échoué : le modèle de base non fine-tuné, repassé dans le même pilote sur
le même jeu réservé scellé (n = 310), donne nDCG@10 = 0,575258 là où l'ADR exige la reproduction de
0,576448 à 6 décimales.** L'ADR-0012 F7 fait de ce manquement un **arrêt dur** : le bras est
**bloqué**, **le primaire n'a jamais été calculé**, aucun verdict n'est émis, aucun chiffre du bras
n'est interprété. **Il n'existe donc dans ce rapport ni Δ, ni p, ni intervalle de confiance, ni
d_z, ni cellules par projet** — non pas parce qu'ils sont omis, mais parce qu'ils n'ont pas été
produits. C'est le comportement pré-enregistré, pas un incident.

| | valeur |
|---|---|
| contrôle F7 calculé (base non fine-tuné, n = 310) | **0,575258** |
| cible F7 inscrite dans l'ADR | **0,576448** |
| écart | **−0,001190** |
| tolérance | 5e−07 (« à 6 décimales ») |
| verdict | **aucun — non émis** |
| bras fine-tuné évalué ? | **non** |
| supersede revendiqué ? | **non** (et il ne pourrait pas l'être : cf. § 7) |

---

## 2. Ce que le manquement est, exactement — un seul enregistrement, et une égalité de score

Le diagnostic est net et il ne laisse pas de place à l'interprétation.

Sur les 310 requêtes du jeu réservé, comparées une à une au substrat par requête de l'ADR
(`bench/runs/S18_ladder_perquery.jsonl`, bras `qwen3-0.6B`, collection B) :

- **79 requêtes** diffèrent de **≤ 4,9e−06** — c'est l'arrondi à 5 décimales du fichier S18
  lui-même, somme totale **−0,000036**. Ce n'est pas une dérive, c'est la précision d'écriture du
  substrat de référence.
- **1 seule requête** diffère matériellement : **`cassandra:13318333`**, qui passe de **1,000000**
  (enregistré en S18) à **0,630930** aujourd'hui, soit **−0,369070**.
- **−0,369070 / 310 = −0,001191.** **La totalité de l'écart du contrôle tient dans cette unique
  requête.** Les 309 autres reproduisent le substrat à la précision d'écriture près.

### La mécanique : une égalité de score exacte, et deux mesures qui la tranchent différemment

Dans le run de base, les deux premiers candidats de cette requête portent **le même score, au bit
près** :

```
cassandra:13318333 Q0 cassandra:13454590 0 0.816895 qwen3_06b_base   ← non pertinent
cassandra:13318333 Q0 cassandra:13309944 1 0.816895 qwen3_06b_base   ← LE positif des qrels
```

Le document pertinent (`cassandra:13309944`, unique positif de cette requête dans les qrels) est
**à égalité parfaite** avec un document non pertinent. nDCG@10 pour un unique document pertinent
vaut 1,000000 au rang 1 et **0,630930 au rang 2** — c'est exactement la valeur observée.

**Et la preuve directe que c'est bien l'égalité qui décide, pas les vecteurs :** dans le *même appel*
à l'évaluateur, sur la *même* requête et le *même* run, on lit

```
cassandra:13318333 : RR@10 = 1,000000   nDCG@10 = 0,630930
```

**RR@10 place le pertinent au rang 1 ; nDCG@10 le place au rang 2.** Deux mesures du même
évaluateur, sur la même ligne, en désaccord : c'est la signature d'une égalité de score tranchée
selon des conventions différentes selon la mesure. Corollaire vérifié : **MRR@10 = 0,543614 et
R@100 = 0,873118 reproduisent le relevé S18 exactement**, parce que ces deux mesures-là sont
insensibles à cette égalité. **Une seule des trois agrégations ne reproduit pas, et c'est celle qui
dépend de l'ordre entre deux scores identiques.**

### Combien l'ancre F7 repose-t-elle sur des égalités ? — recensement

Sur les 310 requêtes du jeu réservé, dans le run de base :

| | nombre |
|---|---|
| requêtes présentant **au moins une égalité de score exacte** dans le top-10 | **82 / 310** |
| requêtes où un groupe d'égalité **mélange pertinent et non pertinent** (nDCG@10 fragile) | **5 / 310** |

Les cinq : `cassandra:13318333`, `cassandra:13481529`, `spark:13363491`, `spark:13381178`,
`spark:13547049`. **`cassandra:13318333` est l'une d'elles, et c'est celle qui a basculé.**

**Ce que cela dit, et qu'il faut dire prudemment : l'ancre 0,576448 n'est pas une quantité stable au
bit près.** Cinq de ses 310 requêtes ont une contribution décidée par la résolution d'une égalité
qui, elle, ne porte aucune information de recherche. Ce constat porte **sur l'ancre**, pas sur le
run d'aujourd'hui ni sur le modèle fine-tuné.

### Ce qui n'explique PAS le manquement — vérifié, pas supposé

- **Ce ne sont pas les plongements du corpus.** Le cache d'encodage de base de cassandra est
  **inchangé depuis le 2026-06-26** (`complete: true`, même `corpus_sha256`) — ce sont les octets
  qu'utilisait S18.
- **Ce n'est pas le pipeline.** 309 requêtes sur 310 reproduisent ; MRR@10 et R@100 reproduisent
  exactement ; les qrels du jeu réservé sont reconstruits par le code du dépôt (348 lignes, n = 310).
- **Ce n'est pas la reprise.** Le substrat du contrôle (`B_holdout_base_run.trec`) date de la
  **première fenêtre** (01:08) : il n'a **pas** été régénéré dans cette session. Le relancer aurait
  été un second tirage du contrôle ; il ne l'a pas été.

**[NON VÉRIFIÉ]** — le lieu numérique exact de la bascule (dernier bit de l'encodage des requêtes
sur ce pilote/GPU, instabilité de `np.argsort` sur valeurs égales, convention de départage de
l'évaluateur) n'est **pas** établi ici et n'est pas affirmé. La tension entre `RR@10 = 1,0` et
`nDCG@10 = 0,630930` sur la même requête est signalée telle quelle : elle mérite l'œil d'un
chercheur indépendant, pas une explication écrite d'avance par le même modèle.

---

## 3. Ce que le lot n'a PAS fait

C'est la partie qui doit être lue en premier par qui vérifie ce dossier.

- **Aucun ré-entraînement.** Les poids sont restés gelés. Leur sha256 sur disque,
  `08547d9a0b876138b572c22c8c2397c0cc45c24b880c1d34a3ea2bf755b134ba`, est **identique** à celui
  qu'avait enregistré le bloc `training`. L'instrument est intact au bit près.
- **Aucune re-fouille (mining), aucun re-passage de la porte F2.** Les deux sont enregistrés,
  horodatés **avant** le premier pas d'optimiseur, et n'ont pas été rejoués.
- **Aucun seuil relâché.** Ni le garde VRAM, ni la tolérance du contrôle F7.
- **Aucune valeur pré-enregistrée ajustée.**
- **Aucun runner existant modifié** (`ladder_run.py`, `compare.py`, `embedding_cache.py`, …) :
  `git diff` sur `bench/runners/` hors les deux fichiers du lot est vide.
- **Aucun calcul du primaire.** Le bras n'a jamais été noté. Le bloc `arm` du relevé de pile
  n'existe pas, et c'est correct : une phase qui n'a pas tourné n'a pas de bloc.
- **Aucune suppression.** Les caches partiels, les artefacts et le `.trec` partiel du bras ont été
  laissés en place (cf. `RESIDUE` dans la synthèse du lot).

---

## 4. Le run a été **interrompu puis repris** — une expérience, deux fenêtres

Ce dossier enregistre **une seule expérience exécutée en deux fenêtres**, pas deux expériences. Un
lecteur qui ignore l'interruption ne doit pas pouvoir être induit en erreur ; un lecteur qui la
connaît doit pouvoir vérifier que rien n'a été rejoué.

**L'interruption.** Le worker `S28_F1_RUN` a été **tué par l'opérateur le 2026-09-04 vers 01:26**,
**au milieu de l'encodage du bras**, sur le projet `spark`. Il n'a écrit ni signal ni commit.
L'ADR-0012 F8 pré-enregistre exactement ce cas (« *so a multi-window run survives a timeout and
resumes without re-training completed steps* ») : la reprise est un **chemin pré-enregistré**, pas
une décision prise en vol.

**Ce qui a été préservé, et non recalculé :**

| élément | état |
|---|---|
| poids fine-tunés | gelés, sha256 **revérifié et identique** |
| entraînement (22 pas d'optimiseur, 71,4 s) | non rejoué |
| fouille des négatifs + porte F2 | non rejouées, horodatées avant l'entraînement |
| run de base complet (substrat du contrôle F7) | 31 000 lignes, fenêtre 1, non régénéré |
| caches d'encodage du bras cassandra / hadoop / hbase | complets, réutilisés |

**Ce qui a été recalculé en fenêtre 2 :** le seul encodage `spark` du bras, **repris depuis son
cache partiel** (8 192 des 20 275 lignes étaient déjà faites), 481,1 s ; puis le fichier `.trec` du
bras réécrit en entier — le runner supprime son **propre** fichier de sortie avant écriture parce
que `write_trec` ajoute en fin de fichier ; c'est le comportement préexistant du runner sur sa
propre sortie, ce qui rend l'encodage idempotent, et non une suppression d'artefact.

**Contrôles refaits après la mise à mort, parce qu'une porte non retestée après un kill n'est plus
une porte :** garde `STOP-VRAM-ENCODE` (8 151 MiB libres contre un seuil de 1 600 → PASS), sha256 de
l'artefact (identique), et la suite de tests hors-GPU (**24 passés, 0 échec, 0,62 s**).

---

## 5. Les valeurs enregistrées avant le premier pas d'optimiseur

**Porte F2 (fuite) — précondition, horodatée `2026-09-03T23:04:31+00:00`, soit avant l'entraînement
horodaté `23:06:44` :**

| contrôle | valeur | exigence |
|---|---|---|
| 1. recouvrement `tuning ∩ holdout` | **0** | doit être 0 |
| 2. qids du jeu réservé présents comme extrémité de paire | **0** | doit être 0 |
| 3. clusters du jeu réservé touchés | **0** | doit être 0 |
| 4. couverture du côté tuning | **476 / 740** | reporté, ne conditionne rien |

→ `passed: true`. Aucune fuite. La porte a rempli son office **en tant que précondition**, ce qui est
la seule manière dont elle peut le remplir.

**VRAM mesurée (et non estimée) :**

| phase | pic mesuré | budget / seuil ADR F8 |
|---|---|---|
| entraînement | **5 863,5 MiB** | budget 6 000 MiB → sous le plafond |
| encodage (base et bras) | **3,314 GiB** ≈ 3 393 MiB | — |
| garde avant encodage, fenêtre 2 | **8 151 MiB libres** | seuil 1 600 MiB → PASS |

Le pic d'entraînement mesuré à 5 863,5 MiB contre un budget de 6 000 MiB laisse **136,5 MiB** de
marge : l'estimation de conception de l'ADR (« ≈3,2 GiB », explicitement `[UNVERIFIED]`) était
**optimiste d'environ 80 %**. C'est une donnée, pas un reproche : l'ADR F8 prévoyait précisément que
le run lise et enregistre la valeur réelle.

---

## 6. Réserves

Une réserve est un constat, pas une licence. Aucune n'a été appliquée comme une modification.

1. **L'ancre F7 contient une fragilité que l'ADR ne pouvait pas connaître au moment de la geler.**
   Cinq requêtes sur 310 ont un nDCG@10 décidé par une égalité de score exacte entre un document
   pertinent et un non pertinent. Une reproduction « à 6 décimales » d'une quantité qui contient de
   telles bascules est une exigence qui peut échouer **sans qu'aucun composant ne soit en faute**.
   L'ADR-0012 *Reserves* 4 anticipait cette classe d'échec (« *that class of control can fail for
   reasons nobody can recover* ») et a maintenu l'arrêt dur **délibérément**. **L'arrêt est appliqué
   tel quel.** Toute modification de F7 est un **amendement neuf, relu par un chercheur non-Claude,
   accepté par l'opérateur, dans cet ordre et jamais en vol** — ce n'est pas la décision de ce lot,
   et ce rapport ne la prend pas.
2. **Une différence par rapport au précédent S21 est consignée, sans en tirer de conclusion.** En
   S21 l'échec du contrôle était irrécupérable faute de relevé de pile. Ici la cause est **nommée et
   quantifiée**, et le substrat est intact. Que cela change ou non ce qu'un amendement devrait
   décider n'appartient pas à ce lot.
3. **`n_pairs_out = 346` pour `n_positive_pairs_in = 806`** : 425 requêtes ont été écartées faute de
   2 négatifs admissibles après les exclusions F3 (bande de rangs 10–50, exclusion du cluster, du
   côté tuning, des positifs). La couverture tuning tombe à 476/740. C'est le comportement
   pré-enregistré (« jamais complété par un document aléatoire »), appliqué tel quel — mais un
   entraînement de **22 pas d'optimiseur** sur 346 paires est un signal court, et cela mérite d'être
   su de quiconque lira un jour un résultat produit par cet artefact.
4. **La moyenne de perte monte** (20 premiers micro-lots 0,466898 → 20 derniers 0,814942). Sur 87
   micro-lots ce n'est pas interprétable comme une divergence, et **ce n'est pas interprété ici** :
   c'est consigné parce que le relevé de pile doit contenir ce qui a été observé.
5. **Avertissement `overflow encountered in cast` à `ladder_run.py:271`** (`sims[...] = -1e9` écrit
   dans un tableau fp16, donc saturé en `-inf`). Comportement préexistant du runner **non modifié**,
   identique sur le run de base et sur celui du bras, et l'auto-exclusion reste correcte (`-inf`
   exclut aussi bien que `-1e9`). Signalé, non corrigé : modifier un runner existant est interdit à
   ce lot.
6. **La contradiction `mean-pool` / `lasttoken` des ADR-0008 et ADR-0009 reste ouverte.** Ce lot
   écrit `lasttoken` (la configuration réelle du modèle) et ne modifie aucun ADR existant.

---

## 7. Ce que ce lot n'autorise pas

- **Aucun verdict n'a été émis** : il n'y a donc rien à promouvoir, rien à superséder, et aucun
  chiffre du bras à citer. `bench/runs/F1_decision.json` porte `"verdict": null` et
  `"status": "fail"`.
- **Le moteur en place ne bouge pas.** `bench/runs/baseline_lock.json` est resté **intact au
  octet près** (ADR F6.2), comme sous tout autre issue.
- **Sur le chercheur indépendant — correction d'un énoncé antérieur.** Le prompt de `S28_F1_RUN`
  demandait d'écrire que le backend de recherche non-Claude était **vide sur cette machine**. **Ce
  n'est plus vrai** : l'opérateur a installé `codex` en S28 (`codex-cli 0.153.1`), qui a exécuté un
  lot complet (`docs/audit/SOCLE_S27/AUD3_embedder_codex_verdict.md`). Ce qui reste inchangé :
  l'ADR F6.1 fait de toute VICTOIRE une **candidate seulement**, exigeant **et** un chercheur AUD-3
  non-Claude **et** le GO de l'opérateur — **aucun des deux n'est acquis par ce lot**. La question
  est de toute façon sans objet aujourd'hui : il n'y a pas de victoire, puisqu'il n'y a pas de
  mesure.
  **Précision opératoire vérifiée ici, et qui n'annule pas la correction ci-dessus.** Le binaire est
  bien présent (lien `~/.nvm/versions/node/v22.23.2/bin/codex`, posé le 2026-09-04 à 00:36) et son
  verdict est sur disque — l'installation est un fait. Mais **il n'est pas invocable depuis le shell
  non-interactif de ce worker** : `node` n'est pas dans le `PATH` ici (nvm non sourcé), et l'appel
  échoue sur `/usr/bin/env: 'node': No such file or directory`. Ce n'est **pas** une absence du
  chercheur, c'est une contrainte d'environnement de dispatch : qui lancera l'AUD-3 devra sourcer
  nvm ou appeler node explicitement. Consigné pour que personne ne relise cela comme « le chercheur
  a de nouveau disparu ».
- **Les poids fine-tunés ne sont pas versionnés.** `bench/runs/.gitignore` couvre `*.trec` et
  `embeddings_cache/` mais **ne couvre pas** `F1_artifacts/finetuned_model/model.safetensors`. Le
  fichier `.gitignore` n'a **pas** été modifié (interdit à ce lot) : l'artefact est simplement
  **jamais indexé**, et le fait est écrit ici plutôt que corrigé en silence.

---

## 8. Ce qu'il reste à décider — et par qui

Ce lot s'arrête ici et ne propose rien. Les faits sur la table, pour l'opérateur :

1. Le pipeline complet a tourné : construction des paires, porte de fuite, fouille des négatifs,
   entraînement, encodage des deux bras sur le jeu réservé. **Tout ce que l'ADR-0012 voulait
   « acheter » — la méthode — a été exercé de bout en bout.** Ce qui n'a pas eu lieu, c'est la
   dernière étape : la notation du bras.
2. Le bras est **encodé et prêt** (`B_holdout_f1_finetuned_run.trec`, 31 000 lignes, 310 requêtes) :
   il n'a **pas** été noté, et il ne le sera pas sans que F7 soit tranché.
3. Le contrôle F7 a échoué **pour une cause identifiée, quantifiée, et étrangère au bras**.
4. L'ADR-0012 F7 interdit toute relaxation en vol et exige, pour bouger, un **amendement relu par un
   chercheur non-Claude puis accepté par l'opérateur**. **Le chercheur non-Claude existe désormais
   sur cette machine** — sous la réserve d'invocation notée au § 7 (nvm à sourcer). Le diagnostic du
   § 2, y compris la tension `RR@10` / `nDCG@10` que ce rapport signale sans la résoudre, est
   précisément le matériau qu'un tel amendement devrait lui soumettre. **Ce lot ne le rédige pas.**

