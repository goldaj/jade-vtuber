# Instructions du projet Jade

## Références visuelles de l’architecture (develop)

**Référence fonctionnelle prioritaire :** [atlas du 16 novembre 2026](docs/architecture/atlas-fonctionnel-2026-11-16/README.md) et [contrat des décisions et appels](docs/architecture/atlas-fonctionnel-2026-11-16/CONTRAT_FLUX_COMPLET.md). L'atlas comporte cinq vues : boucle, choix par canal, parallélisme, mémoire et sorties/échecs. Les [deux schémas du 15 novembre](docs/architecture/README.md) restent des références historiques d'infrastructure. **Consulter ces documents avant tout changement de flux**, puis vérifier le comportement réel dans le code de la branche et la configuration privée. Toute modification d'architecture ou des politiques de décision impose la mise à jour coordonnée des cinq vues, du contrat et des guides ; aucune illustration ne prévaut sur le code exécuté.

## Maintenance documentaire systématique (règle prioritaire sur develop)

Pour **tout changement de code, dépendance, test, configuration, interface, script ou infrastructure** de cette branche, réviser dans le même commit/PR **chaque guide** : `docs/handbook/INSTALLATION.md`, `DEMO.md`, `USER_GUIDE.md`, `TECHNICAL.md`, `AI_HANDOFF.md`, `BRANCH_STATE.md`, `BRANCH_MAINTENANCE.md`. Mettre également à jour `AGENTS.md`, l'index et les passations spécialisées pertinentes. Le contrôle `scripts/check_docs.py` bloque les PR sans mise à jour. **Ces documents décrivent develop, pas main.** Ne pas recopier des capacités inexistantes sur une branche antérieure. Voir [la règle agents détaillée](docs/handbook/AI_HANDOFF.md), [le manuel](docs/handbook/README.md) et [le nettoyage des branches intégrées](docs/handbook/BRANCH_MAINTENANCE.md). La Démo Express est uniquement simulée, sans OpenAI, micro ni Live2D.


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

## État actuel de la mémoire et du mobile (15 novembre 2026)

Les documents de cadrage des PR #6/#7/#8/#9 restent historiques. Les travaux mémoire SQLite, identité locale Goldaj, conversations Discord unifiées, autobiographie et application mobile PWA ont été intégrés à `develop` via la PR #11. **Ils ne sont pas une installation validée sur le PC de l'utilisateur.** Lire [l'audit transverse](docs/gpt6-jade/AUDIT-TRANSVERSE-20261115.md), puis [la passation mémoire](docs/gpt6-jade/HANDOFF-CODEX-MEMORY-20261115.md). Toute affirmation d'état réel demande une vérification sur le poste.

**Instruction prioritaire pour Codex lorsqu'il sera sollicité pour configurer le PC Jade et le téléphone Android : lire et exécuter le [guide opérationnel Windows + Android](docs/gpt6-jade/HANDOFF-CODEX-MOBILE-20261115.md).** Ce guide contient l'inventaire initial du poste, Git/Poetry/LFS, les fichiers privés, Tailscale Serve sur le PC, le SDK Web Live2D sur D:, le launcher, l'installation PWA Android, les tests de recette et le diagnostic des erreurs. **Ne pas suivre les anciennes consignes de lancer un mode mobile isolé `--live --mobile`.** Le démarrage produit courant est **`main.py --all-channels`**.

La configuration Android exige le compte personnel Tailscale sur les deux appareils, son en-tête d'identité propriétaire et un jeton mobile distinct. Aucune route privée n'est à présumer existante : Codex doit contrôler `tailscale serve status` sur le PC avant création. Pas de Tailscale Funnel public, pas de bind public sur 8766, pas de modification du VPS Hyperliquid. Le modèle Web dépend de binaires JS propriétaires **non versionnés** ; vérifier sa licence et sa compatibilité Cubism avant installation. Le rendu, la prise de parole et les coûts sur téléphone nécessitent une recette réelle.

## Ressources 2D

Conserver les sources et les objets Git LFS. Lire `jade-modeling/MODEL_GUIDE.md`, `jade-modeling/CONTINUATION.md` et les documents de coordination 2D avant de les modifier. Exécuter `python jade-modeling/verify_assets.py` après récupération des objets LFS. Le propriétaire décide du périmètre des travaux visuels et des revues Astra.

## Feuille de route voix et téléphone (3 novembre 2026)

La spécification courante pour l'usage oral naturel de Jade **sans obligation de prononcer son nom**, le MVP Discord avec avatar visible et le futur client mobile audio/vidéo est dans [ROADMAP-MVP-DISCORD-PRODUIT-MOBILE.md](docs/gpt6-jade/ROADMAP-MVP-DISCORD-PRODUIT-MOBILE.md). Codex doit la lire avant tout travail sur Discord vocal, la pertinence conversationnelle, VTube Studio, la sortie audiovisuelle ou l'interface mobile. Elle distingue les fonctions déjà codées de celles qui restent à développer et à recetter ; aucune fusion main automatique.


## Contre-audit transverse des branches Jade (15 novembre 2026)

**Historique :** les PR #6 (mémoire), #8 (Discord unifié), #9 (autobiographie) et #7 (PWA mobile) ont d'abord été revues sur une branche d'intégration avant fusion dans `develop` via la PR #11. Consulter [l'audit transverse](docs/gpt6-jade/AUDIT-TRANSVERSE-20261115.md) pour les réserves initiales, puis appliquer l'[état courant du guide d'installation sur le PC](docs/gpt6-jade/HANDOFF-CODEX-MOBILE-20261115.md). Protéger le contenu privé des logs, ne pas divulguer de DM en vocal, conserver la suppression des souvenirs sur demande. Les tests GitHub ne valent pas une recette matérielle. Ne pas toucher au VPS Hyperliquid ni à `main` sans autorisation explicite.

## Launcher Windows local et arbitrage (15 novembre 2026)

Launcher PR #13 puis correction **PR #14 fusionnée dans `develop`** : [guide launcher](docs/gpt6-jade/LAUNCHER-WINDOWS-20261115.md). Installation hors dépôt dans `D:\Jade\launcher`, branche distante au choix, fast-forward sans écrasement, Poetry/LFS obligatoires, préflight et lancement **de tous les supports en une seule instance** via `--all-channels`. Aucun choix de mode. Le runtime Jade arbitre les demandes en attente sans priorité permanente par plateforme. Ne pas diffuser les réponses locales privées dans Discord/OBS. **Rejouer `Installer-Launcher-Jade.cmd` après mise à jour du launcher**, puis réaliser la recette physique guidée par la [passation Windows + Android](docs/gpt6-jade/HANDOFF-CODEX-MOBILE-20261115.md). `main` reste inchangée sans autorisation.

## Nouveau lot Live2D intentions : deux variantes immédiates et 14 animations futures (15/11/2026)

**À lire par Codex/Terra avant tout travail sur le modèle 2D :** [LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md](docs/gpt6-jade/LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md). `develop` vise la synchronisation `Reply.intent` → deux expressions faciales r20 et deux libellés textuels distincts par intention, sur PC et PWA, via le même contrat `intent-visuals.json`. Toggle global `JADE_AVATAR_INTENT_ENABLED` (par défaut activé) sans affecter la voix ou la bouche. **Exigence du propriétaire : créer, à terme, 14 animations Live2D dédiées et distinctes**, deux pour chacune des sept intentions, sur le modèle 2D intégral en pied validé. Les nouveaux motions/SDK non testés ne doivent pas être connectés prématurément. Le r21 en pied reste une référence artistique, pas un rig animé final. Compléter les tests et les guides sur chaque branche concernée et ne jamais confondre le code prévu avec le rendu matériel recetté.

## Décisions produit du 2026-11-15 — prompt validé et comportement

Lire [la passation dialogue](docs/gpt6-jade/DIALOGUE-LOW320-HISTORIQUE-PARTICIPATION-20261115.md) avant de modifier le runtime. Le prompt actif `prompt_chat.txt` est la formulation exacte approuvée par Goldaj ; ne pas réécrire les phrases, même pour « corriger » le style. Les trois propositions historiques sont conservées comme archive et n'ont plus vocation à être activées. Ne pas modifier `INTENT_PROMPT` sans demande.

Contrat : `gpt-6-luna` + `low` + plafond 320 par défaut, sauf variables privées ; persistences des échanges complets strictement opt-in, conservation sans résumé, 48 messages de contexte au maximum, archivage local plus long, suppression associée au profil. Politique tête-à-tête observé (100 %) et groupe (30 % sur tours admissibles) selon le canal ; garder les réponses directes/commandes, les gardes de sécurité, la politique de confidentialité et la gestion des silences.

Deux réactions 2D par intention sont **planifiées**, mais aucune animation supplémentaire n'est fournie par ce chantier. Ne pas assimiler une intention existante ou un emplacement documentaire à une animation validée. Mettre à jour les guides de cette branche, exécuter les tests et réaliser les recettes réelles avant de déclarer la fonction opérationnelle.

## Portes DevOps de develop (15/11/2026)

Pour toute intervention sur la CI, le launcher ou les sauvegardes, consulter [l'audit DevOps et la passation Codex](docs/gpt6-jade/AUDIT-DEVOPS-DEVELOP-20261115.md). Un scan de secrets vert ne remplace pas une suite complète Ubuntu/Windows verte sur le SHA final, et les tests simulés ne sont pas une preuve de recette Discord/Twitch/Android. Le format de transfert SQLite accepte v1/v2/v3 tout en restant non chiffré. Documenter séparément tout accès matériel indisponible et **ne pas** contourner un test en échec.

## Contrôle P0 CI du 16 novembre 2026 (develop)

- Politique de réponse conservée : **100 % en solo vérifié, 30 % en groupe** ; sollicitation explicite prioritaire. Les suivis contextuels en groupe restent échantillonnés et ne garantissent pas une réponse.
- Tests de transport Discord vocal : échantillonnage neutralisé **dans les doubles de test seulement** pour vérifier indépendamment déplacement de canal, interruption et récupération. La présence des participants est une information en lecture seule permettant de distinguer solo/groupe, jamais une autorisation d'écoute.
- Tests Discord écrit : salons à plusieurs participants simulés explicitement pour vérifier le taux et les limites de réponses, sans supprimer la réponse automatique en salon solo.
- Twitch : le test de non-empilement des réponses initialise le participant que l'adaptateur IRC observe normalement. Aucun changement de comportement de production dans ce lot.
- Vérification GitHub Actions Windows/Ubuntu, export de publication, scripts PowerShell et scan de secrets indispensable avant toute affirmation de CI verte. Aucun test vocal matériel ni appel OpenAI réalisé par cette revue.

- Correctif Windows du test IPC Live2D : la simulation valide toujours les deux trames d'expression et de bouche, puis termine par une coupure de pipe contrôlée. L'attente auparavant non bornée du faux moteur était responsable d'annulations Windows au délai de huit minutes ; aucun runtime ni test réel de Live2D n'est remplacé.

## Passation réconciliation develop, 16 novembre 2026

Consulter [l'audit de raccordement code/configuration/docs](docs/gpt6-jade/RECONCILIATION-CODE-CONFIG-DOCS-20261116.md) avant de déclarer une fonctionnalité réellement prête sur le PC. Il confirme les PR #18/#19/#20 fusionnées et sépare preuve CI, branche Git et validation matérielle. `main` reste une branche fonctionnellement différente malgré son ascendance désormais partagée avec `develop`.
