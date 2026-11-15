# Jade — contre-audit transverse PO / architecture / développement / QA
**Date : 15 novembre 2026.** Périmètre de revue : dépôt `goldaj/jade-vtuber`, les cinq premières PR déjà fusionnées dans `develop` (#1–#5) comme base comportementale, les PR actives #6 (SQLite), #7 (PWA), #8 (Discord écrit + vocal), #9 (autobiographie) et la branche de rapprochement #11.

**Nature de la preuve :** inspection du code, comparaison des trees et des PR, tests automatisés GitHub Actions Windows/Linux avec doubles de test. **Pas de recette PC Windows de Goldaj, micro réel, Discord/Tailscale actif, SDK Live2D Web, ni d'appels OpenAI facturés**. Une compilation et des tests simulés réussis ne certifient aucun de ces éléments.

## Verdict de revue
- Les lots #6, #8 et #9 gardent leurs responsabilités distinctes et leurs PR vers leurs branches parentes ; la PWA #7 reste une PR indépendante pour la revue de son code.
- La **branche `review/jade-mobile-memory-integration-20261115` (#11)** constitue une proposition unique de reprise qui rassemble les quatre lots sans toucher à `develop` ou `main`, ni au PC ni au VPS Hyperliquid.
- La branche #11 inclut les sources de #7 et l'historique d'intégration de #6/#8/#9. **Si #11 est fusionnée à terme, ne pas fusionner à nouveau séparément #7 sans vérifier la comparaison de commits** : éviter le double déploiement de fonctionnalités.
- Les flags mobiles et mémoire demeurent désactivés par défaut. Les commandes/identités n'ouvrent aucun canal sans l'autorisation du connecteur.

## Correctifs livrés et justification

| Priorité | Observation vérifiée | Correction / preuve |
| --- | --- | --- |
| P0 | `MobileGateway._conversation` ne pouvait pas annuler le travail IA sur timeout si `wait_for` avait déjà mis la future dans l'état `done` | `completed` distinct et `runtime.cancel_work` pour toute requête non achevée ; test du backend fictif bloqué puis timeout sur #7 et #11 |
| P0 | Après liaison de comptes, un `forget` depuis le compte externe pouvait laisser les `jade_self_core` du même profil, puis les réafficher après nouvelle activation locale | Nettoyage des autobiographies lorsque le profil supprimé contient l'identité propriétaire ; deux tests (profil lié / non lié) |
| P0 | Course : `MemoryService._curate` pouvait commencer sur un profil opt-in, subir un `forget` puis écrire dans le **nouveau** profil réactivé pendant la requête LLM | Capturer le `person_id` initial et l'exiger transactionnellement au `put` / `put_self_core` ; tests d'effacement puis réactivation |
| P1 | Les champs ajoutés indépendamment à `Incoming`, au dialogue, aux réglages et au démarrage rendaient #6 et #7 impossibles à combiner mécaniquement | PR #11 : identité vérifiée, `conversation_id` + `input_modality` + `requested_speech`, rappel mémoire et identité propriétaire mobile ; tests croisés |
| P1 | Les réponses aux **messages privés Discord** pouvaient être diffusées dans un salon vocal connecté via le routage audio hérité | `Incoming.private_channel` renseigné par le connecteur Discord, bloque le contexte vocal secondaire des DM ; plus de TTS inutile si aucune sortie locale ; test de non-fuite |
| P1 | Le filtre conservateur des secrets vérifiait uniquement le `summary`, pas la `significance` enregistrée | Étendu aux deux champs ; test avec exemple synthétique |
| P2 | La PR #8 faisait apparaître >2 000 lignes modifiées principalement à cause des fins de ligne CRLF → LF | Fichiers hérités réenregistrés au format CRLF ; diff réduit aux modifications réellement fonctionnelles |
| P2 | La documentation d'intégration mobile était absente de l'index ou ajoutée hors tableau | Rapprochement des documentations #6/#7/#8/#9 et index corrigé dans #11 |

## Revue par domaine

### Produit et usage
- **Conversation unifiée :** voix et chat *natif du même salon vocal*, même compte Discord et session active. Les DMs, autres salons et autres utilisateurs ne sont pas fusionnés. Le salon texte distinct `#general` n'est PAS corrélé automatiquement : une association explicite et vérifiée reste à spécifier.
- Les messages texte non sélectionnés par la politique Discord peuvent enrichir le contexte courant sans déclencher de réponse supplémentaire. La sélection spontanée à 30 % et son cooldown ne sont pas modifiés.
- **Autobiographie :** une table SQLite distincte de la mémoire relationnelle ; les `core_self` issus de l'identité locale propriétaire sont privés à Goldaj et sans TTL. Les événements d'autres utilisateurs restent dans leurs scopes autorisés. Les Core ne sont pas un entraînement du LLM.
- **Mobile :** PWA privée sur PC par Tailscale Serve, texte + audio *push-to-talk*, réponse WAV complète, rendu Live2D côté navigateur seulement si SDK Web et modèle compatibles installés localement. Pas de duplex, WebRTC, écoute permanente ou APK natif.
- Moteur d'intention `[INTENT:label]`, exclusivité OpenAI pour STT/TTS et choix Tera/Astra : pas de changement de contrat introduit.

### Architecture et intégration
- `Incoming.session` reste la session technique de transport ; `history_key` identifie la conversation logique Discord. Aucun souvenir SQLite n'est déduit du seul nom affiché ou d'un horodatage.
- Le propriétaire est le profil `('microphone','goldaj')` lorsqu'il utilise le micro local ou la passerelle PWA **authentifiée par Tailscale Serve et jeton distinct**. Le simple pseudo `Goldaj` sur un réseau n'attribue jamais ce profil.
- L'assemblage #11 active effectivement le profil Goldaj si `--mobile` seul est lancé avec `JADE_MEMORY_ENABLED=1`. Les réponses mobiles ne déclenchent ni sortie VTS sur PC ni TTS local secondaire.
- Stockage SQLite v1 → v2 : migration additive, Core sans expiration, suppression explicite, export/import v1/v2 avec contrôle d'intégrité. La sauvegarde ZIP reste **non chiffrée** et ne doit pas être copiée dans Git ni sur le VPS de trading.
- Les commits de synchronisation ont recollé les ancêtres Git des branches empilées sans fusion vers `develop` / `main`.

### QA, coûts et exploitation
- Tests ciblés : timeout mobile, déduplication d'historique, unicité des identités, Discord DM, cycle de vie des Core, restauration SQLite v1/v2, refus de fuite entre personnes, course `forget`/`enable`, réponse mobile avec mémoire déjà existante.
- Limitation de curation : **jusqu'à un appel LLM additionnel par tour éligible** lorsque `JADE_MEMORY_CURATOR_ENABLED=1`. Désactivé par défaut. Le choix sémantique de Core Memory reste une sortie IA qui peut se tromper ; pas de validation qualitative humaine faite.
- Le micro Android et le TTS mobile sont encore en WAV complet ; la latence, les droits Android, les interruptions et le comportement réseau instable ne sont pas mesurés.
- Le mobile enregistre son texte via les traces structurées `jade.conversation` sur stderr si la journalisation est activée : garder ces traces privées, les faire expirer selon une politique locale et ne pas les envoyer à GitHub ou à un log public.
- Le rendu Web Cubism r20/r21 demeure un **bloquant physique/licence** avant d'affirmer que l'avatar bouge réellement sur Android.

## Risques ouverts, sans modification sauvage du périmètre

| Priorité | Sujet | Action nécessaire |
| --- | --- | --- |
| P1 | Diffusion vocale héritée des **messages texte de serveur Discord et de Twitch** dans le vocal actif, même si le texte vient d'un autre salon. Le correctif empêche seulement les DMs Discord. | Arbitrage produit du propriétaire : maintien volontaire du broadcast global ou restriction aux salons liés. Ne pas imposer un changement silencieux de politique déjà utilisée. |
| P1 | Moteur Cubism Web et package r20/r21 : compatibilité réelle et droits SDK incertains | Vérification licence/format de modèle/SDK et essai Chrome Android sur le PC |
| P1 | CI hors ligne ne prouve ni connexion DAVE, ni STT/TTS, ni identité Tailscale Serve | Recette réelle courte, contrôle du coût, observations et rollback |
| P2 | Pas de timeline chronologique forte quand la transcription vocale revient après un texte écrit | Conserver ordre d'arrivée, puis mesurer les cas de simultanéité avant d'enrichir le ConversationManager |
| P2 | `core_self` privé à Goldaj : pas d'autobiographie globale partageable à tout le serveur | Classification de visibilité et contrôle de contenu privés avant toute ouverture |
| P2 | Les doublons de Core sont filtrés lexicalement par empreinte, non sémantiquement | Mesurer l'effet de répétition sur des échanges réels avant un moteur de rapprochement plus sophistiqué |
| P2 | Effacement ne purge pas automatiquement les **anciennes sauvegardes** déjà exportées | Politique de conservation et restauration ; ne pas réimporter une archive antérieure à un oubli |

## Plan de passage et recette

1. Confirmer les CI du **SHA HEAD** de #6, #7 et de la branche d'intégration #11 : Ubuntu + Windows, vérification des secrets et hygiène de publication. Les anciens SHA verts ne valident pas les nouvelles modifications.
2. Préserver l'ordre des PR : #6 → #8 → #9 → #11, en évitant le double merge de #7 déjà contenu dans #11. Prendre une seule décision de fusion après revue, jamais vers `main` sans accord du propriétaire.
3. Sur le PC Windows Jade, sauvegarder la base SQLite v1 avant migration ; vérifier D:, version de Python, exigences Tailscale Serve, JWT/Bearer distincts et URL HTTPS réelle. Aucun secret ne doit apparaître dans les PR publiques.
4. Test Discord : vocal et chat du même salon (même auteur), changement de pseudo, autre utilisateur, DM, salon séparé, déconnexion/reconnexion. Vérifier **aussi** qu'un DM ne sort jamais en vocal.
5. Test PWA : texte puis microphone Android dans le même fil, voix désactivée (pas de TTS facturé), rendu alpha/expressions/bouche du SDK légalement installé, réseau instable, interruption et expédition non dupliquée.
6. Test mémoire : une Core ordinaire et une autobiographique décidées en simulation puis en réel avec petit quota, redémarrage, restauration, correction/effacement, course forget/réactivation. Vérifier l'absence de fuite sur un autre compte ou salon.
7. Mesurer la latence perçue au premier son, les coûts, les consommations CPU/réseau et l'éventuel repli en cas de panne.
8. Retour arrière : désactiver `JADE_MOBILE_ENABLED`, `JADE_MEMORY_ENABLED` et/ou `JADE_MEMORY_CURATOR_ENABLED` dans la configuration **privée** sans toucher aux autres services ; restaurer depuis une sauvegarde de base cohérente si une migration devait être annulée.

**Décision de contre-revue :** correctifs candidats pour intégration après CI ; **ne pas** annoncer Jade déployée, recettée matériellement ni intégrée à la production. Ce document n'est pas une approbation de merge automatique.
