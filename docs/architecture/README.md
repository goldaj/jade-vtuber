# Schémas de référence de l'architecture de Jade

**Extension du 26/11, intégrée sur `develop` depuis `90ec0c7` puis corrigée selon la décision propriétaire :** [Live mobile raccordé](LIVE_MOBILE.md) décrit WebRTC/sideband, baux, suivi d'usage passif, délégations et journal commun. Live est activé par défaut sur mobile, sans plafond financier ; la future politique mensuelle 50/40 EUR concerne seulement Discord. Les paroles natives Live sont concurrentes ; leurs opérations backend passent par le worker/arbitre classique. Cette extension datée complète les instantanés historiques sans prétendre qu’elle était présente dans leur SHA ; sa recette réelle reste ouverte.

## Nouvelle référence fonctionnelle : atlas du 16 novembre 2026

**Priorité pour la compréhension du comportement sur `develop` :** [Atlas de la boucle fonctionnelle complète](atlas-fonctionnel-2026-11-16/README.md) et [contrat détaillé](atlas-fonctionnel-2026-11-16/CONTRAT_FLUX_COMPLET.md).

Les cinq vues corrigées et compactes décrivent les décisions d'acceptation par canal, l'arbitrage, les allers-retours vers les services IA/STT/TTS, les traitements simultanés, la mémoire différée, les sorties et les exceptions. Elles sont datées du 16 novembre 2026 et fondées sur `develop` au commit `a841628b`. Elles sont **documentaires**, sans validation de la configuration privée ni de la recette du PC.

- [1. Boucle principale](atlas-fonctionnel-2026-11-16/01_boucle_maitre.svg)
- [2. Décisions par canal](atlas-fonctionnel-2026-11-16/02_decisions_canaux.svg)
- [3. Parallélisme et voix](atlas-fonctionnel-2026-11-16/03_parallelisme_voix.svg)
- [4. Mémoire et identités](atlas-fonctionnel-2026-11-16/04_memoire_et_identites.svg)
- [5. Sorties et exceptions](atlas-fonctionnel-2026-11-16/05_sorties_et_exceptions.svg)

Les **deux schémas du 15 novembre** sont conservés ci-dessous à titre historique. En cas de divergence, consulter le code exécuté, puis actualiser l'atlas, le contrat et les guides correspondants.

Les deux schémas historiques ci-dessous ont été fournis par le propriétaire le **15 novembre 2026** et sont conservés dans cette branche `develop` comme **références visuelles pour les agents IA et les contributeurs**. Leur perspective est complémentaire : le premier détaille la chronologie des appels ; le second localise les composants par machine et service.

## 1. Architecture et flux d'appels

![JADE — Architecture et flux d'appels : sources, connecteurs, noyau, sorties, mémoire, chronologie](jade-architecture-flux-appels-2026-11-15.png)

Fichier : [jade-architecture-flux-appels-2026-11-15.png](jade-architecture-flux-appels-2026-11-15.png)

Cette figure illustre le trajet habituel : entrée sur un support, politique de sélection et transcription STT si nécessaire, normalisation en `Incoming`, file de `Runtime`, arbitrage des demandes concurrentes, éventuelle lecture mémoire, `Dialogue`/OpenAI, analyse de l'intention, `Reply`, distribution texte/audio/visuel et éventuelle curation.

## 2. Infrastructure et emplacement des composants

![Jade — Architecture et infrastructure complète : PC Windows, mobile Android, Twitch, Discord, OpenAI, Tailscale, GitHub, OBS et stockage](jade-infrastructure-complete-2026-11-15.png)

Fichier : [jade-infrastructure-complete-2026-11-15.png](jade-infrastructure-complete-2026-11-15.png)

Cette figure situe les responsabilités du **PC de Jade**, de la PWA Android, des services externes, du noyau Python, des connecteurs, du rendu Live2D et des données locales.

## Règle d'interprétation obligatoire

**Ces PNG sont des vues de référence datées, pas la source de vérité du produit.** Ils ont été élaborés à partir du code de `develop` au 15 novembre 2026, notamment à partir du moteur du commit `aea51174`. Ils peuvent simplifier certaines connexions ou devenir obsolètes après des modifications. Lorsqu'une illustration et le runtime divergent, **le code et les réglages de la branche courante prévalent**.

En particulier :

- **Arbitrage** : `TurnArbiter` ne sollicite le modèle que s'il existe plusieurs conversations en attente et si aucun mécanisme de repli/équité ne suffit ; ce n'est pas un appel systématique sur chaque message.
- **Voix/STT** : les chemins audio font une transcription avant la normalisation des messages de dialogue ; tous les messages ne passent pas par STT ni par TTS.
- **Mémoire** : l'activation et la curation sont conditionnelles ; une commande mémoire peut répondre sans appel LLM de dialogue. La curation est une tâche ultérieure, pas une étape bloquante de chaque tour.
- **Twitch/OBS** : le connecteur Twitch du dépôt lit et répond au **chat IRC**. Les éléments de vidéo du stream passent par une composition OBS externe, non par un encodeur RTMP interne à Jade. Le fichier de sous-titres texte n'est pas aligné mot à mot.
- **Rendu** : l'avatar Live2D autonome et VTube Studio constituent deux voies différentes ; VTube Studio reste optionnel. La PWA possède son rendu Web local au navigateur.
- **Confidentialité** : les réponses privées micro/HTTP/mobile ne doivent pas être réémises automatiquement vers Discord, Twitch ou OBS. La configuration privée du PC peut surcharger les modèles, les voix et les réglages affichés dans les images.

### Lecture avant toute évolution

Consulter [AGENTS.md](../../AGENTS.md), le [guide technique](../handbook/TECHNICAL.md), le [guide de passation des agents](../handbook/AI_HANDOFF.md), puis vérifier impérativement `main.py` et les modules exécutés (`src/jade_runtime/`). Si l'architecture change, **réviser les images et leurs légendes**, et maintenir les documents synchronisés dans **la branche concernée**, sans recopier la description de `develop` sur `main`.

Les deux PNG sont ajoutés tels que fournis, sans retouche. Aucun secret ni donnée privée du runtime ne doit être placé dans ce dossier.

## Flux de voix et de rendu sur develop

- Le dialogue classique transmet `Reply.intent` après filtrage. L’avatar autonome Windows reçoit une expression. La PWA applique une pose et un mouvement A/B du r21.
- Sur le GPT-Live natif, Jade parle directement et l’avatar estime le geste à partir des premiers mots de sa réponse. En délégation, le pont transmet l’intention du dialogue. [Architecture Live mobile](LIVE_MOBILE.md)
- Discord Live partage le contexte de Jade et utilise son propre transport audio, avec repli vers le moteur vocal classique selon les réglages et la disponibilité. [Architecture Discord Live](DISCORD_LIVE.md)
- Le r21 mobile dispose de neuf intentions et dix-huit mouvements. DEV-001 suit l’autonomie du r21 au démarrage Windows. Les schémas ci-dessus restent des repères datés. [État courant](../handbook/BRANCH_STATE.md)
