# Décision de suspension ciblée : microphone PC, Twitch, OBS

**Date :** 21 novembre 2026. **Propriétaire :** validation explicite du report et clarification : « Non pas les cartes qui nécessitent le pc local. Mais les cartes qui utilisent le micro local du pc pour les tests. »

**Interprétation appliquée :** bloquer jusqu'à nouvel ordre les cartes dont la recette complète nécessite le microphone physique **local du PC exécutant Jade**, Twitch ou OBS. **Ne pas bloquer toute carte Windows**. Le micro d'un participant Discord ou le micro Android ne sont pas le microphone local du PC Jade.

**Branche :** develop. **Base avant modification :** `87a117a0969b3dae92385c579d90c8db67bdd449`. **Nature du travail :** modification documentaire de statut, sans test, déploiement ou changement de code.

## Changements de statut

| Carte | Statut avant | Statut après | Motif |
| --- | --- | --- | --- |
| REC-001 | À faire | **Bloqué** | Le scénario complet --all-channels exige Twitch et le micro physique PC; les sous-tests indépendants restent possibles |
| REC-004 | À valider | **Bloqué** | Test du microphone physique du PC, transcription, retour audio et anti-écho |
| REC-005 | À valider | **Bloqué** | Contrôles OBS et mixage de données privées, incluant micro PC et Twitch |
| REC-008 | À valider | **Bloqué** | Recette complète des commandes vocales incluant la voie microphone PC via REC-004; essais Discord seuls possibles |
| REC-010 | À valider | **Bloqué** | Mesures multi-canaux incluant la voie microphone physique du PC; mesures partielles possibles |
| REC-012 | À valider | **Bloqué** | Recette du connecteur Twitch réel |
| REC-022 | À valider | **Bloqué** | Liaison de comptes Twitch restant à tester; liaison Discord déjà validée partiellement |
| REC-023 | À valider | **Bloqué** | Résilience Twitch comprise dans le périmètre; incidents Discord existants conservés et non résolus |
| OPS-005 | À faire | **Bloqué** | Configuration de tous les connecteurs, dont Twitch et micro physique PC; sous-configurations indépendantes possibles |
| OPS-007 | À faire | **Bloqué** | Préparation matérielle du microphone physique du PC, FFmpeg, ffplay et contrôle anti-écho |

**Déjà bloquées, inchangées :** DEV-004 (OBS) et OPS-006 (préflight tous canaux avec Twitch/micro). DEV-001 (dépendance aux assets r21) et DEV-006 (concurrence WebSocket VTube Studio) restent bloquées pour des raisons indépendantes de la présente suspension.

**Non bloquées par principe :** OPS-008/009/010/012 (Discord, Tailscale, SDK mobile, SQLite), REC-002 (Discord écrit/MP), REC-006 (PCM Discord sans microphone physique du PC), REC-020 (variantes A/B), REC-021 (mémoire), REC-024 (installateur Windows graphique), REC-025 (sauvegarde et effacement), les cartes de l'application mobile et les tâches Live2D. Les cartes déjà Done ne changent pas.

**Cartes mixtes :** les sous-scénarios Discord, mémoire et Android peuvent être travaillés séparément, mais aucun succès ni clôture de la carte complète ne doit être inventé, particulièrement pour REC-022 (liaison Twitch restante) et REC-023 (incidents Discord déjà signalés).

**Reprise :** uniquement sur décision explicite du propriétaire ; à ce moment, réévaluer les critères et preuves avant de sortir les cartes du statut Bloqué. L'ancienne règle « REC non automatisable → À valider » demeure applicable aux cartes non suspendues.

**Vérifications :** revue des statuts, périmètres et critères documentaires uniquement ; ni exécution technique ni accès aux périphériques du propriétaire. `main` inchangée.
