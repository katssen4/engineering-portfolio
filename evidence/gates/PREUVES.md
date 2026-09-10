# PREUVES

Registre de preuve de ce répertoire. Il sert d'exemple exécutable : `proof_registry.py` le relit
et vérifie mécaniquement les trois catégories qui peuvent l'être.

Format d'une ligne : `- [CATÉGORIE] énoncé — preuve : pointeur`

**Ce qu'une catégorie prouve, exactement.** `[TESTED]` est la plus forte : le test cité doit
exister, et il s'exécute. `[INVARIANT]` est plus faible qu'elle n'en a l'air, et une revue
extérieure a eu raison de le dire : elle prouve qu'une chaîne est encore dans le code, pas que le
garde-fou fonctionne. Elle est donc réservée ici aux gardes dont la chaîne est **distinctive**, et
tout ce qui pouvait passer en `[TESTED]` y est passé.

- [TESTED] La porte refuse un chiffre gonflé dans un document dérivé. — preuve : test_un_chiffre_gonfle_est_refuse
- [TESTED] La porte refuse une affirmation que la source ne porte pas. — preuve : test_une_affirmation_non_sourcee_est_refusee
- [TESTED] Une reformulation honnête du même fait passe. — preuve : test_une_reformulation_honnete_passe
- [TESTED] Un décimal ne se confond plus avec l'entier privé de son point. — preuve : test_un_decimal_n_est_pas_l_entier_sans_le_point
- [TESTED] Le signe entre dans la clé : -10 diffère de 10. — preuve : test_le_signe_entre_dans_la_cle
- [TESTED] L'unité entre dans la clé : 5 MB diffère de 5 GB. — preuve : test_l_unite_entre_dans_la_cle
- [TESTED] Un identifiant long ne perd pas de précision à la normalisation. — preuve : test_un_identifiant_long_ne_perd_pas_de_precision
- [TESTED] Le registre refuse une ligne de puce qui ne suit pas le format. — preuve : test_une_puce_mal_formee_est_signalee_pas_ignoree
- [TESTED] Une catégorie inconnue fait échouer le contrôle. — preuve : test_une_categorie_inventee_fait_echouer
- [TESTED] Un test cité qui n'existe plus fait échouer le contrôle. — preuve : test_un_test_cite_qui_n_existe_plus_fait_echouer
- [INVARIANT] Le fabricant de document lève plutôt que d'écrire un fichier dont un contrôle a échoué. — preuve : `Un controle a echoue : le fichier n'est pas ecrit.`
- [INVARIANT] Le sondeur ouvre réellement chaque adresse au lieu de la supposer connue. — preuve : `urllib.request.urlopen`
- [OBSERVED] Les quatre outils ont été rendus agnostiques et versés ici. — preuve : 2026-09-10
- [OBSERVED] Deux revues extérieures à l'aveugle ont été instruites contre ce répertoire. — preuve : 2026-09-10
- [DESIGN] Les commentaires du code sont en français, langue de travail du laboratoire, tandis que le reste du dépôt est en anglais. Assumé plutôt que traduit après coup.
- [DESIGN] La porte anti-invention signale plus qu'elle ne laisse passer : un mot ordinaire en tête de phrase peut être pris pour un nom propre. Le biais est volontaire.
- [KNOWN GAP] La porte est lexicale : une phrase qui contredit la source sans introduire de jeton passe. Deux cas sont livrés comme tests dans `tests/test_anti_invention.py`.
- [KNOWN GAP] La porte ne voit pas les omissions : retirer une rubrique de réserves ne déclenche rien.
- [KNOWN GAP] Le fabricant de document n'a pas de test unitaire ici : ses onze contrôles s'exercent sur un vrai document, qui n'est pas public. Il faudrait un document d'exemple pour les couvrir.
- [KNOWN GAP] Le sondeur n'a pas de test hors ligne : il faudrait un serveur factice pour couvrir les quatre formes de réponse.
