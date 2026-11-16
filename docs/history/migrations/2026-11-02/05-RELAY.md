# Relais manuel Astra puis Terra

**Astra a terminé la revue le 2 novembre 2026.** Le prochain intervenant est Terra ; commencer par [06-ASTRA-REVIEW.md](06-ASTRA-REVIEW.md), puis exécuter le plan amendé. Le message de reprise Astra ci-dessous est conservé comme historique, sans demander une nouvelle revue identique.

Le propriétaire demande cette revue Astra pour la présente migration. Aucun modèle n’est changé par l’agent ; aucune règle générale de double revue automatique n’est créée.

## Point de reprise

- Copie : `D:\Codex\projects\jade-migration-20261102`.
- Branche : `codex/migration-audit-20261102`, documents et scripts de constat sur research `df544ed`.
- Lire `AGENTS.md`, `docs/conversations/INDEX.md`, puis `docs/migration/2026-11-02/README.md`.
- Ancien clone applicatif inchangé ; aucune production active selon le propriétaire.

## Message de reprise proposé pour Astra

> Relis le dossier de migration Jade du 2 novembre 2026 dans D:\Codex\projects\jade-migration-20261102. Lis AGENTS.md et l’index de conversation avant toute modification. Le visuel et l’animation 2D sont hors périmètre. Vérifie les références actuelles, le traitement de chaque branche, les huit reproductions, les quatre constats supplémentaires et les doutes. Challenge surtout l’arrêt immédiat, l’expiration/coût HTTP, la coordination micro/parole, les ressources Discord et les critères de première mise en service. Aucune production n’est active. Confirme ou corrige le plan et documente ton avis ; ne corrige pas encore le runtime et ne fusionne pas. Prépare le retour sous Terra après cette relecture.

## Décisions à examiner

| Sujet | Proposition actuelle | Décision attendue |
| --- | --- | --- |
| Cible Git | `develop`, une seule intégration consolidée | Confirmer ; `master` reste historique |
| Arrêt | Immédiat et gracieux distincts, admissions fermées avant fermeture | Invariants et délai maximal |
| HTTP | Échéance portée par le travail, pas d’appel pour requête expirée en file | Annulation, délai global et idempotence |
| Micro/parole | Coordination partagée, traitement de la capture déjà commencée | Stratégie half-duplex et limites face à l’écho acoustique |
| Connecteurs | Corrections avant activation | Modes inclus ou laissés inactifs en première release |
| Installation | Venv Windows et lock, extras choisis | Outil de lock et compatibilité |
| CI | Aucun run final vert, locaux 51/51 | Diagnostic et preuve SHA final |
| Preview public | F11 distinct et différable | Ne pas bloquer l’intégration privée pour publier |

Astra doit ajouter un avis daté : constats confirmés/rejetés avec preuve, corrections du plan, décisions humaines restantes et lots exécutables. Rejouer seulement les vérifications nécessaires aux points contestés ; ne pas inventer de test live. Les anciens documents 2D ne relancent pas ce chantier.

## Reprise Terra et clôture

Exécuter le plan par petits changements avec tests ciblés et commits séparés. Relever les références avant intégration ; préserver les quatre documents exclusifs à develop et actualiser `TASKS.md`. Les modes externes restent désactivés jusqu’à leur validation. La demande actuelle n’a exécuté ni push, ni fusion, ni mise en service.

La PR #2 reste la référence à conserver si possible : la branche d’exécution pourra avancer sa source par historique normal, sans force-push, lors de la reprise autorisée. Une PR de remplacement ne se justifie que si l’état distant change ou si cette voie devient techniquement inadaptée. Toujours une seule PR active d’intégration, aucune seconde fusion de #1.

La migration sera achevée quand les défauts bloquant les modes retenus seront corrigés et testés, l’installation verrouillée vérifiée, les preuves CI finales disponibles et les connecteurs activés recettés en privé. Il faudra aussi un arrêt efficace, des ressources bornées, un budget d’appels défini, une intégration unique, un statut pour chaque branche et une installation traçable avec retour arrière. Une exception de CI éventuelle doit être examinée explicitement, sans prétendre à une CI verte.

Un feu vert de migration privée n’est pas une autorisation de rendre public l’ancien historique ou les sources.
