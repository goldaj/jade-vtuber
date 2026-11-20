# Instructions du projet Jade — develop

## Point d'entrée et gouvernance documentaire

**Toute intervention d'agent, Codex (ses modèles Terra/Astra/Sol et ses sous-agents) ou ChatGPT en mode chat, commence par ce fichier**, puis lit [le centre opérationnel](docs/operations/README.md) et [les règles de collaboration](docs/operations/AGENT_COORDINATION.md). Le [journal des modifications](docs/operations/CHANGELOG.md) consigne chaque changement technique. Les échanges entre agents sont écrits dans `docs/operations/handoffs/`, avec une fiche **par mission**, puis référencés dans la PR ; jamais dans un rapport historique pris pour un ordre courant.

## Sources de vérité et décisions du propriétaire

**Le code de la branche consultée définit les fonctionnalités existantes.** Si un module est intégré et raccordé au runtime, le considérer comme implémenté. Les tests/recettes relèvent de l'assurance qualité et ne créent pas un deuxième statut fonctionnel. Les variables privées peuvent modifier le comportement du poste.

- **[État du code de develop](docs/handbook/BRANCH_STATE.md)** : liste canonique des fonctions et limitations.
- **[Manuel et guide technique](docs/handbook/README.md)** ; [atlas des décisions et appels](docs/architecture/atlas-fonctionnel-2026-11-16/README.md) et [contrat de flux](docs/architecture/atlas-fonctionnel-2026-11-16/CONTRAT_FLUX_COMPLET.md) (instantanés datés à confronter au code).
- **[Backlog opérationnel priorisé](docs/backlog/README.md)** : **source de vérité pour les travaux et recettes en attente**, quatre vues (DEV/REC/OPS/ART), jalons A/B, dépendances et statuts de travail. **Lors d'une nouvelle session Codex, consulter d'abord la section « Reprise prioritaire » en tête du backlog**, puis vérifier les statuts canoniques et les dépendances.
- **[Definition of Done officielle](docs/backlog/DEFINITION_OF_DONE.md)** : règle obligatoire avant de mettre une carte en **Done** : réalisation, tests/preuves, validation positive par **Codex OU le propriétaire**, intégration applicable et traçabilité. Ni double validation, ni accord humain systématique. La validation Codex est une passe distincte de la réalisation.
- **[Catalogue des améliorations futures](docs/ameliorations/README.md)** : idées prospectives distinctes, non engagées automatiquement comme tâches du backlog opérationnel.
- [Archives et index des conversations](docs/history/conversations/INDEX.md) : contexte historique, pas des ordres d'exécution actuels.

**Décision générale maintenue, avec exception du 19 novembre :** Goldaj a explicitement autorisé les quick wins DEV-003/005–008 avant les recettes PC ; les autres idées restent différées ; le backlog **opérationnel** créé le 18 novembre organise au contraire installation, recette, modèle r21 et maintenance déjà attendues. Ne pas engager de développement à partir du catalogue prospectif sans nouvelle demande ; la création du backlog opérationnel n'autorise pas à elle seule l'exécution de ses tâches ni des appels facturés. Le routage exclusivement par canal source, le préchargement mémoire, la visibilité conditionnelle de l'avatar et le moteur Realtime sans Luna sont des objectifs **non intégrés**. Luna reste le modèle configuré par défaut dans le code actuel.

## Branches, poste et confidentialité

- Travailler sur `develop` pour les changements autorisés ; pas de merge sur `main` sans autorisation explicite et renouvelée. Ne pas effacer ou écraser les travaux locaux de Terra/Codex. Ne pas copier les documents de develop tels quels sur main.
- Sur le PC du propriétaire, conserver dépôt, outils, modèles, caches et temporaires sur **D:**, en préservant fichiers uniques et checkpoints. En phase de tests, lancer Jade depuis PyCharm ; pour la production, utiliser un lancement autonome. Le launcher est installé séparément du dépôt et se réinstalle quand ses scripts changent.
- Ne jamais publier secrets, configuration privée, mémoire SQLite, transcriptions ou captations audio. La configuration privée est sélectionnable avec `JADE_SECRETS_FILE`. Ne pas activer de connecteurs, microphones ou appels facturés sans autorisation.
- Mobile privé uniquement par Tailscale Serve et identité propriétaire + Bearer ; **pas de Funnel public**, pas d'exposition LAN, pas d'utilisation/modification du VPS Hyperliquid.
- Préserver les identités vérifiées, la conservation annoncée aux membres Discord, l'activation manuelle sur MP/Twitch, le refus de réinscription après effacement, l'isolement des sessions et la suppression de mémoire. Les entrées privées PC/mobile/HTTP et les MP ne doivent pas sortir en Discord/Twitch/OBS public.

## Runtime codé sur develop

- `main.py --all-channels` lance ensemble les connecteurs configurés, sans sélecteur de mode. `TurnArbiter` arbitre les conversations en attente et le worker principal reste séquentiel.
- Discord écrit/vocal et Twitch IRC sont intégrés. Solo humain observé : réponse aux tours admissibles ; groupe : intervention spontanée échantillonnée à 20 % sur Discord et 30 % sur Twitch, interpellations directes prioritaires. Twitch refuse d'empiler un second message pendant un tour en cours.
- Mémoire SQLite v3 activée par défaut en mode réel, curation activée, fichier privé hors Git ; inscription automatique des membres identifiés d'un serveur Discord à la première interaction traitée, opt-out persistant, activation manuelle sur MP/Twitch ; profil Goldaj partagé par micro PC et mobile authentifié ; historique complet en base avec fenêtre récente bornée ; conversation Discord voix/chat natif du même vocal unifiée par compte et session.
- **Décision propriétaire DEV-011 du 20/11/2026 :** une demande naturelle d'enregistrer un souvenir, même si elle nomme les « Core Memories », crée **uniquement** un souvenir ordinaire (`kind=ordinary`) dans la portée autorisée ; **ni Goldaj ni un tiers ne peut imposer, créer, promouvoir ou sélectionner directement une Core Memory**. Seule la curation autonome de Jade décide `core_self`/`core_relationship` en dehors des instructions utilisateurs. Maintenir les commandes privées de lecture et d'effacement pour les droits des personnes, sans ajout forcé.
- Réponses vocales OpenAI ; voix `shimmer` 1,25×, pitch +2 via FFmpeg Rubber Band quand disponible. Intention `[INTENT:...]` filtrée. **Deux réactions faciales r20 et deux textes PWA par chacune des sept intentions** codés ; **14 motions corporelles originales** et rig r21 final à créer.
- PWA Android privée : texte, prise de parole WAV, TTS mobile, avatar Web sous SDK compatible. Le duplex temps réel n'est pas codé.
- Streaming PCM Discord disponible sous conditions : `--all-channels` conserve `ffplay` pour le microphone PC, mais le PCM de Discord vocal l'utilise désormais indépendamment. Le mode par phrases reste opt-in, le fallback WAV Discord vocal n'utilise plus la sortie locale et les écrits Discord/Twitch/HTTP ne déclenchent plus de TTS. Le routage complet des rendus par audience reste à construire.

## Validation du backlog opérationnel

Pour toutes les cartes **DEV, REC, OPS, ART** : appliquer la [DoD officielle](docs/backlog/DEFINITION_OF_DONE.md) et renseigner le **statut dans la vue thématique**, pas dans l'index des priorités. Une validation explicite de **Codex (quel que soit modèle/sous-agent)** **OU du propriétaire** suffit. Une conversation ChatGPT en mode chat ne vaut pas validation Codex implicite. Un agent auteur peut faire une passe de vérification distincte ; contre-revue indépendante conseillée, non systématique. Tests physiques déclarés réussis uniquement s'ils ont été réellement observés. Les validations peuvent couvrir un lot de cartes nommées avec preuves par ID ; la présence du code ou la CI seule ne clôture pas une tâche de recette.

Pour une carte en **À valider**, relier les preuves et la décision du validateur à une PR ou [passation](docs/operations/handoffs/TEMPLATE.md) avant **Done**. Si la carte conditionnelle est sans objet, classer sans suite avec justification au lieu d'inventer un correctif. `main` reste inchangée sans accord explicite.

## Commits et exécution sans surcharge

**Privilégier un commit cohérent par lot de travail** incluant ses fichiers de code, ses tests pertinents et les documents impactés ; éviter les commits séquentiels artificiels « un fichier = un commit » qui annulent inutilement des CI. Garder plusieurs commits lorsque de véritables étapes indépendantes ou des travaux concurrents le justifient ; ne jamais réécrire l'historique publié juste pour regrouper des commits. Viser au plus trois tâches réellement actives simultanément et consulter le [focus du backlog](docs/backlog/README.md#focus-de-travail-léger-limite-indicative--3-tâches-réellement--en-cours-) sans calendrier cérémoniel imposé.

## Maintenance et passation

Avant modification, consulter les sources du domaine, [AI_HANDOFF](docs/handbook/AI_HANDOFF.md) et la [passation active de la mission](docs/operations/handoffs/README.md). **Les passations historiques suivantes sont des références complémentaires à lire seulement si le sujet le justifie, pas des instructions en vigueur :** [voix](docs/history/gpt6-jade/HANDOFF-CODEX-VOICE-INTENTS-20261113.md), [mémoire](docs/history/gpt6-jade/HANDOFF-CODEX-MEMORY-20261115.md), [Discord](docs/history/gpt6-jade/HANDOFF-DISCORD-UNIFIED-20261115.md), [PC/Android](docs/history/gpt6-jade/HANDOFF-CODEX-MOBILE-20261115.md), [Live2D](docs/history/gpt6-jade/LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md), [DevOps](docs/history/gpt6-jade/AUDIT-DEVOPS-DEVELOP-20261115.md).

Pour toute modification **technique** (code, configuration, dépendances, scripts, assets, workflow), mettre à jour **un seul document imposé par la CI** : [`docs/operations/CHANGELOG.md`](docs/operations/CHANGELOG.md), avec la justification, les fichiers concernés, les risques et les vérifications. Examiner ensuite les guides et schémas du domaine : **modifier seulement ceux réellement impactés**. `BRANCH_STATE.md` reste la source de vérité fonctionnelle lorsque le comportement change ; `AGENTS.md` seulement lorsque les règles changent. Les tests seuls et les archives documentaires ne forcent pas une réécriture des guides. Voir [`scripts/check_docs.py`](scripts/check_docs.py) et [règles de collaboration](docs/operations/AGENT_COORDINATION.md).

Préserver les assets Git LFS et leurs droits (`python jade-modeling/verify_assets.py`). La compilation et les tests (`python -m unittest discover -s tests -v`, `python -m compileall -q src main.py`) servent aux contrôles de changement ; leur exécution ne modifie pas à elle seule le statut d'une fonction déjà présente dans le code.
