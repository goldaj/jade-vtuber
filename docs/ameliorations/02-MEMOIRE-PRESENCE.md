# Mémoire anticipée, identités et présence

**Principe :** charger les données autorisées **avant** que l'interlocuteur parle, mais n'injecter au modèle que les quelques souvenirs pertinents. La mémoire actuelle repose sur SQLite, une sélection chronologique/limitée et une identité Goldaj commune au micro local et au mobile authentifié.

| ID | Priorité / état | Amélioration proposée / condition de réussite |
| --- | --- | --- |
| MEM-05 | P1 / P | **Planifier les personnes du jour** : commande privée ou interface propriétaire « aujourd'hui je parlerai à… ». Résoudre les vrais ID/liaisons consenties et précharger L1/L2 dès l'annonce. Ne pas deviner un compte depuis un surnom. |
| MEM-08 | P2 / P | **Discord serveur en ligne** : préchargement plus léger (L1, quota limité) sur événement de présence, indépendamment d'une interaction. Nécessite d'étudier Guild Presences/Guild Members, permissions, coût RAM et opt-in. Être « en ligne » n'indique pas un canal particulier. |
| MEM-12 | P2 / P | Distinguer clairement **mémoire d'une personne**, **mémoire de relation**, **mémoire partagée d'un serveur/salon**, **autobiographie privée de Jade** et éventuels souvenirs publics validés. Les scopes ne s'ouvrent jamais implicitement. |
| MEM-14 | P2 / P | Anticiper récupération L2 à partir de **transcriptions STT provisoires**, sans injecter ni stocker une hypothèse erronée ; revalidation finale et annulation en cas de changement d'interlocuteur. |
| MEM-15 | P2 / E | Qualité de la **curation asynchrone** : pertinence des Core, doublons sémantiques, contradictions, coûts, surcharge, possibilité de curation par lots, sans retarder la parole. |
| MEM-16 | P2 / E | Commandes personnelles de **consultation, correction ciblée, export, déliaison et effacement** ; révoquer les caches, clarifier les archives déjà sauvegardées et les journaux séparés de SQLite. |
| MEM-17 | P3 / D | Éventuelle mémoire autobiographique globale de Jade partageable publiquement, uniquement après classification des événements, politique de visibilité et accord explicite ; l'actuel core_self privé ne devient jamais public par défaut. |

**Normalisation et récupération structurée :** la sélection pertinente et le rappel sécurisé sont désormais dans [DEV-022](../backlog/01-DEVELOPPEMENT.md), le cache sensible à la présence dans [DEV-023](../backlog/01-DEVELOPPEMENT.md). Les données structurées et la provenance restent traitées dans [10-NORMALISATION-DONNEES-MEMOIRE.md](10-NORMALISATION-DONNEES-MEMOIRE.md) ; la qualité de la curation asynchrone demeure une proposition distincte (MEM-15).

## Invariants de sécurité

La **présence n'est ni un consentement à mémoriser, ni une permission de divulgation**. On peut préparer un cache autorisé pour une identité déjà opt-in ; pour un utilisateur non opt-in, aucune récupération de souvenirs personnels ni activation mémoire automatique. Les données de tiers ne sont pas exposées à Goldaj simplement parce qu'il utilise l'application privée.

**Sources :** [mémoire Codex](../history/gpt6-jade/HANDOFF-CODEX-MEMORY-20261115.md), [spécification mémoire](../history/gpt6-jade/PLAN-MEMOIRE-PERSISTANTE-IDENTITES-CORE-20261115.md) (historique, état initial périmé), [audit transverse](../history/gpt6-jade/AUDIT-TRANSVERSE-20261115.md), [conversation unifiée](../history/gpt6-jade/IDEE-CONVERSATION-UNIFIEE-20261115.md), code memory_store.py / memory_service.py, conversation du 16/11/2026.
