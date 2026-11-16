# Architecture conversationnelle légère et extensible

**Décision produit actuelle : pas de Luna pour le MVP.** Jade doit mener des conversations simples rapidement. Préparer **les points d'extension** d'un moteur de réflexion avancé sans exécuter, facturer ou imposer son intégration maintenant. L'existant reste opérationnel tant que la refonte n'est pas recettée.

| ID | Priorité / état | Amélioration proposée / condition de réussite |
| --- | --- | --- |
| ARC-01 | P2 / P | Implémenter un **RealtimeConversationEngine** vocal/texte léger, avec session, arrivée d'audio et sortie incrémentale, à comparer avant tout remplacement du dialogue actuel. |
| ARC-02 | P2 / P | **Interface de backend IA** stable (texte/audio, intention, contexte, deadlines, annulation) : permet une stratégie future de délégation vers Luna ou un moteur local, inactive aujourd'hui. |
| ARC-03 | P2 / P | Faire converger Discord, micro PC, Twitch et mobile sur un **contrat d'événements** commun : transcription, message, intention, chunk audio, animation, accusé de sortie et fin de tour. |
| ARC-04 | P2 / P | Découpler les sous-systèmes **InputAdapter → Presence/Memory → ConversationEngine → OutputRouter → SurfaceRenderer** avec états par session, non un callback géant bloquant. |
| ARC-05 | P2 / P | **Gestionnaire de sessions** : garder/fermer les connexions vocales selon activité, restaurer persona et contexte condensé sans perdre les messages, mesurer facturation des sessions actives. |
| ARC-06 | P2 / P | Supporter proprement une **interruption naturelle / barge-in** sans double STT, fuite de session, écho de voix ou lecture d'un vieux chunk. |
| ARC-07 | P2 / P | **A/B de deux prototypes** : (A) pipeline actuel optimisé, (B) backend vocal Realtime natif. Comparer latence de contenu utile, cohérence des intentions, prononciation française, mémoire, coût et défaillances. |
| ARC-08 | P2 / P | Réponse légère aux demandes ordinaires ; aucun appel de réflexion supplémentaire, de curation ou d'arbitrage IA si une décision locale suffit. Préserver comportement naturel et prise en compte du contexte. |
| ARC-09 | P2 / P | **Observabilité par étape**, budgets de temps et de coût configurables, feature flags et rollback vers pipeline historique sans migration irréversible. |
| ARC-10 | P3 / D | **Luna ultérieurement** : décision de délégation sur besoin prouvé, travaux parallèles, injection de résultat vérifié, gestion d'attente sans mensonge. Ne pas activer ni optimiser ce composant aujourd'hui. |
| ARC-11 | P3 / D | **Moteur IA local éventuel** : évaluer selon matériel réel, latence, mémoire, qualité française et coûts avant de changer les services OpenAI ; pas de promesse de compatibilité sans benchmark PC. |
| ARC-12 | P1 / R | Maintenir la **personnalité validée** (prompt de Goldaj, intentions, variations, affection occasionnelle) et une voix cohérente à travers tout backend ; écouter de vrais dialogues et non quelques mocks. |

## Cible mesurable, à confirmer

Une première réponse audible utile après une salutation courte **environ 0,5 à 1,5 s** serait une cible de recherche dans des conditions favorables (connexion chaude, file vide, réseau adapté). Elle n'est ni garantie ni preuve d'une mise en production. Utiliser des épreuves incluant les questions de mémoire et les interruptions ; relever médiane/p95 et coût.

**Sources :** [roadmap produit](../gpt6-jade/ROADMAP-MVP-DISCORD-PRODUIT-MOBILE.md), [plan latence](../gpt6-jade/PLAN-LATENCE-20261110.md), [handbook technique](../handbook/TECHNICAL.md), [atlas des flux](../architecture/atlas-fonctionnel-2026-11-16/CONTRAT_FLUX_COMPLET.md), conversation du 16/11/2026.
