# Recette fonctionnelle du code existant — backlog opérationnel

**Branche :** develop · **Révision :** 18 novembre 2026 · **Type :** REC · **État de référence :** lecture GitHub, pas recette locale.

Ces tâches vérifient sur appareils et services réels des fonctionnalités déjà codées. Elles ne doivent jamais être transformées en développement à refaire par défaut. Une anomalie reproductible génère une carte DEV liée.

Les priorités expriment la valeur de livraison et les dépendances, non un ordre absolu de traitement. **Responsable pressenti :** Codex (modèle ou sous-agent disponible) pour la réalisation sur PC, propriétaire pour les autorisations/comptes et, s'il le souhaite, la validation ; attribution effective à confirmer. **La [DoD officielle](DEFINITION_OF_DONE.md) exige la réalisation, les tests pertinents, l'intégration applicable, la traçabilité et la validation par Codex OU par le propriétaire.** La validation humaine n'est pas obligatoire. La situation initiale ne remplace pas la colonne Statut.

| ID | Prio | Jalon | Statut | Situation initiale | Tâche | Résultat attendu / vérification | Dépend de |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **REC-001** | P0 | A | **À faire** | À faire sur PC | Démarrer Jade entière en une instance | Lancer --all-channels et relever les connexions actives Discord, Twitch, micro, HTTP, PWA et avatar sans choisir de mode. | OPS-004, OPS-006, OPS-008 |
| **REC-002** | P0 | A | **À faire** | [Lecture et réponse écrites **Done**](#validation-propriétaire-du-20-novembre-2026) | Discord écrit et messages privés | Vérifier réception, réponse dans le salon source, mentions, DM, participants observés et rythme solo/groupe 30 % sans divulgation externe. | REC-001 |
| **REC-003** | P0 | A | **À faire** | [Écoute et réponse orales **Done**](#validation-propriétaire-du-20-novembre-2026) | Discord vocal réel | Vérifier capture PCM/DAVE, STT, génération, TTS, changement de canal, autorisations de participants et conversation naturelle. | REC-001, OPS-007 |
| **REC-004** | P0 | A | **À faire** | À recetter | Microphone PC réel | Vérifier transcription, lecture locale, silence de fin de phrase et anti-écho, même lorsque les autres canaux sont actifs. | REC-001, OPS-007 |
| **REC-005** | P0 | A | **À faire** | À recetter | Isolation des sorties et confidentialité | Exercer Discord public/DM, Twitch, micro, HTTP et mobile ; vérifier DEV-004 (aucun sous-titre OBS pour DM, sous-titres publics préservés) ainsi que le mixage audio OBS réel : aucun texte, son, sous-titre ou effet visuel privé hors de son audience autorisée. | REC-001, REC-002, REC-003, REC-004 |
| **REC-006** | P0 | A | **À faire** | À recetter | PCM Discord progressif sous --all-channels | Vérifier PCM progressif et option early speech lorsque activée, premier son utile et absence de dépendance à ffplay pour Discord. | REC-003 |
| **REC-007** | P0 | A | **À faire** | À recetter | Repli WAV et absence de double diffusion | Simuler indisponibilité PCM/streaming et observer repli, annulation et destination ; ne pas payer ni émettre deux fois ; toute fuite observée ouvre un bug DEV. | REC-006, REC-005 |
| **REC-008** | P0 | A | **À faire** | À recetter | Commandes silence/reprise et interruption | Tester silence, arrête, reprends, départ d'un salon et coupure pendant lecture sans réponse fantôme ni écho. | REC-003, REC-004 |
| **REC-009** | P0 | A | **À faire** | À recetter | Arbitrage multi-conversations | Soumettre des messages simultanés, vérifier équité, FIFO de repli, ordre d'un même fil, absence de famine et décisions sous contention. | REC-001 |
| **REC-010** | P0 | A | **À faire** | À mesurer | Latence et coût d'une session réelle | Mesurer STT, IA, TTS, premier audio utile, durée globale, p50/p95, coût des tours et arbitrages, CPU/GPU sur plusieurs canaux. | REC-003, REC-004, REC-009 |
| **REC-011** | P1 | A | **À faire** | À recetter | Voix Étincelle et sept intentions | Écouter en français voix shimmer 1,25x, pitch +2, artefacts DSP, prosodie et variations d'intention ; consigner les défauts. | REC-003, REC-004 |
| **REC-012** | P1 | A | **À faire** | À recetter | Twitch IRC réel | Vérifier OAuth, lecture, envoi, limites de débit, solo/groupe et reconnect, avec droits du compte existant. | OPS-011, REC-001 |
| **REC-013** | P1 | A | **À faire** | À recetter | API HTTP locale authentifiée | Vérifier Bearer, réponse au seul appelant, timeout, comportement avec autres canaux actifs et absence de fuite en public. | REC-001 |
| **REC-014** | P1 | A | **À faire** | [Accès et échange texte **Done**](#validation-propriétaire-du-20-novembre-2026) | PWA Android texte et authentification | Ouvrir l'URL réelle via Serve, identité propriétaire + Bearer, installer depuis Chrome, envoyer et recevoir en conservant la session. | OPS-009, REC-001 |
| **REC-015** | P1 | A | **À faire** | [Micro et réponse audio **Done**](#validation-propriétaire-du-20-novembre-2026) | PWA Android voix et micro | Tester push-to-talk, STT/TTS téléphone, permissions micro, longueur maximale, synchronisation avec la conversation texte. | REC-014 |
| **REC-016** | P1 | A | **À faire** | À recetter | PWA arrière-plan, connexion et réseau mobile | Tester Wi-Fi/4G-5G, reconnexion Serve, page cachée, désactivation capture, abandon sans nouvelle génération facturée ou double réponse. | REC-014, REC-015 |
| **REC-017** | P1 | A | **À faire** | À recetter | TTS mobile désactivé | Valider que l'option Voix coupée empêche réellement une synthèse payante inutile et respecte le mode texte. | REC-014 |
| **REC-018** | P1 | A | **À faire** | À recetter | Avatar r20 Windows en rendu réel | Observer corps/portrait disponible, Idle, bouche, expressions, fermeture, affichage, GPU et continuité du dialogue si fenêtre absente. | REC-001, OPS-002 |
| **REC-019** | P1 | A | **À faire** | À recetter | Avatar Web Android r20 | Observer WebGL/Cubism réel sur smartphone, fond transparent, Idle, bouche, intentions, neutralisation, et compatibilité SDK ; ouvrir DEV-002 si défaut. | OPS-010, REC-014 |
| **REC-020** | P1 | A | **À faire** | À recetter | Variantes d'intention A/B | Provoquer deux réponses pour chacune des sept intentions ; valider 14 variantes faciales/textes, toggle, retour neutre et absence de texte de contrôle prononcé. | REC-018, REC-019 |
| **REC-021** | P1 | A | **À faire** | À recetter | Mémoire SQLite, Core et autobiographie | Contrôler opt-in, conservation des tours, rappel par portée, curation, durabilité, suppression et absence de mémoire pour comptes non consentants. | OPS-012, REC-001 |
| **REC-022** | P1 | A | **À faire** | À recetter | Liaisons des comptes Discord/Twitch avec Goldaj | Tester preuve par code à cible, expiration, refus autre compte, association, déliaison, préservation des historiques et confidentialité. | REC-021, REC-002, REC-012 |
| **REC-023** | P1 | A | **À faire** | À recetter | Résilience des canaux et arrêt propre | Tester déconnexion Discord/Twitch, interruption réseau, redémarrage, arrêt Ctrl+C, nettoyage ressources et absence de tours obsolètes. | REC-001, REC-003, REC-012, REC-014 |
| **REC-024** | P2 | A | **À faire** | À recetter | Seule Démo Express distribuée | Sur Windows graphique, tester installateur, raccourci, lancement sans installation, désinstallation et simulation sans API réelle. | OPS-002, OPS-003 |
| **REC-025** | P1 | A | **À faire** | À recetter | Sauvegarde/restauration et droit à l'effacement | Restaurer SQLite dans une copie privée, vérifier que supprimer/oubli n'efface pas d'autres identités et contrôler les fichiers de logs/archives. | REC-021, OPS-012 |

### Validation propriétaire du 20 novembre 2026

Base de recette réellement déployée sur Windows et Android · develop b4fdd70. Le propriétaire a explicitement validé les entrées et sorties texte et voix des deux canaux. [Confirmation](../history/conversations/2026-11-20-reprise-develop.md#validation-discord-et-mobile).

| Carte | Sous-recette | Statut | Résultat confirmé |
| --- | --- | --- | --- |
| REC-002 | Discord écrit | **Done** | Jade lit les messages et répond par écrit dans le parcours testé. |
| REC-003 | Discord vocal | **Done** | Jade entend la parole et répond oralement dans le vocal testé. |
| REC-014 | PWA Android texte | **Done** | Accès à la PWA privée et échange de messages dans la session testée. |
| REC-015 | PWA Android voix et micro | **Done** | Jade entend la parole depuis le téléphone et l'utilisateur entend la réponse dans la PWA. |

Les lignes correspondantes restent ouvertes pour leurs autres critères. Ce lot ne documente pas les variantes Discord (mentions, MP, cadence et changement de salon), l'installation et la continuité de session sur Android, la limite de capture ou la synchronisation du fil. REC-019 couvre séparément l'avatar.

## Compte-rendu de recette rapide

**Un seul petit tableau par session ou lot**, dans la PR, la fiche de [passation existante](../operations/handoffs/TEMPLATE.md) ou la référence de preuve prévue. **Pas un fichier supplémentaire par test.** Renseigner uniquement les faits observés, puis pointer vers ce compte-rendu depuis la carte lorsqu'elle change de statut.

| ID | Version / environnement | Scénario | Attendu / observé | Verdict | Preuve ou anomalie | Validation et date |
| --- | --- | --- | --- | --- | --- | --- |
| `REC-XXX` | SHA, PC/appareil, version sans donnée sensible | Action concrète | Résultat attendu et résultat observé | OK / KO / Bloqué | Trace expurgée, test/PR ou ID DEV lié | Codex **OU** propriétaire, seulement après passe explicite |

Un « OK » technique ne remplace pas les cinq conditions de la [DoD](DEFINITION_OF_DONE.md) et ne doit pas être attribué à une session réelle si elle n'a pas eu lieu. Un cas KO ouvre si nécessaire une anomalie `DEV` liée ; **la fonction codée reste codée**, seule la recette demeure ouverte. Une validation peut couvrir plusieurs IDs cités avec leur résultat propre.

## Règle de suivi

**Clôture :** suivre la [Definition of Done officielle](DEFINITION_OF_DONE.md). **Done** n'est autorisé qu'après une passe de vérification explicite et une validation positive par **Codex OU le propriétaire**, les deux autres garanties étant les preuves pertinentes et la traçabilité/intégration requises. La décision indique dans la passation/PR liée : ID(s), validateur, date, version/SHA ou asset, tests observés, limites et livraison. Aucune carte n'a été automatiquement clôturée lors de l'adoption de cette règle.



- **À recetter / à faire** : tâche non clôturée sur le poste ; le code correspondant peut être déjà implémenté.
- **À confirmer / si nécessaire** : vérifier d'abord la réalité matérielle ou la configuration avant de créer un correctif.
- Les résultats sont notés avec le SHA, environnement non sensible, observations, limites, preuve et lien PR ou [passation](../operations/handoffs/README.md) ; aucune donnée personnelle ni jeton.
- Ne pas démarrer de services réels ou d'appels API facturés, modifier le poste ou effectuer une suppression de branche sans la procédure et l'autorisation appropriées.

## Sources de référence

- [État de develop](../handbook/BRANCH_STATE.md)
- [Guide utilisateur](../handbook/USER_GUIDE.md)
- [Recette PC et Android](../history/gpt6-jade/HANDOFF-CODEX-MOBILE-20261115.md)
- [Passation PCM/mémoire/mobile](../operations/handoffs/2026-11-16-chatgpt-pcm-memoire-mobile.md)

Retour à l'[index opérationnel](README.md). Les [améliorations prospectives](../ameliorations/README.md) restent hors de ce backlog.
