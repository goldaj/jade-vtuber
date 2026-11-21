# Diagnostic statique DEV-019 — MP Discord écrits silencieux

- **Date :** 21 novembre 2026.
- **Demande :** analyse du code `develop` et enrichissement du P0 DEV-019 ; aucune correction logicielle ni recette matérielle demandée à ce stade.
- **Révision du code analysé :** `eb79f5538e362a35158ef7e7cd238e293ff2aa3e` (`develop` au début de l'audit).
- **Observation propriétaire :** Jade répond dans les salons Discord, mais pas dans un message privé Discord. Pas de journaux ni d'exécution du bot sur le PC disponibles dans cette analyse.
- **Verdict :** un **chemin de perte de réponse certain dans le code** si le canal DM n'est pas en cache ; c'est **la cause principale probable** du symptôme. Il reste à confirmer qu'elle se produit sur la session réelle et à exclure toute seconde cause.

## 1. Trajet d'un MP, vérifié dans les sources

1. **Entrée :** `src/jade_runtime/discord_text.py:17-31` produit un `Incoming(platform="discord", account_id=str(message.author.id), channel=str(message.channel.id), private_channel=True)` pour un MP (`guild is None`). `connect_forever():57-58` active `message_content`. Le callback `on_message():119-156` soumet au runtime les messages retenus par la politique. L'intent `dm_messages` n'est pas explicitement désactivé.
2. **Sélection :** `src/jade_runtime/discord_text_policy.py:104-105,118-141` définit `direct=True` pour un MP et impose `force_reply=True`, indépendamment du taux de participation aléatoire. Exception générale : les textes de plus de 1200 caractères sont rejetés à la ligne 122. `src/jade_runtime/social_intelligence.py:17-28` laisse immédiatement passer les MP, sans arbitrage LLM de groupe.
3. **Conversation :** `src/jade_runtime/dialogue.py:64-78` admet `force_reply` puis utilise `incoming.history_key`; `src/jade_runtime/messages.py:56-64` sépare les historiques par plateforme/canal hors liaison de conversation explicitement établie. `dialogue.py:104-115` réserve le contexte propriétaire Goldaj **aux plateformes `mobile` et `microphone`**, pas à `discord`.
4. **Identité et mémoire :** `src/jade_runtime/memory_store.py:29-48` mappe un MP sur `("discord", account_id)`, jamais sur `("microphone","goldaj")` sans liaison vérifiée. `memory_service.py:56-70` enrôle automatiquement le Discord identifié ; `memory_service.py:26-38,73-138` utilise la portée du canal et permet le rappel des souvenirs de comptes liés uniquement dans un MP ou canal privé autorisé. Le `person_id` lié est résolu par SQLite, pas par le pseudo.
5. **Sortie :** `main.py:138-167` remet la réponse au connecteur via `discord_client.send_chat(source.channel, reply.text, source_message_id=source.message_id)`. C'est ici que se concentre l'anomalie probable.

## 2. Défaut principal : dépendance au cache Discord lors de l'envoi

**Preuve de code :** `src/jade_runtime/discord_text.py:232-242` :

```python
target = self.client.get_channel(channel_id)
if target is None:
    return False  # Never guess a destination or fetch unknown IDs.
```

- `Client.get_channel` est une consultation du cache local et **ne garantit pas** qu'un DM reçu soit retrouvable. Un signalement amont de `discord.py` décrit exactement `on_message` sur un DM suivi de `get_channel(channel_id) is None` : https://github.com/Rapptz/discord.py/issues/7409 (signalement historique v2 alpha, **pas preuve directe** de la session actuelle). Référence API : https://discordpy.readthedocs.io/en/stable/api.html .
- La branche `target is None` rend **certain** le résultat `False` sans `send()`, sans retry, sans recours à `message.channel`, `fetch_channel` ou `get_partial_messageable`. La dépendance `discord-py >=2.7.1,<2.8` figure dans `pyproject.toml`.
- Le modèle `message.channel` existe pourtant lors de `on_message`; son objet de réponse fiable **n'est pas conservé** par le transport jusqu'au traitement asynchrone par le runtime.
- Cela explique qu'un salon de serveur puisse fonctionner et un DM non caché échouer silencieusement. **Diagnostic réel à confirmer** avec un MP de test et une instrumentation minimale du cas `cache_miss`. Ne pas prétendre que chaque MP de `discord.py` 2.7.1 est non caché sans vérification.

## 3. Défaut aggravant : échec masqué et historique erroné

- `main.py:152-167` encapsule `send_chat` dans `optional()` : le résultat booléen **n'est jamais contrôlé**. Le `False` normal (absence de cible) ne génère donc aucune alerte. Les exceptions d'API sont seulement résumées par `Jade optional output failed: discord`.
- `src/jade_runtime/orchestrator.py:217-230` enregistre `reply_planned` **avant** l'expédition. `src/jade_runtime/turn_logging.py:56-90` marque explicitement `delivery_status="planned_not_confirmed"`, pas une livraison réussie. **Les traces de réponse planifiée ne prouvent pas que le MP est parti.**
- `orchestrator.py:231-240` considère `played=True` pour un échange écrit et appelle `remember_turn` / `schedule` après la tentative `on_reply`, même si `send_chat` a renvoyé `False`. `dialogue.py:168-172` a en outre déjà versé le tour dans l'historique volatile. **La mémoire peut donc conserver une réponse que l'interlocuteur n'a jamais reçue.** Ce n'est pas l'origine de l'absence d'envoi mais un défaut de fiabilité directement connexe.
- Si un long message est découpé (`discord_text.py:244-267`), le premier fragment peut être envoyé puis un fragment suivant échouer ; aujourd'hui le suivi de livraison n'est pas assez précis pour qualifier cette réussite partielle.
- `tests/test_jade_discord_text_policy.py:176-202` simule uniquement `get_channel` qui **réussit**. Le scénario MP non caché, l'absence de confirmation d'envoi et les échecs d'API ne sont pas couverts par ces tests.

## 4. Autres hypothèses et risques, à ne pas confondre avec la cause probable

| Hypothèse ou constat | État | Comment trancher |
| --- | --- | --- |
| Réception des MP désactivée dans le Developer Portal / intents ou message non reçu | **Non constaté** ; parcours prévu en code | Vérifier `on_message` réel pour un DM test, sans conserver son texte ni un jeton |
| `message.content` vide, très long, ou auteur invalide | **Cas de rejet explicites** dans `parse_discord_message` et la politique | Reproduire avec « Salut » envoyé par un utilisateur humain, longueur courte |
| Filtre social à 20/30 % | **Pas une explication pour les MP normaux** : `dm` force la sélection et `HybridSocialPolicy.allow` l'autorise | Test unitaire sans mention, taux fixé à 0 |
| Panne backend LLM, file saturée, timeout, déconnexion Discord | **Possibles, sans preuve** ; devraient en général affecter aussi d'autres canaux ou produire une trace | Comparer `input_selected`, `reply_planned`, `turn_outcome` et événement d'envoi |
| Confusion systématique avec Goldaj en MP | **Non observée dans le parcours de résolution actuel** : Discord utilise `author.id`, et le prompt ne force Goldaj que pour mobile/micro | Test avec deux IDs Discord dont un lié au profil propriétaire ; vérifier `person_id` et périmètre mémoire sans afficher de souvenirs |
| Fuite des MP dans stdout / journaux | **Risque adjacent réel** : `main.py:145-146` affiche tout texte sauf mobile et `turn_logging.py` journalise du contenu ; déjà couvert prospectivement par RTE-14 | Ne pas augmenter la journalisation privée ; mesurer seulement l'issue d'envoi, et traiter la confidentialité des journaux séparément |
| Mauvais aiguillage vers mobile/API locale | **Non confirmé comme cause** : `mobile_gateway.deliver` et `local_http.deliver` filtrent par `source.platform` | Test de non-diffusion multi-canaux |

## 5. Correctif recommandé (à développer ensuite, pas exécuté ici)

1. **Conserver la cible entrante vérifiée :** dans `DiscordText.JadeClient.on_message`, pour un MP direct, enregistrer un *reply target* éphémère, borné et expirant, lié à `(source.channel, source.message_id, source.account_id)` et à l'objet `message.channel` fourni par `discord.py`. Ne pas passer par un cache global non vérifié ; libérer la référence à la livraison, à l'expiration, à l'arrêt et après échec. Les salons peuvent conserver la résolution actuelle, avec repli sécurisé si nécessaire.
2. **Routage privé strict :** envoi dans **le même DM** que le message origine, uniquement si canal, source et destinataire vérifiés concordent. Un repli `fetch_channel` ou `get_partial_messageable` est acceptable seulement pour un canal issu d'un message reçu et lié au même compte vérifié, jamais pour un identifiant arbitraire inventé. Empêcher toute fuite vers un autre utilisateur, un autre salon, un vocal ou OBS.
3. **Propager un accusé d'envoi :** `send_chat` doit produire une issue contrôlée (`sent`, `cache_miss`, `forbidden`, `not_found`, `api_error`, `partial`, `cancelled`), sans texte privé. `main.on_reply` et le runtime doivent **exploiter** cette issue ; ne pas transformer un `False` en succès silencieux. Conserver la distinction entre tentative de livraison et confirmation.
4. **Éviter de mémoriser une réponse invisible :** ne valider l'échange assistant dans la mémoire persistante qu'après réception d'une confirmation d'envoi écrite ; pour l'historique volatil, soit différer le commit soit marquer/retirer le tour échoué afin que Jade ne suppose pas avoir répondu. Éviter les retry qui dupliquent une réponse après succès partiel.
5. **Respecter le contrat d'identité existant :** conserver `account_id=Discord user ID`, le `person_id` SQLite éventuellement lié et le `scope` du MP ; ne jamais affecter Goldaj par défaut. Aucune activation de mémoire d'un autre profil ni changement de modèle d'instance.

## 6. Tests / recette exigés pour DEV-019

**Tests automatisés sans Discord ni API payante :**
- DM court, sans mention de Jade, avec `auto_rate=0` : parsé comme `private_channel=True`, reçu par le runtime et forcé en réponse.
- `client.get_channel(id)` renvoie `None` : le système expédie pourtant dans le **canal source vérifié** ou qualifie explicitement l'échec ; aucun abandon silencieux.
- Deux MP A/B simultanés : correspondance stricte message origine/canal/auteur, sans substitution ni fuite ; aucun compte attribué à Goldaj par défaut.
- Auteur lié à un profil existant : rappel autorisé du bon `person_id` ; auteur non lié : profil indépendant ; isolation des scopes MP/serveur.
- Simulation `Forbidden`, `NotFound`, timeout HTTP, cible périmée, déconnexion et réponse découpée : échec explicite, absence de mémoire d'une réponse invisible, réessai sûr ou état partiel connu.
- Pas de TTS, diffusion Discord vocale, sous-titre OBS, réponse Twitch/mobile et aucune fuite de secrets ou de contenu privé dans les métriques.
- Une seule réponse aux messages venant de Jade elle-même ; conservation de la validation actuelle des salons publics.

**Recette réelle sur le PC :**
1. Actualiser `develop`, redémarrer Jade, envoyer un MP court depuis un Discord non lié, puis depuis un compte lié, et contrôler la réponse dans **chacun des MP**.
2. Répéter après reconnexion et avec plusieurs utilisateurs ; vérifier que les réponses et souvenirs privés demeurent séparés.
3. Tracer sans contenu privé : événement reçu/accepté, ID technique du canal ou identifiant opaque, `cache_hit/cache_miss`, `send_attempt`, `send_success/send_failure` et code d'erreur Discord. Vérifier surtout si `reply_planned` est présent sans `send_success`.
4. Cocher REC-002 et confidentialité REC-005 uniquement après preuve ; appliquer la DoD. Ne pas fermer DEV-019 sur l'audit seul.

## Conclusion et limites

**Cause principale probable à traiter :** confiance injustifiée dans `client.get_channel(channel_id)` pour l'envoi d'un MP. **Défauts associés certains par lecture du code :** échec silencieux sur `False`, absence d'acknowledgment de livraison exploité, possibilité de mémorisation d'une réponse non remise, tests positifs seuls. **Aucun correctif, test exécuté ni validation réelle du bot** dans cette passation. Aucun secret ni donnée de conversation privée récupéré.
