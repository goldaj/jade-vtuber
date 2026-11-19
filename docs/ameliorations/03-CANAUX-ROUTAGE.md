# Routage par canal source, sessions et concurrence

**Décision produit du 16/11/2026 :** réponse uniquement au canal/modalité d'entrée sauf redirection autorisée. **Correctifs partiels DEV-003/005 du 19/11** : plus de TTS pour les écrits, plus de fallback WAV local sur Discord vocal ; routeur général des sorties et animations encore à créer. Le mode tous canaux du launcher reste actif.

## Matrice cible du routeur

| Entrée | Sortie normale et unique | Ne doit PAS se produire |
| --- | --- | --- |
| Discord texte salon X | Texte dans le même salon X | TTS, sortie Discord vocal, Twitch, haut-parleur PC, overlay sans audience pertinente |
| Discord MP | Texte dans ce MP | Aucune sortie publique ni sous-titre/animation de stream |
| Discord vocal salon X | Audio dans **ce vocal**, session encore autorisée | Son PC, autre vocal, retour texte automatique dans d'autres salons |
| Twitch écrit | Texte dans le même chat | TTS PC ou Discord |
| Microphone PC | Voix sur les haut-parleurs PC | Discord/Twitch |
| PWA mobile texte | Texte dans la session mobile ; audio seulement si option demandée | Audio PC ou Discord |
| PWA mobile voix | Voix dans la session mobile si demandée, texte de transcription dans l'application | Audio PC ou Discord |
| HTTP local | Texte sur la connexion HTTP source | Synthèse et lecture PC |
| Console | Réponse console | Sorties publiques secondaires |

**Note :** les animations sont un effet de présentation **conditionnel sur le rendu visible de la même audience**, non une nouvelle destination de réponse. Les journaux techniques ne sont pas des canaux de diffusion des conversations.

| ID | Priorité / état | Amélioration proposée / condition de réussite |
| --- | --- | --- |
| RTE-01 | P1 / P | Créer **OutputRouter** : décision centralisée avant tout TTS/texte/overlay, à partir du transport, canal, session, modalité et autorisations. Ne pas reproduire des tests de plate-forme épars dans on_reply. |
| RTE-02 | P1 / E | Supprimer la **synthèse vocale des écrits** Discord, Twitch et HTTP, et l'audio Discord vocal doublé sur les haut-parleurs PC. Préserver PWA speak=true et voix du microphone local. |
| RTE-03 | P0 / E | Protéger les messages privés, les salons différents, les personnes différentes, les sessions vocales révoquées et les canaux Twitch contre une diffusion croisée ; conserver les gardes existantes. |
| RTE-04 | P1 / E | **Consolider le routage exclusif** avec early speech, PCM progressif et replis WAV dans `--all-channels` : le streaming PCM Discord ne dépend déjà plus du lecteur `ffplay` réservé au micro PC ; traiter les éventuelles doubles sorties du chemin de repli sans casser le microphone local. |
| RTE-05 | P1 / P | Séparer **génération du tour**, **diffusion** et **confirmation de lecture**. Une lecture longue ne doit pas monopoliser l'unique worker et retarder une nouvelle question texte sur un autre support. |
| RTE-06 | P2 / P | Architecture à **tâches par conversation**, file audio par destination, backpressure et quotas globaux ; préserver ordre dans un même fil et équité entre les plateformes, sans priorité Twitch/Discord fixe. |
| RTE-07 | P2 / E | Optimiser **TurnArbiter** au-delà du cas **déjà codé d'une seule demande en attente**, qui ne déclenche aucun arbitrage LLM : identifier les autres décisions triviales localement, garantir l'équité sous charge et ne jamais facturer un arbitrage pour un arrêt d'urgence. Voir le doublon LAT-12 retiré du catalogue. |
| RTE-08 | P1 / E | Annulation/coupure : départ du vocal, perte de consentement, stop/reprise, mutation de session et interruption pendant streaming doivent supprimer immédiatement le travail et le son obsolètes. |
| RTE-09 | P1 / P | Ajouter une **politique explicite de redirection** uniquement quand l'utilisateur l'a demandée et que les deux cibles sont authentifiées/permises ; ne jamais inférer une autorisation du simple fait qu'un bot est connecté partout. |
| RTE-10 | P2 / E | Garder le partage d'historique entre voix Discord et chat **natif du même vocal** et améliorer les cas de textes reçus pendant STT ; ne pas fusionner automatiquement les autres salons. |
| RTE-11 | P1 / P | Faire de **la sortie visuelle un abonné filtré** par audience : une conversation Discord ne doit pas automatiquement déclencher un visage visible sur Twitch ni vice versa. |
| RTE-12 | P1 / E | Journaliser séparément **destinations prévues**, **envois réellement confirmés** et **diffusion audio complète** ; éviter de présenter planned_not_confirmed comme une preuve de livraison. |
| RTE-13 | P0 / C | Tester la matrice complète sur deux salons Discord, un MP, un vocal, Twitch, micro PC, HTTP et PWA ; vérifier facturation TTS nulle sur les écrits et non-fuite de texte/audio/avatar. |
| RTE-14 | P2 / E | **Limiter l'exposition des conversations privées dans la console et les journaux structurés** : étudier le masquage ou le caviardage des contenus de MP Discord, de l'API locale et des autres conversations propriétaires dans `main.py` (stdout) et `turn_logging.py` (stderr / journaux JSON). Conserver les informations de diagnostic utiles (canal, type d'événement, résultat, durée, identifiants techniques non sensibles) et, si nécessaire, une journalisation détaillée explicitement activée et protégée. Vérifier par tests que les échanges privés ne s'affichent pas lors d'une capture de console ou de journaux, sans empêcher les usages légitimes de débogage. **Amélioration différée, non bloquante, pas de développement avant décision ultérieure.** Voir également QUA-07 pour la gestion des journaux privés. |

**Sources :** [audit transverse](../history/gpt6-jade/AUDIT-TRANSVERSE-20261115.md), [Discord unifié](../history/gpt6-jade/HANDOFF-DISCORD-UNIFIED-20261115.md), [réconciliation](../history/gpt6-jade/RECONCILIATION-CODE-CONFIG-DOCS-20261116.md), [contrat de flux](../architecture/atlas-fonctionnel-2026-11-16/CONTRAT_FLUX_COMPLET.md), code main.py/output.py/turn_logging.py et conversation du 16/11/2026.
