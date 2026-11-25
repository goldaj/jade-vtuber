# Production artistique Live2D r21 — backlog opérationnel

**Branche :** develop · **Révision :** 18 novembre 2026 · **Type :** ART.

Production du modèle complet r21 à partir des sources et checkpoints existants, sans réintroduire les anciennes démos. Le runtime r20 reste utilisable pour la première recette (jalon A), indépendamment du r21 (jalon B).

**Priorité :** valeur et dépendances, pas un engagement de calendrier. **DoD officielle :** [règle de clôture commune](DEFINITION_OF_DONE.md), adaptée aux assets, à Cubism/VTS et aux essais graphiques. **Codex (tout modèle/sous-agent) OU le propriétaire** peut valider chaque carte après une vérification explicite et des preuves réelles.

| ID | Prio | Jalon | Statut | Situation initiale | Tâche | Résultat attendu / vérification | Dépend de |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **ART-001** | P1 | B | **En cours** | Plan approuvé, feu vert donné le 25/11 | Aligner la reprise Codex avec le v32 local et les MCP | Réconcilier le plan, le suivi et l’état du v32 local. Préparer les copies de travail et maintenir le point de reprise des outils et des candidats. | OPS-002 |
| **ART-002** | P1 | B | **À faire** | À vérifier sur D: | Identifier et sécuriser les sources r20/r21 | Inventorier v30/v31/r02, maîtres RGBA, CMO3, PSD/KRA et checkpoints ; confirmer intégrité LFS, rôle et versions avant retouche. | OPS-002 |
| **ART-003** | P1 | B | **En cours** | Premier r21 chargé en pied, contrôle des corrections v33 en cours | Obtenir un atlas plein pied fidèle au v31 | Ouvrir une copie du v32 dans Cubism et utiliser Turboism. Vérifier l’ourlet, le corps, les jambes et les chaussures après export. Corriger les défauts observés qui bloquent le premier paquet utilisable. | ART-001, ART-002 |
| **ART-004** | P1 | B | **En cours** | Triangles des deux épaules retirés, raccords joues et mèches revus sur quatre diagonales en v39 | Réparer les raccords cheveux, épaules, cou et vêtements | Contrôler poses neutres, extrêmes et combinées ; éliminer trous, doubles silhouettes, bandes incorrectes et racines de mèches instables. | ART-002 |
| **ART-005** | P1 | B | **En cours** | Regard et clignement acceptés en v39. Reste un liseré d’environ 1 px au bas de l’iris en regard haut extrême | Corriger le clignement et les yeux | Conserver sprites réellement fermés et iris stables ; résoudre cils gris, contours doubles et reliquat d'iris en transition, sans retarder inutilement la première version utilisable. | ART-002 |
| **ART-006** | P1 | B | **En cours** | Regard et sourcils validés en parole. Coordination buste, bassin, genoux et pieds à terminer | Finaliser tête, regard et rig du corps plein pied | Valider Head X/Y/Z, diagonales, cou/épaules, posture, bras, bassin, jambes et chaussures avec amplitude et volume cohérents. | ART-002, ART-004 |
| **ART-007** | P1 | B | **À faire** | À créer/ajuster | Finaliser les physiques cheveux, oreilles et vêtements | Construire et calibrer physique r21 propre aux paramètres r21 ; ne pas copier sans adaptation les sorties r20 absentes. | ART-004, ART-006 |
| **ART-008** | P1 | B | **En cours** | Smile et Sad validés en parole, bascule et relâchement en VTS. Socle des autres intentions et idle final à terminer | Créer idle, expressions et règles de transitions r21 | Clignements, respiration, micro-mouvements, neutralisation et priorités entre animation, parole, tracking et physique sans saut ou pose collante. | ART-005, ART-006, ART-007 |
| **ART-009** | P1 | B | **À faire** | Non livré | Créer 14 motions corporelles originales | Deux animations distinctes pour chacune des 7 intentions, avec gestuelle/regard/posture propres, jamais un simple renommage ; livrer assets et paramètres utilisables. | ART-006, ART-007, ART-008 |
| **ART-010** | P1 | B | **En cours** | Sept pièces reportées en KRA/PSD et deltas v36, v38, v39 conservés pour la suite | Réconcilier les sources éditables KRA/PSD avec le rig r21 | Transposer couches, masques et sous-peintures utiles dans des copies maîtrisées, garder images masters et GUID ; comparer avec modèle natif et noter les divergences restantes. | ART-002, ART-004, ART-006 |
| **ART-011** | P1 | B | **En cours** | Paquet natif v39 chargé avec les expressions en parole. Bundle final à produire | Créer le bundle r21 versionné et réutilisable | Exporter moc3, model3.json, textures/atlas, physique, expressions, motions, manifestes et documentation de provenance ; valider intégrité du corps entier. | ART-003, ART-007, ART-008, ART-009, ART-010 |
| **ART-012** | P1 | B | **À faire** | Prérecette v39 en parole et suivi de tête. Calibration et recette du bundle final à réaliser après ART-011 | Importer, calibrer et recetter r21 dans VTube Studio | Ouvrir le bundle final dans VTube Studio, calibrer entrées/sens/inertie, contrôler toutes poses et motions, lip-sync, performance et récupération du neutre ; consigner défauts réels. | ART-011, DEV-001 |

## Usage pour les agents

**Clôture :** suivre la [Definition of Done officielle](DEFINITION_OF_DONE.md). **Done** n'est autorisé qu'après une passe de vérification explicite et une validation positive par **Codex OU le propriétaire**, les deux autres garanties étant les preuves pertinentes et la traçabilité/intégration requises. La décision indique dans la passation/PR liée : ID(s), validateur, date, version/SHA ou asset, tests observés, limites et livraison. Aucune carte n'a été automatiquement clôturée lors de l'adoption de cette règle.



- Ne jamais confondre **fonction déjà codée mais non recettée** et **travail logiciel à développer**.
- Tout nouveau bug exige une observation reproductible : source, environnement/branche SHA, résultat réel vs attendu, impact, dépendance de recette et preuve sans contenu privé.
- La décision de prise en charge, la branche de travail et le responsable sont confirmés à l'ouverture ; ce document n'autorise aucune dépense, modification d'un poste local ou écriture dans main.
- Pour le r21 : préserver checkpoints natifs, sources et licences ; le dessin, le rig et les assets vont dans la [production 2D](04-PRODUCTION-2D.md), le câblage du runtime dans le [développement](01-DEVELOPPEMENT.md).

## Sources de référence

- [État de travail artistique](../../jade-modeling/CONTINUATION.md)
- [Plan directeur r21 approuvé](../../jade-modeling/MODEL2D_MASTER_PLAN.md)
- [Plan qualité r21 du 13 novembre](../../jade-modeling/PLAN_QUALITE_PRO_20261113.md)
- [Reprise Codex 2D](../../jade-modeling/MODEL2D_CODEX_STATE.md)
- [Passation des animations](../history/gpt6-jade/LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md)

Retour au [backlog opérationnel](README.md).
