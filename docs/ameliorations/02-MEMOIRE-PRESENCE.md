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


La sélection de souvenirs est suivie en REC-032 et le cache de présence en REC-033. La lecture globale de l’autobiographie, anciennement envisagée dans MEM-17, est intégrée à la consultation L1/L2/L3. [Recettes](../backlog/02-RECETTE.md) · [Mémoire globale](../operations/handoffs/2026-11-22-jade-global-memory.md)

## Présence et droits de mémoire

La présence et la liaison des comptes donnent des repères aux parcours d’écriture et à la reprise d’une session. La consultation globale permet à Jade de rappeler ses souvenirs avec leur origine, y compris sur les canaux publics. Les futures optimisations de cache doivent préserver les contrôles d’inscription, d’écriture et de suppression.

**Sources :** [mémoire Codex](../history/gpt6-jade/HANDOFF-CODEX-MEMORY-20261115.md), [spécification mémoire](../history/gpt6-jade/PLAN-MEMOIRE-PERSISTANTE-IDENTITES-CORE-20261115.md) (historique, état initial périmé), [audit transverse](../history/gpt6-jade/AUDIT-TRANSVERSE-20261115.md), [conversation unifiée](../history/gpt6-jade/IDEE-CONVERSATION-UNIFIEE-20261115.md), code memory_store.py / memory_service.py, conversation du 16/11/2026.
