# Mémoire anticipée, identités et présence

**Principe :** charger les données autorisées **avant** que l'interlocuteur parle, mais n'injecter au modèle que les quelques souvenirs pertinents. La mémoire actuelle repose sur SQLite, une sélection chronologique/limitée et une identité Goldaj commune au micro local et au mobile authentifié.

| ID | Priorité / état | Amélioration proposée / condition de réussite |
| --- | --- | --- |
| MEM-01 | P1 / P | Développer un **PresenceAwareMemoryCache** commun aux canaux. Chargement asynchrone par identité stable, plafonds RAM, métadonnées de version, métriques hits/miss et aucune requête payante par simple présence. |
| MEM-02 | P1 / P | **L1** : profil compact prêt pour le modèle (identité, relation, préférences autorisées, événements majeurs, contexte récent). Contexte petit et daté ; ne pas remplir systématiquement le prompt. |
| MEM-03 | P1 / P | **L2** : souvenirs détaillés, index de recherche locale et historique préparés en RAM pour les personnes susceptibles d'interagir ; recherche à la demande sans charger tout le dossier dans le LLM. |
| MEM-04 | P2 / E | **L3** : SQLite durable, source de vérité ; optimiser les index, scopes et requêtes, sans remplacer arbitrairement SQLite par une base serveur. |
| MEM-05 | P1 / P | **Planifier les personnes du jour** : commande privée ou interface propriétaire « aujourd'hui je parlerai à… ». Résoudre les vrais ID/liaisons consenties et précharger L1/L2 dès l'annonce. Ne pas deviner un compte depuis un surnom. |
| MEM-06 | P1 / P | **Goldaj PC/mobile** : précharger immédiatement le profil propriétaire commun à l'ouverture d'une session locale authentifiée, puis le tenir à jour ; aucun mélange avec un compte Discord se prétendant Goldaj. |
| MEM-07 | P1 / P | **Discord vocal** : sur entrée d'un membre dans le salon Jade, précharger ses souvenirs autorisés **sans attendre qu'il parle ou écrive**, puis actualiser à chaque activité et libérer après sortie. |
| MEM-08 | P2 / P | **Discord serveur en ligne** : préchargement plus léger (L1, quota limité) sur événement de présence, indépendamment d'une interaction. Nécessite d'étudier Guild Presences/Guild Members, permissions, coût RAM et opt-in. Être « en ligne » n'indique pas un canal particulier. |
| MEM-09 | P1 / P | TTL après déconnexion/départ (valeur initiale à essayer : 10 min), maintien en cas de retour rapide et **LRU pondérée par priorité** : Goldaj > personnes annoncées/vocal Jade > autres membres en ligne > anciens participants. |
| MEM-10 | P1 / P | **Invalidation ciblée** lors de création/correction/suppression de souvenir. Un oubli/retrait de consentement invalide immédiatement L1/L2, même si des résumés ou tâches de curation étaient en cours. |
| MEM-11 | P2 / E | Élargir la sélection à la pertinence, récence, portée, contradictions et provenance : recherche texte/FTS puis éventuellement embeddings locaux, sans transformer chaque réponse en appel d'inférence mémoire. |
| MEM-12 | P2 / P | Distinguer clairement **mémoire d'une personne**, **mémoire de relation**, **mémoire partagée d'un serveur/salon**, **autobiographie privée de Jade** et éventuels souvenirs publics validés. Les scopes ne s'ouvrent jamais implicitement. |
| MEM-13 | P2 / E | **Conversation Discord unifiée** au-delà du chat textuel natif du même vocal : association d'autres salons seulement si explicite et autorisée ; chronologie fiable quand STT et textes arrivent en désordre. |
| MEM-14 | P2 / P | Anticiper récupération L2 à partir de **transcriptions STT provisoires**, sans injecter ni stocker une hypothèse erronée ; revalidation finale et annulation en cas de changement d'interlocuteur. |
| MEM-15 | P2 / E | Qualité de la **curation asynchrone** : pertinence des Core, doublons sémantiques, contradictions, coûts, surcharge, possibilité de curation par lots, sans retarder la parole. |
| MEM-16 | P2 / E | Commandes personnelles de **consultation, correction ciblée, export, déliaison et effacement** ; révoquer les caches, clarifier les archives déjà sauvegardées et les journaux séparés de SQLite. |
| MEM-17 | P3 / D | Éventuelle mémoire autobiographique globale de Jade partageable publiquement, uniquement après classification des événements, politique de visibilité et accord explicite ; l'actuel core_self privé ne devient jamais public par défaut. |
| MEM-18 | P1 / R | Recetter les identités, scopes et consentements avec deux utilisateurs Discord, Goldaj PC/mobile, opt-in puis oubli/réactivation, déconnexion pendant chargement et conversation collective ; aucun souvenir privé ne doit sortir sur le mauvais canal. |

## Invariants de sécurité

La **présence n'est ni un consentement à mémoriser, ni une permission de divulgation**. On peut préparer un cache autorisé pour une identité déjà opt-in ; pour un utilisateur non opt-in, aucune récupération de souvenirs personnels ni activation mémoire automatique. Les données de tiers ne sont pas exposées à Goldaj simplement parce qu'il utilise l'application privée.

**Sources :** [mémoire Codex](../gpt6-jade/HANDOFF-CODEX-MEMORY-20261115.md), [spécification mémoire](../gpt6-jade/PLAN-MEMOIRE-PERSISTANTE-IDENTITES-CORE-20261115.md) (historique, état initial périmé), [audit transverse](../gpt6-jade/AUDIT-TRANSVERSE-20261115.md), [conversation unifiée](../gpt6-jade/IDEE-CONVERSATION-UNIFIEE-20261115.md), code memory_store.py / memory_service.py, conversation du 16/11/2026.
