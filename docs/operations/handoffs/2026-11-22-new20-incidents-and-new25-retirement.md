# Passation : NEW-20 → DEV-031 ; NEW-25 retirée

**Décision du propriétaire : 22 novembre 2026, branche develop exclusivement.**

## Périmètre du développement NEW-20

Objectif produit : lorsqu'une interaction directe échoue, Jade informe l'interlocuteur sur le **canal autorisé d'origine**, si cette information peut être délivrée sans nouveau modèle IA. Ne jamais prétendre qu'un message, une lecture ou une action a réussi quand ce n'est pas confirmé.

- Nouveau module `incidents.py` : classification déterministe et bornée des exceptions et codes HTTP, avec phrases françaises pour délai, surcharge, perte de connexion, permissions, limitation fournisseur et incident générique. **Aucun `str(exc)` ne rejoint la réponse** ; les identifiants et contenus privés sont exclus. Champ `retryable` informatif, pas de relance automatisée.
- Discord texte : la politique existante marque une **demande explicitement directe** (mention, réponse au bot, MP ou commande) séparément des participations spontanées ; seul ce type de demande peut recevoir une notification, dans le même salon/MP que le message d'origine et sans changement d'audience. Si une erreur intervient **avant que `on_reply` ne démarre**, `Runtime` peut appeler un callback facultatif avec un délai maximal de 3 secondes. Une réponse déjà engagée, une annulation, une expiration, une intervention spontanée ou un shutdown n'engendrent jamais de seconde notification. Un échec du callback ne bloque ni le worker ni la conversation suivante.
- Saturation de la file Discord : le connecteur peut prévenir une demande directe refusée avant l'entrée dans Runtime, sans relancer le LLM ; les interventions ambiantes restent silencieuses.
- PWA : les erreurs des API conversationnelles authentifiées gardent leurs champs `error` historiques mais ajoutent `incident_code`, `message` et `retryable`. L'interface affiche le motif utile lorsqu'il est connu. Une synthèse vocale échouée **après une réponse textuelle valide** est signalée comme problème vocal seulement, sans effacer la réponse ni regénérer du texte. Streaming NDJSON et mode non-streaming conservent leurs protocoles.
- HTTP local : même enrichissement du JSON d'erreur, en conservant les anciens codes `busy`, `timeout` et `unavailable` ; l'interface locale présente la formulation humaine.
- Console/micro PC : si la demande directe est authentiquement marquée, le callback peut afficher une information locale non sensible ; ni la voix Discord, ni Twitch, ni OBS n'envoient de nouveau message de panne non sollicité.
- Aucun appel OpenAI supplémentaire, aucune boucle de retry, aucun envoi intersalon, aucun changement de routeur multimédia, de mémoire, de TTS, d'autorisation ou de fournisseur. Cette fonctionnalité n'ajoute pas de « conscience de la panne » au LLM : c'est une explication produit déterministe.

## Non-régression et limites

Tests ciblés pour cas : exception avec message privé, 429, délai, droits, connexion et inconnu ; notification au plus une fois après erreur avant diffusion ; aucune notification sur participation spontanée ; aucune double diffusion si l'envoi initial échoue ; panne du callback n'empêche pas le tour suivant ; erreur TTS PWA conserve la réponse ; API locale et PWA gardent leurs anciens champs.

**Limitations assumées :** une réponse audio Discord coupée n'est pas convertie en voix de secours payante et n'est pas publiée dans un salon non garanti ; Twitch et OBS n'ont pas de notification publique de panne ajoutée. Les erreurs de streaming déjà démarré peuvent se limiter au signal audio d'échec prévu par le protocole. Une panne du transport empêchant tout envoi signifie qu'un message explicatif peut également ne pas parvenir.

**Recette physique restante :** provoquer un indisponibilité réversible dans une conversation Discord directe, vérifier un message unique dans le même canal ; ouvrir la PWA et provoquer l'indisponibilité vocale (réponse écrite conservée), vérifier erreur authentifiée claire, absence de fuite et pas d'appel IA de rattrapage. Le ticket reste ouvert jusqu'à cette validation.

## Suppression des idées multilingues

**NEW-25** (multilinguisme et traduction contextuelle) a été supprimée du **catalogue prospectif actif**, sur demande expresse. Recherche sur les onze thèmes : aucune autre ligne de proposition directement consacrée à la traduction ou aux langues multiples. Les exigences qui mentionnent « langue » au sens de formats/types ou « langage naturel » ne constituent pas des fonctionnalités multilingues et restent intactes. Aucun code de traduction, configuration linguistique actuelle ni comportement existant n'a été modifié par ce nettoyage.

Les identifiants retirés restent dans l'historique Git, mais ne sont plus des idées actives et ne doivent pas être proposés de nouveau sans demande explicite du propriétaire.
