# Instructions du projet Jade

Avant toute modification, lire [l’index des conversations](docs/conversations/INDEX.md), puis les instructions de cette page et les documents liés au domaine concerné. Le journal est partiel : conserver les décisions successives, distinguer verbatim et résumé et ne jamais y copier de secrets, identifiants privés ou sorties brutes d’outils.

## Dépôt et configuration

Ce dépôt rassemble le moteur et les sources de Jade. Respecter les branches et le travail existants ; vérifier l’état du dépôt avant toute modification. Les anciennes instructions sont conservées à titre historique dans [l’archive](docs/archives/AGENTS-avant-nouveau-depot.md).

Les travaux hors production se font sur `develop` dans ce dépôt public. `main`
reste la branche destinée aux versions de production ; son existence ne signifie
pas qu’une production est déjà active. Les changements validés de `develop` ne
sont fusionnés dans `main` que sur demande explicite du propriétaire, à renouveler
pour chaque fusion. Il a demandé la fusion après la présente vérification et le
redéploiement ; les prochains travaux se poursuivront sur `develop`.

La contre-revue Astra du dépôt public est consignée dans le
[rapport de reprise Terra](docs/migration/2026-11-02/08-ASTRA-CONTROLE-DEPOT-PUBLIC.md).
Les consignes de relais de cette revue sont historiques ; appliquer les
instructions courantes du paragraphe Runtime ci-dessous pour la reprise actuelle.

Ne jamais committer de secrets, fichiers de configuration privés, enregistrements ni transcriptions. La configuration privée est externe au dépôt et peut être sélectionnée avec `JADE_SECRETS_FILE`. Ne pas divulguer son contenu. Ne pas activer de connecteur, microphone ou appel payant sans demande explicite.

Pour Jade, l'utilisateur demande désormais de travailler intégralement sur `D:` : dépôt Git local, fichiers de travail, modèles, outils, caches et temporaires. Ne pas utiliser `C:` comme espace de travail ni maintenir son ancien chemin comme référence ; migrer uniquement les éléments utiles qui ne sont pas déjà sur `D:`, après vérification. Préserver les données uniques, les checkpoints utiles, les autres services et tout travail simultané. Cette consigne actualise la préférence historique de compatibilité `C:` figurant dans les anciens journaux.

## Runtime

La revue MVP du 10 novembre et le relais courant sont dans
[ASTRA-REVUE-MVP-20261110.md](docs/gpt6-jade/ASTRA-REVUE-MVP-20261110.md).
Cette revue est terminée. Le propriétaire a ensuite autorisé Astra à résoudre
la panne DAVE et confirmé la réponse vocale réelle. Le relais courant est le
[plan de réduction de latence](docs/gpt6-jade/PLAN-LATENCE-20261110.md). Le
propriétaire a demandé sa réalisation sous Terra puis un lancement local pour
ses essais Discord sur téléphone. Le partage vidéo et les nouveaux résultats
doivent être confirmés par une recette réelle ; ne pas les déclarer validés à
partir des seuls tests simulés.

Python ; STT et TTS OpenAI uniquement ; dialogue interchangeable. Par défaut, la démo et les tests restent hors ligne. La validation repose sur `python -m unittest discover -s tests -v` et `python -m compileall -q src main.py`. Distinguer les tests simulés des essais réels. Consigner les résultats observés et leurs limites dans `docs/gpt6-jade/TASKS.md`.

## Passation actuelle voix Étincelle et moteur d'intentions (13 novembre 2026)

**Codex/Terra : lire avant toute retouche du dialogue, du TTS, de Discord vocal ou de la configuration de voix** : [HANDOFF-CODEX-VOICE-INTENTS-20261113.md](docs/gpt6-jade/HANDOFF-CODEX-VOICE-INTENTS-20261113.md), puis [spécification](docs/gpt6-jade/VOICE-PROFILES-20261113.md) et [audit PO/architecture/QA/audio](docs/gpt6-jade/REVIEW-INTENT-ETINCELLE-20261113.md). Ces trois documents priment sur les anciennes valeurs vocales historiques figurant dans HANDOFF.md / TASKS.md / ROADMAP.

Sur `develop`, Étincelle est le **défaut public** (`shimmer`, 1,25×), Friponne et Rosée restent des alternatives documentées. Le LLM produit un seul préfixe strict `[INTENT:label]` ; le module `src/jade_runtime/intent_engine.py` le supprime du texte affiché, lu et mémorisé et fournit une direction vocale **statique autorisée**. Les sept intentions sont **candidates à valider à l'écoute** ; ne pas les qualifier de capacités acoustiques garanties par OpenAI. Le filtre PCM de pitch +2 demi-tons est désormais intégré **sous réserve que FFmpeg dispose de rubberband** ; vérifier sa présence et sa latence selon [la passation DSP](docs/gpt6-jade/PITCH-SHIFT-ETINCELLE-20261113.md). Les variables privées/locales peuvent remplacer les défauts Git.

CI Windows/Linux réussie en simulation : la **recette réelle** voix/Discord/téléphone, les coûts et la latence restent à confirmer. Ne pas toucher à `main` ni écraser les travaux locaux Terra pour « synchroniser » le dépôt.

## Prochain chantier documenté : mémoire persistante, identité et Core Memories

**Cadrage uniquement, non codé :** [plan mémoire et relations](docs/gpt6-jade/PLAN-MEMOIRE-PERSISTANTE-IDENTITES-CORE-20261115.md). Le propriétaire souhaite que Jade reconnaisse les personnes à l'aide des identifiants de plateformes et décide elle-même quand un événement devient une Core Memory. Les Core de Jade et les Core relationnelles ne subissent aucune purge automatique ; les droits de correction, de déliaison et de suppression sur demande restent obligatoires. Avant de développer ce chantier, lire le plan, vérifier les changements des autres branches, préserver le prompt et les contrats d'intention et ne pas écrire de données privées dans le dépôt public.

## PR en cours : développement de la mémoire persistante (15 novembre 2026)

**À lire en priorité pour Codex :** [passation du code SQLite, activation et migration de PC](docs/gpt6-jade/HANDOFF-CODEX-MEMORY-20261115.md). La branche `feat/jade-persistent-memory-core-20261115` est une PR séparée vers `develop` ; ne pas la confondre avec la spécification initiale non codée. Le développement inclut l'identité stable, le micro local attribué à Goldaj, des Core Memories non purgées, une mémoire opt-in et des exports/imports SQLite. Aucun poste local ni compte réel testé. **Conversation Discord écrite et vocale en parallèle : spécification Codex uniquement**, pas de fusion des historiques dans cette PR ; voir [idée de conversation unifiée](docs/gpt6-jade/IDEE-CONVERSATION-UNIFIEE-20261115.md). Ne pas modifier main automatiquement.

## Développement en PR : appli mobile privée Jade (15 novembre 2026)

**Codex/Terra :** [passation mobile du 15 novembre](docs/gpt6-jade/HANDOFF-CODEX-MOBILE-20261115.md). Branche `feat/jade-private-mobile-pwa-20261115`, PR indépendante vers `develop`, ni déployée sur le PC ni fusionnée en production. Le client PWA réservé à Goldaj (créateur/père) utilise `--mobile` et `127.0.0.1:8766` derrière Tailscale Serve **sur le PC**, sans changement des services VPS Hyperliquid. Deux entrées `mobile/text` et `mobile/voice` partagent un historique de session ; le SDK Cubism Core propriétaire et les bundles Pixi sont installés **sur D: hors Git** après vérification de licence. **Le rendu Live2D, le micro mobile et les coûts réels nécessitent la recette Android/Windows.** Le rapprochement avec la mémoire personnelle de la PR #6 reste à faire après fusion consciente des branches.

**Contre-audit du 15 novembre :** [contre-audit mobile + mémoire, correctifs et gates réels](docs/gpt6-jade/AUDIT-REVUE-MOBILE-MEMOIRE-20261115.md). Le backend vérifie maintenant `JADE_MOBILE_OWNER_LOGIN` dans l'en-tête de Tailscale Serve pour toutes les routes, les captures sont abandonnées en arrière-plan, et une voix mobile coupée ne facture pas de TTS. Le code n'est pas recetté sur Android : SDK Cubism 3/4 versus 5 à contrôler, fusion PR #6/#7 manuelle obligatoire.

## Ressources 2D

Conserver les sources et les objets Git LFS. Lire `jade-modeling/MODEL_GUIDE.md`, `jade-modeling/CONTINUATION.md` et les documents de coordination 2D avant de les modifier. Exécuter `python jade-modeling/verify_assets.py` après récupération des objets LFS. Le propriétaire décide du périmètre des travaux visuels et des revues Astra.

## Feuille de route voix et téléphone (3 novembre 2026)

La spécification courante pour l'usage oral naturel de Jade **sans obligation de prononcer son nom**, le MVP Discord avec avatar visible et le futur client mobile audio/vidéo est dans [ROADMAP-MVP-DISCORD-PRODUIT-MOBILE.md](docs/gpt6-jade/ROADMAP-MVP-DISCORD-PRODUIT-MOBILE.md). Codex doit la lire avant tout travail sur Discord vocal, la pertinence conversationnelle, VTube Studio, la sortie audiovisuelle ou l'interface mobile. Elle distingue les fonctions déjà codées de celles qui restent à développer et à recetter ; aucune fusion main automatique.


## Contre-audit transverse des branches Jade (15 novembre 2026)

Après les PR #6 (mémoire), #8 (Discord unifié), #9 (autobiographie) et #7 (PWA mobile), consulter **[AUDIT-TRANSVERSE-20261115.md](docs/gpt6-jade/AUDIT-TRANSVERSE-20261115.md)** avant toute reprise. La branche d'intégration `review/jade-mobile-memory-integration-20261115` vérifie les quatre lots sans déploiement. Protéger le contenu privé des logs, ne pas divulguer de DM dans le vocal, conserver les garde-fous de suppression des souvenirs et comparer les SHA des PR avant fusion. Les tests GitHub n'équivalent pas aux essais matériels. Ne pas toucher au VPS Hyperliquid ni à `main` sans nouvelle autorisation du propriétaire.
