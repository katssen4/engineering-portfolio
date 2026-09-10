# PREUVES

Registre de preuve de ce répertoire. Il sert d'exemple exécutable : `proof_registry.py` le relit
et vérifie mécaniquement les trois catégories qui peuvent l'être.

Format d'une ligne : `- [CATÉGORIE] énoncé — preuve : pointeur`

- [TESTED] Le registre refuse une ligne de puce qui ne suit pas le format. — preuve : test_une_puce_mal_formee_est_signalee_pas_ignoree
- [TESTED] Une catégorie inconnue fait échouer le contrôle. — preuve : test_une_categorie_inventee_fait_echouer
- [INVARIANT] La porte anti-invention sort en code 1 dès qu'un nombre ou un nom propre manque à la source. — preuve : `sys.exit(1)`
- [INVARIANT] Le fabricant de document refuse d'écrire quand un de ses contrôles échoue. — preuve : `ECHEC`
- [INVARIANT] Le sondeur de portes appelle réellement chaque adresse au lieu de la supposer connue. — preuve : `urllib.request`
- [OBSERVED] Les trois outils ont été rendus agnostiques et versés ici. — preuve : 2026-09-10
- [DESIGN] Les commentaires du code sont en français, langue de travail du laboratoire, tandis que le reste du dépôt est en anglais. Assumé plutôt que traduit après coup.
- [DESIGN] La porte anti-invention signale plus qu'elle ne laisse passer : un mot ordinaire en tête de phrase peut être pris pour un nom propre. Le biais est volontaire.
- [KNOWN GAP] Le fabricant de document n'a pas de test unitaire ici : ses onze contrôles s'exercent sur un vrai document, qui n'est pas public. Il faudrait un document d'exemple pour les couvrir.
- [KNOWN GAP] Le sondeur n'a pas de test hors ligne : il faudrait un serveur factice pour couvrir les quatre formes de réponse.
