# Dialogue Low/320, mémoire et participation — état du code develop

**Référence consolidée, 16 novembre 2026.** Cette fiche remplace les doubles explications historiques de `LLM-HISTORIQUE-PARTICIPATION-20261115.md`.

## Dialogue et historique codés

- Valeurs par défaut : `gpt-6-luna`, `reasoning_effort=low`, `max_completion_tokens=320` pour dialogue Chat Completions et streaming, modifiables par `JADE_LLM_MODEL`, `JADE_LLM_REASONING_EFFORT`, `JADE_MAX_COMPLETION_TOKENS`. Les tokens de réflexion interne sont comptés dans le plafond de complétion.
- Persona actif : `prompt_chat.txt`, texte approuvé par Goldaj le 15 novembre, à ne pas modifier sans accord. L'intention `[INTENT:label]` est filtrée hors de la sortie finale.
- Mémoire de conversation : 48 **messages** récents en RAM par défaut ; `MemoryStore` SQLite v3, si activé, conserve les échanges **entiers**, sans résumé, pour les profils fiables et opt-in. `MemoryService` restaure jusqu'aux 24 derniers tours de même périmètre, non l'intégralité de l'archive à chaque requête.
- Les conversations en base et les souvenirs ordinaires/Core sont distincts. La curation est facultative et asynchrone après livraison. La commande d'oubli efface le profil et les tours liés en base ; logs et sauvegardes externes ont leur propre politique de conservation.
- Goldaj : même identité privée pour micro PC et mobile authentifié. Un pseudonyme public ne suffit jamais à obtenir cette identité.

## Participation actuelle, d'après les transports

| Canal | Décision codée |
| --- | --- |
| Micro local / PWA privée / HTTP | Réponse à chaque tour admissible, sous réserve des gardes et commandes |
| Discord écrit | Un auteur humain observé au cours des 10 dernières minutes : 100 % ; groupe : 30 % des interventions spontanées et suivis admissibles. Messages directs, MP, mentions et commandes prioritaires |
| Discord vocal | Un humain vérifié dans le vocal : 100 % ; plusieurs humains : 30 % des tours spontanés. Adresse explicite, arrêt/reprise prioritaires. Présence inconnue ≠ solo |
| Twitch IRC | Les auteurs ayant parlé dans les 10 minutes déterminent solo/groupe : un auteur → `force_reply=True` ; plusieurs → échantillonnage 30 % via `Dialogue`, sauf adresse directe. **Un seul message Twitch en cours : nouveaux messages ignorés pendant son traitement** |

Les spectateurs Twitch silencieux ne sont pas connus par IRC. Les filtres de longueur, les délais, files et garde-fous restent actifs. Discord vocal et chat **natif de ce même vocal** peuvent partager un historique volatil pour le même compte et la même session, pas les salons différents.

## Intentions codées et travail restant

Le registre `intent-visuals.json` contient **sept intentions × deux expressions faciales r20 × deux libellés PWA** ; PC et mobile consomment ce contrat. Les **14 motions corporelles originales** sur rig r21 sont à développer, sans qualifier les expressions r20 actuelles de motions finales. Voir [passation Live2D](LIVE2D-INTENT-ANIMATION-HANDOFF-20261115.md).

Le projet de backend Realtime léger sans Luna, la mémoire anticipée et le routage exclusivement par origine sont détaillés dans le [catalogue des améliorations](../ameliorations/README.md) ; ils ne sont pas encore intégrés.
