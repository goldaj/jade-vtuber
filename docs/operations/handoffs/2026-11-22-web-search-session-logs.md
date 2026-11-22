# Passation : journal web par session de démarrage (22 novembre 2026)

## Objet
Remplacer l'unique fichier historique des recherches Tavily par un dossier privé contenant un JSONL horodaté distinct par lancement de Jade, conformément à la mécanique des logs de sessions généraux.

## Implémentation
- Dossier par défaut `D:/Jade/private/jade-web-search/` sur Windows ou dossier voisin de `JADE_MEMORY_DB_PATH` ; nouvelle option `JADE_WEB_LOG_DIR`.
- Ancienne configuration `JADE_WEB_LOG_PATH` toujours lue, convertie vers un dossier du même nom sans `.jsonl`. L'ancien fichier unique demeure intact.
- À chaque démarrage live avec le web activé, création exclusive de `jade-web-search_<horodatage>_pid-XXXX.jsonl`, avec une entrée `session_started` même si aucune recherche ne suit.
- Événement `web_search_journal_started` affichant l'emplacement dans les logs généraux ; toutes les tentatives restent tracées avant tout accès réseau avec `fsync`.
- Aucun appel Tavily ni migration destructive des journaux lors du déploiement. Aucune purge automatique.

## QA et reprise
- Tests ajoutés dans `tests/test_jade_web_search.py` (rotation par démarrage, fichier initial, compatibilité ancien réglage, non-écrasement, échec de création).
- Lire la CI du commit associé pour confirmer les contrôles offline. Les erreurs historiques des tests mémoire sont distinctes.
- Recette sur PC, clé Tavily réelle et redémarrage effectif restent couverts par REC-038, `À valider`.
