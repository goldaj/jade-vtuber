# Modèle 2D conditionnel, intentions et animation

**But :** ne pas produire de rendu Live2D, expression, mouvement de lèvres ou commande VTube Studio lorsqu'aucun écran autorisé ne peut montrer Jade. **La voix et le texte restent disponibles.**

La présence d'un spectateur et la visibilité de l'avatar ne sont pas synonymes. Un stream Twitch « live » ne prouve pas que Jade est dans la scène OBS ; un partage Discord ne prouve pas que Jade est dans l'image ; un onglet ouvert peut être masqué. Il faut croiser plusieurs signaux et accepter l'état **inconnu**.

| ID | Priorité / état | Amélioration proposée / condition de réussite |
| --- | --- | --- |
| VIS-01 | P1 / P | Créer **AvatarVisibilityManager** indépendant des canaux avec état visible / invisible / inconnu **par surface** (PC, OBS, Discord stream, PWA). |
| VIS-02 | P1 / P | **OBS/Twitch :** signal OBS WebSocket de stream + scène et source effectivement affichées. Compteur Twitch éventuellement informatif, jamais preuve suffisante de visibilité du modèle. |
| VIS-03 | P2 / P | **Discord :** détecter l'activité de partage d'écran quand accessible ; vérifier séparément que la fenêtre montrée est Jade, ou fournir un toggle manuel. Ne pas inventer un détecteur de spectateur absent des API. |
| VIS-05 | P1 / P | **Fenêtre PC :** minimisée/fermée/cachée versus visible ou capturée par OBS ; ne pas arrêter les animations d'une fenêtre capturée même si elle n'a pas le focus. |
| VIS-06 | P1 / P | **Arrêt effectif du travail graphique** : pause render loop/GPU, calcul de bouche, envoi de hotkeys et messages IPC lorsqu'aucune sortie visuelle utile n'est active. Ne pas simplement masquer le personnage. |
| VIS-07 | P1 / P | **Hystérésis** à l'extinction (premier candidat : 5–10 s) et reprise depuis un état neutre ; éviter les redémarrages fréquents quand on change de fenêtre. |
| VIS-10 | P2 / E | Uniformiser synchronisation PC/Discord/PWA : déclencher bouche sur **audio effectivement consommé**, expression seulement pour une audience autorisée, retour au neutre, silence et annulation. |
| VIS-13 | P1 / P | **Filtrage par audience** : une question privée/mobile ou un salon Discord sans visibilité ne pilote pas l'avatar d'un live Twitch public. Si OBS montre Jade, l'Idle peut continuer sans réagir aux conversations hors diffusion. |
| VIS-14 | P2 / P | Mesurer charge CPU/GPU, consommation mémoire, FPS et délai de bascule visible/invisible. Ne pas prétendre gagner une seconde de LLM parce que l'avatar est éteint. |

**Promotion du 22/11/2026 :** VIS-04 est retirée des idées actives et transférée en [DEV-027](../backlog/01-DEVELOPPEMENT.md) (suspension du moteur Live2D mobile hors champ).

## Contrat fonctionnel

- **Aucune fenêtre visible, aucun OBS avec Jade et aucune PWA active** : seul le texte ou l'audio du canal d'origine est généré. Le composant graphique ne tourne pas.
- **Une sortie graphique visible** : seuls les événements autorisés destinés à son audience sont animés.
- **Visibilité inconnue** : politique conservatrice configurable, et possibilité de forcer le mode visuel manuellement ; jamais un partage d'informations privées vers une scène publique.
- La disponibilité d'un moteur graphique n'est pas un motif pour diffuser les messages vers lui.

**Sources :** [handoff Live2D intentions](../history/gpt6-jade/LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md), [audit mobile/mémoire](../history/gpt6-jade/AUDIT-REVUE-MOBILE-MEMOIRE-20261115.md), [qualité artistique](../../jade-modeling/PLAN_QUALITE_PRO_20261113.md), code avatar.py, main.py, mobile_gateway.py et conversation du 16/11/2026.
