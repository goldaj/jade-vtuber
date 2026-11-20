# Demande P0 : Core Memory explicite du créateur (20 novembre 2026)

> **HISTORIQUE, EXIGENCES REMPLACÉES LE 20 NOVEMBRE 2026.** Nouvelle décision du propriétaire : les demandes humaines mémorisent uniquement en ordinaire, Jade choisit seule ses Core Memories. Voir [la nouvelle passation DEV-011](2026-11-20-chatgpt-dev011-ordinary-autonomous-core.md). Les comportements d’ajout Core décrits ci-dessous ne doivent pas être rétablis.

- Mission : consigner dans le **backlog opérationnel** la demande de Goldaj, sans implémentation prématurée.
- Branche : `docs/p0-explicit-core-memories-20261120`, base `develop` au commit `3325990c56d1f3f478c0e6394189b42b14de825f`.
- Carte : **DEV-011**, **P0**, jalon A, **À faire**.
- Objectif : Jade doit pouvoir écrire immédiatement et durablement une Core Memory lorsque Goldaj, créateur identifié et autorisé, le lui demande explicitement en langage naturel.
- Critères : identifier le propriétaire de manière fiable, y compris via les comptes liés prouvés ; conserver le souvenir dans `core_self` ou `core_relationship` selon sa nature sans attendre la curation ; confirmer seulement après écriture SQLite ; préserver persistance, provenance, idempotence, suppression, confidentialité interpersonnelle et inter-salons ; refuser les non-propriétaires.
- Impact : `docs/backlog/01-DEVELOPPEMENT.md` (statut canonique) et `docs/backlog/README.md` (priorité et compte). Aucun code, base privée ou configuration locale modifié.
- Vérification : cohérence ID/priorité/statut/rang, pas de conflit de priorités, liens internes. Validation de la **fonction** reste à faire suivant la DoD et ses tests fonctionnels réels.
- Reprise : examiner `src/jade_runtime/memory_service.py`, `memory_store.py`, `identity_of`, les liaisons de compte et l'orchestrateur ; implémenter les autorisations et les tests de non-régression sans attribuer les droits du créateur à un simple pseudo déclaré.

**Note :** ne pas clôturer DEV-011 simplement parce que l'ajout au backlog est committé. La livraison et sa recette restent ouvertes.