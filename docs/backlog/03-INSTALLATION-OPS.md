# Installation, exploitation et maintenance — backlog opérationnel

**Branche :** develop · **Révision :** 18 novembre 2026 · **Type :** OPS · **État de référence :** lecture GitHub, pas recette locale.

Préparation du PC, services réels, contrôles Git et clôture des passations. Tâches d'installation et opérations, pas nouvelles fonctionnalités.

Les priorités expriment la valeur de livraison et les dépendances, non un ordre absolu de traitement. **Responsable pressenti :** Codex (modèle ou sous-agent disponible) pour la réalisation sur PC, propriétaire pour les autorisations/comptes et, s'il le souhaite, la validation ; attribution effective à confirmer. **La [DoD officielle](DEFINITION_OF_DONE.md) exige la réalisation, les tests pertinents, l'intégration applicable, la traçabilité et la validation par Codex OU par le propriétaire.** La validation humaine n'est pas obligatoire. La situation initiale ne remplace pas la colonne Statut.

| ID | Prio | Jalon | Statut | Situation initiale | Tâche | Résultat attendu / vérification | Dépend de |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **OPS-001** | P0 | A | **À faire** | À faire sur PC | Sécuriser l'état local avant intervention | Inventorier git status, branches, processus Jade, launcher installé, travaux non commités Codex/Terra et fichiers uniques ; consigner sans écraser. | — |
| **OPS-002** | P0 | A | **À faire** | À faire sur PC | Mettre à jour develop et les assets LFS | Faire fetch puis fast-forward uniquement ; récupérer les objets LFS ; exécuter l'intégrité LFS et verify_assets ; relever les écarts. | OPS-001 |
| **OPS-003** | P0 | A | **À faire** | À confirmer sur PC | Installer/contrôler le socle Windows | Vérifier Python 3.11, Poetry, dépendances all, FFmpeg/ffplay, pilotes audio et OpenGL, chemins sur D: ; garder un inventaire des versions. | OPS-001 |
| **OPS-004** | P0 | A | **À faire** | À faire si nécessaire | Installer/actualiser le launcher réel | Comparer le lanceur installé hors Git avec la version develop ; relancer Installer-Launcher-Jade.cmd si nécessaire ; aucun sélecteur de mode. | OPS-002, OPS-003 |
| **OPS-005** | P0 | A | **À faire** | À confirmer sur PC | Préparer la configuration privée de tous les connecteurs | Réutiliser sans divulguer les fichiers secrets existants ; vérifier les paramètres exigés par --all-channels et les tokens distincts HTTP/mobile. | OPS-001 |
| **OPS-006** | P0 | A | **À faire** | À faire sur PC | Exécuter la validation technique locale | Lancer compilation, suite unittest, contrôle assets et --preflight --all-channels au SHA testé ; documenter erreurs réelles, sans démarrer les API payantes. | OPS-002, OPS-003, OPS-005 |
| **OPS-007** | P0 | A | **À faire** | À confirmer sur PC | Préparer le chemin microphone et lecture audio | Identifier micro et haut-parleurs, autorisations Windows, FFmpeg/Rubber Band disponible, anti-écho et configuration locale ffplay. | OPS-003, OPS-005 |
| **OPS-008** | P0 | A | **À faire** | À confirmer sur comptes réels | Préparer Discord texte/vocal et DAVE | Vérifier bot, permissions, intents, salon vocal, participants autorisés, réception audio et comptes de test ; sans activer de capture non autorisée. | OPS-005 |
| **OPS-009** | P1 | A | **À faire** | À faire sur PC/Android | Configurer Tailscale Serve privé | Contrôler tailnet, identité propriétaire, HTTPS Serve vers loopback 8766, ACL, Wi-Fi/data et absence de Funnel/port public ; ne pas toucher au VPS trading. | OPS-005 |
| **OPS-010** | P1 | A | **À faire** | À faire sur PC | Installer les dépendances Live2D Web de la PWA | Installer légalement le SDK JS Web hors Git sur D:, vérifier versions Cubism/moc3, assets r20 et accès privé de la PWA. | OPS-002, OPS-009 |
| **OPS-011** | P1 | A | **À faire** | À confirmer sur compte Twitch | Préparer OAuth et authentification Twitch | Vérifier validité des jetons existants, scopes lecture/envoi, compte du bot et rotation ; réautoriser seulement si nécessaire, sans publier de jeton. | OPS-005 |
| **OPS-012** | P1 | A | **À faire** | À confirmer sur PC | Sauvegarder SQLite avant migration ou recette mémoire | Identifier la base privée, sa version, créer une copie protégée avant ouverture en v3 si nécessaire ; ne jamais committer base/ZIP. | OPS-001, OPS-005 |
| **OPS-013** | P2 | Transverse | **À faire** | À recontrôler | Nettoyer les branches déjà intégrées | Vérifier la pointe Git, les PR squash-fusionnées, les commits uniques et l'absence de travail actif ; supprimer seulement les références autorisées et documentées. | OPS-002 |
| **OPS-014** | P2 | Transverse | **À faire** | À analyser | Auditer les branches divergentes | Comparer notamment docs/jade-persistent-memory-identity, feat/turn-conversation-logs et test/intent-all-channels ; conserver ce qui n'est pas intégré. | OPS-002 |
| **OPS-015** | P2 | B | **À faire** | À analyser sur assets | Étudier les redondances artistiques et outils inutiles | Comparer sémantiquement CMO3/KRA/PSD, rapports et générateurs ; tableau garder/archiver/supprimer avec preuves ; aucune purge automatique. | OPS-002 |
| **OPS-016** | P2 | Transverse | **À faire** | À vérifier | Vérifier secrets historiques, LFS, licences et provenance | Contrôler l'exposition éventuelle dans l'historique et les binaires, ainsi que les droits de redistribution. Le dépôt est volontairement public et reste public. | OPS-002 |
| **OPS-017** | P2 | Transverse | **À qualifier** | À décider / clôturer | Réviser les protections de branches et fermer les passations | Soumettre les éventuelles règles Git à décision, vérifier les liens actifs, mettre à jour les fiches de relais et les clôturer une fois les travaux factuellement achevés. | OPS-013, OPS-014 |

## Règle de suivi

**Clôture :** suivre la [Definition of Done officielle](DEFINITION_OF_DONE.md). **Done** n'est autorisé qu'après une passe de vérification explicite et une validation positive par **Codex OU le propriétaire**, les deux autres garanties étant les preuves pertinentes et la traçabilité/intégration requises. La décision indique dans la passation/PR liée : ID(s), validateur, date, version/SHA ou asset, tests observés, limites et livraison. Aucune carte n'a été automatiquement clôturée lors de l'adoption de cette règle.



- **À recetter / à faire** : tâche non clôturée sur le poste ; le code correspondant peut être déjà implémenté.
- **À confirmer / si nécessaire** : vérifier d'abord la réalité matérielle ou la configuration avant de créer un correctif.
- Les résultats sont notés avec le SHA, environnement non sensible, observations, limites, preuve et lien PR ou [passation](../operations/handoffs/README.md) ; aucune donnée personnelle ni jeton.
- Ne pas démarrer de services réels ou d'appels API facturés, modifier le poste ou effectuer une suppression de branche sans la procédure et l'autorisation appropriées.

## Sources de référence

- [Installation](../handbook/INSTALLATION.md)
- [Passation Codex nettoyage](../operations/handoffs/2026-11-16-repository-cleanup.md)
- [Twitch OAuth](../operations/reference/TWITCH-AUTH.md)
- [Maintenance des branches](../handbook/BRANCH_MAINTENANCE.md)

Retour à l'[index opérationnel](README.md). Les [améliorations prospectives](../ameliorations/README.md) restent hors de ce backlog.
