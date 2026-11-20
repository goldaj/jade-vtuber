# Production artistique Live2D r21 — backlog opérationnel

**Branche :** develop · **Révision :** 18 novembre 2026 · **Type :** ART.

Production du modèle complet r21 à partir des sources et checkpoints existants, sans réintroduire les anciennes démos. Le runtime r20 reste utilisable pour la première recette (jalon A), indépendamment du r21 (jalon B).

**Priorité :** valeur et dépendances, pas un engagement de calendrier. **DoD officielle :** [règle de clôture commune](DEFINITION_OF_DONE.md), adaptée aux assets, à Cubism/VTS et aux essais graphiques. **Codex (tout modèle/sous-agent) OU le propriétaire** peut valider chaque carte après une vérification explicite et des preuves réelles.

| ID | Prio | Jalon | Statut | Situation initiale | Tâche | Résultat attendu / vérification | Dépend de |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **ART-001** | P1 | B | **À qualifier** | À réconcilier | Aligner la reprise Codex avec l'avancement artistique v31 | Comparer MODEL2D_CODEX_STATE et CONTINUATION : plan directeur, propriétaire, prochain checkpoint, jalons et preuve ; ne pas réinitialiser les progrès faits après v30. | OPS-002 |
| **ART-002** | P1 | B | **À faire** | À vérifier sur D: | Identifier et sécuriser les sources r20/r21 | Inventorier v30/v31/r02, maîtres RGBA, CMO3, PSD/KRA et checkpoints ; confirmer intégrité LFS, rôle et versions avant retouche. | OPS-002 |
| **ART-003** | P1 | B | **En cours** | [Candidat 2×4096 contrôlé hors ligne](../operations/handoffs/2026-11-20-codex-art003-atlas.md) ; contrôle natif et export à faire | Corriger les UV et construire un atlas plein pied | Repartir d'une copie v31 intacte ; corriger remappage UV des pièces bas du corps, vérifier corps/jambes/chaussures après export ; ne pas promouvoir les anciens atlas 4096 non valides. | ART-002 |
| **ART-004** | P1 | B | **À faire** | À terminer | Réparer les raccords cheveux, épaules, cou et vêtements | Contrôler poses neutres, extrêmes et combinées ; éliminer trous, doubles silhouettes, bandes incorrectes et racines de mèches instables. | ART-002 |
| **ART-005** | P1 | B | **À faire** | À terminer, non bloquant pour premier export candidat | Corriger le clignement et les yeux | Conserver sprites réellement fermés et iris stables ; résoudre cils gris, contours doubles et reliquat d'iris en transition, sans retarder inutilement la première version utilisable. | ART-002 |
| **ART-006** | P1 | B | **À faire** | À finir | Finaliser tête, regard et rig du corps plein pied | Valider Head X/Y/Z, diagonales, cou/épaules, posture, bras, bassin, jambes et chaussures avec amplitude et volume cohérents. | ART-002, ART-004 |
| **ART-007** | P1 | B | **À faire** | À créer/ajuster | Finaliser les physiques cheveux, oreilles et vêtements | Construire et calibrer physique r21 propre aux paramètres r21 ; ne pas copier sans adaptation les sorties r20 absentes. | ART-004, ART-006 |
| **ART-008** | P1 | B | **À faire** | À finir | Créer idle, expressions et règles de transitions r21 | Clignements, respiration, micro-mouvements, neutralisation et priorités entre animation, parole, tracking et physique sans saut ou pose collante. | ART-005, ART-006, ART-007 |
| **ART-009** | P1 | B | **À faire** | Non livré | Créer 14 motions corporelles originales | Deux animations distinctes pour chacune des 7 intentions, avec gestuelle/regard/posture propres, jamais un simple renommage ; livrer assets et paramètres utilisables. | ART-006, ART-007, ART-008 |
| **ART-010** | P1 | B | **À faire** | Non synchronisé | Réconcilier les sources éditables KRA/PSD avec le rig r21 | Transposer couches, masques et sous-peintures utiles dans des copies maîtrisées, garder images masters et GUID ; comparer avec modèle natif et noter les divergences restantes. | ART-002, ART-004, ART-006 |
| **ART-011** | P1 | B | **À faire** | Non livré | Créer le bundle r21 versionné et réutilisable | Exporter moc3, model3.json, textures/atlas, physique, expressions, motions, manifestes et documentation de provenance ; valider intégrité du corps entier. | ART-003, ART-007, ART-008, ART-009, ART-010 |
| **ART-012** | P1 | B | **À faire** | À valider sur Windows | Importer, calibrer et recetter r21 dans VTube Studio | Ouvrir le bundle final dans VTube Studio, calibrer entrées/sens/inertie, contrôler toutes poses et motions, lip-sync, performance et récupération du neutre ; consigner défauts réels. | ART-011, DEV-001 |

## Usage pour les agents

**Clôture :** suivre la [Definition of Done officielle](DEFINITION_OF_DONE.md). **Done** n'est autorisé qu'après une passe de vérification explicite et une validation positive par **Codex OU le propriétaire**, les deux autres garanties étant les preuves pertinentes et la traçabilité/intégration requises. La décision indique dans la passation/PR liée : ID(s), validateur, date, version/SHA ou asset, tests observés, limites et livraison. Aucune carte n'a été automatiquement clôturée lors de l'adoption de cette règle.



- Ne jamais confondre **fonction déjà codée mais non recettée** et **travail logiciel à développer**.
- Tout nouveau bug exige une observation reproductible : source, environnement/branche SHA, résultat réel vs attendu, impact, dépendance de recette et preuve sans contenu privé.
- La décision de prise en charge, la branche de travail et le responsable sont confirmés à l'ouverture ; ce document n'autorise aucune dépense, modification d'un poste local ou écriture dans main.
- Pour le r21 : préserver checkpoints natifs, sources et licences ; le dessin, le rig et les assets vont dans la [production 2D](04-PRODUCTION-2D.md), le câblage du runtime dans le [développement](01-DEVELOPPEMENT.md).

## Sources de référence

- [État de travail artistique](../../jade-modeling/CONTINUATION.md)
- [Plan qualité r21](../../jade-modeling/PLAN_QUALITE_PRO_20261113.md)
- [Reprise Codex 2D](../../jade-modeling/MODEL2D_CODEX_STATE.md)
- [Passation des animations](../history/gpt6-jade/LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md)

Retour au [backlog opérationnel](README.md).
