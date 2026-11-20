# Passations actives entre agents

La procédure est dans [AGENT_COORDINATION.md](../AGENT_COORDINATION.md). **Chaque mission a un document unique** nommé `YYYY-MM-DD-<agent>-<sujet>.md`, rédigé depuis [TEMPLATE.md](TEMPLATE.md). Un agent reprend la mission depuis le fichier et la PR, puis indique son état sur sa branche. Pas de comptes-rendus concurrents dans un fichier géant.

**Pour clore une carte du backlog :** utiliser la [Definition of Done officielle](../../backlog/DEFINITION_OF_DONE.md) et le [modèle de passation](TEMPLATE.md). La validation explicite de **Codex (n'importe lequel de ses modèles ou sous-agents) OU du propriétaire** suffit, après vérification distincte, preuves, intégration applicable et mise à jour du statut dans la vue opérationnelle ; pas de double validation imposée.

## Missions actuelles

- [Rétention des mémoires Jade : 7 jours / 365 jours / Core permanentes](2026-11-20-chatgpt-retention-memoire-7j-365j.md) · Migration SQLite v4, reprise de tous les échanges des 24 dernières heures et purge automatique.

- [**DEV-011 : demandes de souvenirs ordinaires, Core choisies par Jade**](2026-11-20-chatgpt-dev011-ordinary-autonomous-core.md) · Décision du propriétaire du 20/11 remplaçant l'ajout forcé Core ; tests, correctif et recette PC.

- [DEV-011 (historique, remplacée)](2026-11-20-chatgpt-dev011-core-memory-implementation.md) · Ancienne implémentation permettant de forcer une Core, **à ne pas reproduire**.

- [DEV-011 (ancienne demande, annulée)](2026-11-20-chatgpt-core-memory-explicite-p0.md) · Référence historique remplacée par le refus d'écriture Core forcée.

- [Mémoire SQLite par défaut et inscription Discord](2026-11-20-chatgpt-memoire-discord-auto.md) · Inscription automatique des intervenants vérifiés de serveur Discord et effacement durable, sans ouvrir la mémoire aux autres canaux.

- [Retours Discord et lancement PyCharm](2026-11-20-codex-retours-discord.md) · coupures, fin de parole, reconnect et recette REC-023.

- [Dépenses OpenAI et voix mobile progressive](2026-11-20-codex-couts-voix-mobile.md) · UX-18, LAT-06 et LAT-16, branche isolée non intégrée.

- [Reprise du backlog et audit du poste](2026-11-20-codex-audit-ops.md) · DEV-009, OPS-005/006/007/008 et REC-009.

- [Reconnexion du vocal Discord](2026-11-20-codex-reconnexion-vocale.md) · Diagnostic réel, reprise et REC-023.

- [Chambre de Jade dans la PWA](2026-11-20-codex-chambre-mobile.md) · Direction illustrée, étapes de validation et publication.

- [Rendu r20 dans la PWA du 20 novembre](2026-11-20-codex-avatar-mobile-r20.md) · Correctif DEV-002, résultat Chromium et recette Android.

- [Validation et lancement Windows du 20 novembre](2026-11-20-codex-validation-develop.md) · PR #26, lancement Discord, prérequis mobiles, anomalies différées et revue des branches.
- [Quick wins voix/routage/latence du 19 novembre](2026-11-19-chatgpt-quickwins-voice-routing.md) : DEV-003/005–008, preuves et relais de validation.

- [Passation Codex : clôture du rangement develop du 16 novembre](2026-11-16-repository-cleanup.md) : **résidus à effectuer**, tests physiques, revue du modeling, branches fusionnées, droits/provenance et règles explicites. **Le dépôt est volontairement public et doit le rester.**

Les documents clôturés peuvent être déplacés vers [les archives historiques](../../history/README.md) avec mise à jour des liens. Ne pas confondre une note de passation avec la liste des fonctionnalités codées.

- [PCM Discord, identités mémoire et PWA (PR #23)](2026-11-16-chatgpt-pcm-memoire-mobile.md) : correctifs de code et sécurité, tests CI, recette PC/Android non réalisée et reprise par Codex/Terra.
