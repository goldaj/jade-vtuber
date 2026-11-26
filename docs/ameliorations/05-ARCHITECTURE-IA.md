# Architecture conversationnelle légère et extensible

**Décision produit actuelle : pas de Luna pour le MVP.** Jade doit mener des conversations simples rapidement. Préparer **les points d'extension** d'un moteur de réflexion avancé sans exécuter, facturer ou imposer son intégration maintenant. L'existant reste opérationnel tant que la refonte n'est pas recettée.

| ID | Priorité / état | Amélioration proposée / condition de réussite |
| --- | --- | --- |
| ARC-10 | P3 / D | **Luna ultérieurement** : décision de délégation sur besoin prouvé, travaux parallèles, injection de résultat vérifié, gestion d'attente sans mensonge. Ne pas activer ni optimiser ce composant aujourd'hui. |
| ARC-11 | P3 / D | **Moteur IA local éventuel** : évaluer selon matériel réel, latence, mémoire, qualité française et coûts avant de changer les services OpenAI ; pas de promesse de compatibilité sans benchmark PC. |


**Transfert du 25/11, précisé le 26/11 :** ARC-01 et ARC-05 sont reprises dans le [plan Live mobile](../backlog/PLAN-LIVE-MOBILE.md), avec DEV-040 pour la bascule et DEV-046..051 pour le socle, le pont Jade et les contrôles. Le classique est conservé ; aucun moteur écrit Live ni adaptateur Discord n’est engagé. Un paramètre Discord OFF prépare son futur raccordement. Les ID historiques ne sont pas réattribués.

## Extension produit du 18/11/2026 : modularité généralisée

**Ambition du propriétaire :** l'architecture entière de Jade doit être **ultra modulaire**. Il ne suffit pas d'échanger le LLM : **toutes les API, toutes les entrées/sorties et chaque fonctionnalité doivent pouvoir être branchées, débranchées, remplacées ou étendues** sans reconstruire le moteur central. Cette cible se décline dans ARC-13 à ARC-17 et les contrats d'événements NRM-01 à NRM-05 ; **elle n'affirme pas que l'existant est déjà ainsi**.

| ID | Priorité / état | Amélioration proposée / condition de réussite |
| --- | --- | --- |
| ARC-13 | P2 / P | **Contrats de fournisseurs échangeables** pour chaque dépendance technique : LLM/conversation, STT, TTS, VAD, vision image/vidéo, mémoire/stockage/recherche, transport, renderer/Live2D, outils externes, modération et observabilité. Permettre plusieurs implémentations (API cloud, moteur local, fournisseur alternatif) sans modifier la logique métier. |
| ARC-14 | P2 / P | **Entrées et sorties plug-and-play** : adaptateurs source (Discord chat/voix, Twitch, microphone PC, mobile, image, capture vidéo, futures plateformes) et adaptateurs de destination (texte, audio, avatar, overlays) déclarés, configurables, désactivables indépendamment ; préserver l'isolement des sessions et le routage par audience de RTE-01/RTE-09. |
| ARC-15 | P2 / P | **Fonctionnalités modulaires** : modules à cycle de vie explicite (initialiser, activer, suspendre, arrêter), dépendances et capacités déclarées, événements/contrats versionnés, injection de dépendances ou registre de plugins, configuration et feature flags. Ajouter/retirer une mémoire, un outil, un pipeline de perception ou une compétence sans casser la conversation de base. |
| ARC-16 | P2 / P | **Remplacement fiable d'un fournisseur** : adaptateurs de compatibilité, négociation des capacités (streaming, langue, intentions, images, coût), timeouts, circuit breakers, fallback choisi et rollback ; tenir compte des différences réelles entre API. Une bascule à chaud n'est exigée que si elle est sûre pour la session en cours, sinon bascule au prochain tour. |
| ARC-17 | P2 / C | **Contrats et vérifications transverses** : jeu de tests commun par interface avec faux fournisseurs, tests d'intégration multi-canaux et non-fuite, tests d'activation/désactivation, budgets de coût/latence, documentation du module, gestion de version/migration et secrets isolés par fournisseur. Conduire la refonte de manière incrémentale, pas par big bang. |

### Règles de conception proposées

- Le **cœur de Jade** porte les tours de conversation, identité/session, orchestration, politique de confidentialité, permissions, événements et décisions de routage ; il ne contient pas d'appels directs propres à une plateforme ou un fournisseur.
- Chaque adaptateur déclare **capabilities, configuration, dépendances, formats d'entrée/sortie, coûts et limites**. Une fonction non prise en charge reste indisponible explicitement ou emprunte un fallback choisi, jamais silencieusement.
- Les modules communiquent par des **interfaces stables et événements typés**, pas par des importations circulaires ou des fonctions spécifiques à une API répandues dans le code.
- Les modules optionnels défaillants **ne font pas tomber tout Jade** ; dégradation claire, suppression des traitements obsolètes, observabilité, restauration. La sécurité, le consentement et les politiques d'audience restent des invariants du cœur.
- La modularité **n'impose pas un microservice par fonction** : commencer par des interfaces Python et adaptateurs au sein du processus actuel. N'isoler en services distincts que lorsque cela apporte une valeur mesurée.
- Critère de réussite concret : **remplacer un fournisseur TTS/STT/LLM/vision, débrancher le visuel, ajouter un nouveau connecteur ou une compétence** avec des modifications confinées au module et à sa configuration, sans réécrire le moteur, l'identité, la mémoire ou le routage.

**Normalisation transverse :** les échanges standardisés, contrats canoniques d'événements, formats des sorties et recherches mémoire sont détaillés dans [10-NORMALISATION-DONNEES-MEMOIRE.md](10-NORMALISATION-DONNEES-MEMOIRE.md). Les choix de formats restent indépendants des fournisseurs.

**Lien fonctionnel :** la perception d'images et de vidéo est détaillée dans [09-PERCEPTION-MULTIMODALE.md](09-PERCEPTION-MULTIMODALE.md), et sert de cas d'usage exemplaire pour les adaptateurs et fournisseurs interchangeables.

## Cible mesurable, à confirmer

Une première réponse audible utile après une salutation courte **environ 0,5 à 1,5 s** serait une cible de recherche dans des conditions favorables (connexion chaude, file vide, réseau adapté). Elle n'est ni garantie ni preuve d'une mise en production. Utiliser des épreuves incluant les questions de mémoire et les interruptions ; relever médiane/p95 et coût.

**Sources :** [roadmap produit](../history/gpt6-jade/ROADMAP-MVP-DISCORD-PRODUIT-MOBILE.md), [plan latence](../history/gpt6-jade/PLAN-LATENCE-20261110.md), [handbook technique](../handbook/TECHNICAL.md), [atlas des flux](../architecture/atlas-fonctionnel-2026-11-16/CONTRAT_FLUX_COMPLET.md), conversation du 16/11/2026.
