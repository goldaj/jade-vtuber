# Développement logiciel engagé ou conditionnel — backlog opérationnel

**Branche :** develop · **Révision :** 18 novembre 2026 · **Type :** DEV.

Au dernier relevé GitHub, aucune issue/PR de développement ouverte. Les fonctionnalités existantes ne sont pas à recoder. Ce tableau distingue un travail futur **déjà nécessaire pour livrer le r21** des **anomalies candidates qui ne deviennent du développement qu'après reproduction en recette**. Il ne reprend pas par défaut les 185 idées futures.

**Priorité :** valeur et dépendances, pas un engagement de calendrier. **Statut non finalisé :** les critères spécifiques ci-dessous sont des résultats attendus, pas la Definition of Done transversale, à définir avec le propriétaire ultérieurement.

| ID | Prio | Jalon | Situation | Tâche | Résultat attendu / vérification | Dépend de |
| --- | --- | --- | --- | --- | --- | --- |
| **DEV-001** | P1 | B | Bloqué par assets r21 | Raccorder les 14 vraies motions r21 au runtime Jade | Lorsque les assets ART-009/011 seront prêts : contrat de motions versionné, sélection de deux motions par intention, transitions, idle/replis r20, appels Windows et PWA, tests de non-régression. Ne pas considérer les expressions r20 A/B comme 14 motions. | ART-009, ART-011, REC-020 |
| **DEV-002** | P1 | A | Conditionnel : anomalie à confirmer | Corriger une éventuelle incompatibilité SDK Live2D Web Android | Créer un correctif uniquement si REC-019 révèle un défaut reproductible de compatibilité moc3/Cubism/adapter ; documenter version, cas minimal, correction et résultat ciblé. Sinon clore la qualification sans développement. | OPS-010, REC-019 |
| **DEV-003** | P0 | A | Conditionnel : anomalie à confirmer | Corriger la sortie indésirable du repli WAV s'il se produit réellement | Le code courant contient encore un chemin de fallback pouvant jouer hors destination. Vérifier REC-007/REC-005 ; si reproduit, corriger ce défaut avec régression d'isolation sans engager la refonte RTE-01 du catalogue futur. Sinon pas de changement arbitraire. | REC-005, REC-007 |

## Usage pour les agents

- Ne jamais confondre **fonction déjà codée mais non recettée** et **travail logiciel à développer**.
- Tout nouveau bug exige une observation reproductible : source, environnement/branche SHA, résultat réel vs attendu, impact, dépendance de recette et preuve sans contenu privé.
- La décision de prise en charge, la branche de travail et le responsable sont confirmés à l'ouverture ; ce document n'autorise aucune dépense, modification d'un poste local ou écriture dans main.
- Pour le r21 : préserver checkpoints natifs, sources et licences ; le dessin, le rig et les assets vont dans la [production 2D](04-PRODUCTION-2D.md), le câblage du runtime dans le [développement](01-DEVELOPPEMENT.md).

## Sources de référence

- [Code actuel et limites](../handbook/BRANCH_STATE.md)
- [PCM et mémoire](../operations/handoffs/2026-11-16-chatgpt-pcm-memoire-mobile.md)
- [Animation r21](../history/gpt6-jade/LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md)
- [Idées futures non engagées](../ameliorations/README.md)

Retour au [backlog opérationnel](README.md).
