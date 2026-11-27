# Discord Live automatique — contrat du 27 novembre 2026

Le propriétaire demande de développer l'automatisme mensuel Discord maintenant, à la suite de la reprise du Live mobile. Cette décision remplace le cadrage « Discord futur » du 26/11. La fonction est suivie en **REC-051 (ancienne DEV-052)** ; les tests logiciels ne remplacent pas l'essai du compte et du salon Discord réels. [Passation](../operations/handoffs/2026-11-27-chatgpt-discord-auto-live.md) · [État de develop](../handbook/BRANCH_STATE.md).

## Un seul interrupteur

Dans `src/jade_runtime/discord_config.py` :

```python
DISCORD_ENABLED = True
```

| Valeur | Comportement au lancement habituel |
| --- | --- |
| `True` | Discord écrit et vocal actifs ; le vocal choisit automatiquement Live ou classique selon la politique ci-dessous |
| `False` | Tout Discord désactivé, y compris avec `--all-channels`, `--discord` ou `--discord-voice` |

Redémarrer Jade après modification. Le masque est appliqué avant les prérequis du token et la construction des connecteurs. Les anciens paramètres privés `JADE_DISCORD_ENABLED`, `JADE_DISCORD_VOICE_ENABLED` et `JADE_DISCORD_LIVE_ENABLED` ne contournent pas cette constante. Les options CLI individuelles restent des choix de transport pour les diagnostics ; le lancement habituel est `--all-channels`.

Le texte Discord garde son moteur écrit. L'interrupteur n'ouvre pas de session audio facturée à lui seul : la voix attend une nouvelle parole admissible. Les flags Live mobiles et le choix du Profil mobile ne pilotent pas Discord.

## Décision financière limitée au moteur Discord

| Qualité des données | Décision |
| --- | --- |
| Dépenses monétaires complètes, borne de couverture explicitement fraîche | Live sous 50 EUR, classique à partir de 50 EUR |
| Relevés exploitables mais estimés ou retardés | Live sous 40 EUR, classique à partir de 40 EUR |
| Source essentielle absente, conversion impossible, état incertain ou relevé expiré | Classique, avec motif de diagnostic |
| Seuil consommé atteint pendant le mois | Classique pour le reste du mois, même après correction baissière ou redémarrage |

Le mois est civil en **Europe/Paris**, y compris les changements d'heure. Au nouveau mois, la politique refait une décision avec les données du nouveau mois et les engagements non soldés. Elle ne réactive pas Live sur un compteur vide non vérifié. Une qualité qui se dégrade avec 45 EUR déjà observés impose immédiatement le seuil de 40 EUR.

Avant chaque ouverture, une transaction SQLite réserve atomiquement une garde pour les durées maximales d'ouverture, de clôture et l'intervalle de contrôle. Après l'ID de session reçu, seule la garde clôture/contrôle reste future. Deux admissions concurrentes partagent donc la même marge disponible, y compris entre instances utilisant cette base. Une marge insuffisante rend le tour entier au classique **avant** toute création fournisseur ; elle n'est pas une dépense et ne déclenche pas à elle seule le verrou mensuel.

Pendant la session, le temps écoulé non couvert par un compteur fournisseur ajoute une exposition estimée, distincte du consommé et de la garde future. L'absence d'événements d'usage n'autorise pas une session illimitée. À la fermeture confirmée, le compteur final remplace cette exposition ; un compteur final nul ne crée aucun débit fictif pour la connexion ou le nettoyage. Sans confirmation, l'engagement reste durable, même au mois suivant. L'usage final est enregistré de façon idempotente avant de libérer la réserve et d'effacer la tentative de transport.

**Les relevés standard utilisent 40 EUR.** Les API consultées ne promettent pas une borne instantanée de complétude comptable. Une réponse HTTP récente prouve la lecture récente du relevé, pas la fraîcheur des écritures sous-jacentes. Le seuil de 50 EUR n'est donc pas obtenu en étiquetant arbitrairement une lecture « complète ».

Ce mécanisme choisit le moteur vocal de Discord. Les appels classiques et ceux des autres canaux continuent : il ne garantit pas que la facture totale du mois sera plafonnée. **Aucun budget financier mobile n'est ajouté.** Le mobile contribue au total observé, mais cette politique ne change ni sa préférence ni sa session.

### Périmètre des sources

`global_spend.py` couvre les fournisseurs payants actuellement intégrés à Jade :

- **OpenAI :** `/v1/organization/costs`, sans filtre de projet, clé, modèle, produit ou canal. Le relevé inclut les produits OpenAI de l'organisation : voix mobile/Discord, STT, TTS, dialogue, backend, curation, arbitrage et outils facturés par OpenAI. La clé privée existante `JADE_OPENAI_ADMIN_KEY` est nécessaire ; une clé de projet du dialogue ne suffit pas à lire les coûts de l'organisation. Les coûts des autres applications de la même organisation sont aussi inclus.
- **Tavily :** `/usage`, champs du **compte entier**, quand le compte est configuré ou a été observé actif dans le mois. Les crédits effectivement consommés sont valorisés à 0,008 USD/crédit, tarif public pay-as-you-go utilisé comme estimation prudente. Les crédits gratuits ou prépayés ne réinitialisent pas la consommation ; **les quotas inutilisés ne deviennent jamais des dépenses**. Une désactivation de la recherche en cours de mois n'efface pas son coût.
- **Conversion :** taux ECB quotidien, cache de six heures, date du fixing conservée, ancienneté maximale de sept jours. La conversion divise par le nombre d'unités de devise par euro. Aucune parité USD/EUR inventée ; devise non couverte ou taux inexploitable = classique.

Les comptes privés ne sont pas inventoriés à distance par ce développement. L'installation doit vérifier que la clé d'administration et les clés applicatives appartiennent bien au périmètre voulu. Tout nouveau fournisseur payant devra être ajouté au collecteur avant de prétendre à une couverture globale.

Tavily documente un reset mensuel mais son endpoint ne publie ni fuseau ni ID de cycle. À une frontière mensuelle ambiguë sans historique de reset, le collecteur garde le classique pendant la fenêtre de transition de 48 heures, jusqu'à obtenir un cycle exploitable. Il n'utilise pas le plafond du plan comme substitut à une consommation inconnue.

### Cadence et persistance

Le rafraîchissement fournisseur cible **300 secondes**, avec délais réseau et volume de réponse bornés. Une décision locale n'attend pas un appel fournisseur ; au-delà de 330 secondes sans relevé exploitable, elle refuse Live et lance un rafraîchissement en arrière-plan. L'adaptateur contrôle la politique chaque seconde pendant une session. Aucun LLM n'est appelé pour surveiller les coûts.

`jade-global-spend.sqlite3`, voisin du fichier `JADE_LIVE_USAGE_DB_PATH`, conserve relevés, provenance, fixing, observations Live et verrou mensuel. Les observations de durée sont cumulatives et dédupliquées. Le coût local non encore réconcilié complète le relevé OpenAI ; une simple lecture réussie, une variation Tavily ou un changement de taux ne le supprime pas. La croissance monétaire OpenAI effectivement relevée peut absorber ce report. L'absence d'usage final ne vaut pas zéro.

La décision expose mode, raison, mois, montant, seuil, qualité et date de collecte. Les changements de décision sont consignés sans spam dans les journaux. Une indisponibilité de la collecte garde le parcours classique ; elle ne bloque pas le démarrage du mobile.

## Transport audio et conversation

`discord_live_provider.py` utilise la **WebSocket primaire Live** : connexion serveur authentifiée, `session.start` en première commande, attente de `session.started`, puis PCM16 mono 24 kHz. Les clés restent côté serveur. L'entrée Discord PCM16 stéréo 48 kHz est filtrée et convertie en continu ; les trames sont cadencées en temps réel. Aucun replay automatique d'un flux après erreur réseau.

`discord_live.py` s'insère dans `OpenVoiceBridge` :

- **Solo humain vérifié :** détection locale de parole, pré-roll borné, ouverture seulement pour une nouvelle parole, puis streaming natif sans STT préalable.
- **Groupe :** conserver la segmentation, STT et décision de participation du vocal existant ; envoyer au Live seulement le tour autorisé, avec son auteur vérifié. Ce parcours a une latence plus élevée que le solo.
- **Sortie :** PCM vers le lecteur Discord existant, bouche/observateurs pilotés par ce qui est joué. Durée cumulative bornée par la session ; files audio en mémoire bornées séparément. Les événements de transcript alimentent le contexte et la mémoire, sans seconde synthèse TTS.
- **Mémoire et outils :** `LiveConversationBridge` réutilise persona, Runtime, arbitrage, droits d'écriture/suppression, politique de lecture globale et identités Discord vérifiées. Le contexte source est enregistré dans le journal privé pour la reprise. Les délégations et effets métier sont idempotents. Les documents sont publiés dans le texte du salon vocal, avec la rétention existante, sans double réponse classique.

Un changement de présence/speaker/canal, une déconnexion, l'inactivité, la durée maximale ou la politique invalide la génération avant de demander sa fermeture. Une phrase déjà commencée dans un moteur n'est pas coupée en deux routes lors d'une bascule. Un énoncé ambigu ou partiellement consommé n'est pas réémis automatiquement dans le classique ; la parole suivante utilise le moteur disponible.

## Fermeture, incidents et reprise

Le terminal `session.closed` confirme la fermeture fournisseur. Une fermeture réseau ou un timeout seul ne la prouve pas. Une tentative d'ouverture est persistée **avant** la commande pouvant créer la session. Une annulation conserve l'ID reçu tardivement et le résultat de clôture, quand ils existent.

Le registre de transport réside dans `jade-discord-live-journal.sqlite3`, voisin du fichier d'usage, table `discord_live_transport`. Il conserve seulement les métadonnées techniques nécessaires ; les données métier suivent le journal privé et sa rétention. Au redémarrage, une session connue non confirmée reçoit une tentative de fermeture par sideband, sans création ni renvoi d'audio. Sans ID ou sans terminal confirmé, Live demeure fermé et le classique reste disponible. Ne pas supprimer ces lignes pour masquer l'incertitude.

Le résultat d'usage final doit rester durable jusqu'à sa prise en compte idempotente par la comptabilité. Le nettoyage final ferme l'adaptateur avant la politique pour conserver cet usage. Les erreurs de fermeture Live ne dispensent pas de fermer le transport vocal classique.

## Recette et références

Les tests injectent fournisseurs, compteurs, réseau et audio : seuils, baisse de qualité, concurrence, persistance, changement de mois, pannes, annulation, taille des buffers, routes de groupe, mémoire, outils et switch OFF. Les suites mobiles sont conservées. Les résultats chiffrés et contre-revues sont dans la [passation](../operations/handoffs/2026-11-27-chatgpt-discord-auto-live.md).

**REC-051 reste À valider** sur le compte Discord réel : accès Live et Costs, lecture Tavily, permissions/DAVE, audio solo/groupe, latence, coupures, franchissement de seuil, OFF complet et indépendance du mobile. Aucun test physique n'est présumé réussi.

Sources officielles consultées le 27/11/2026 : [Live WebSockets](https://developers.openai.com/api/docs/guides/voice-websockets), [Organization Costs](https://developers.openai.com/api/reference/resources/admin/subresources/organization/subresources/usage/methods/costs), [Tavily usage](https://docs.tavily.com/documentation/api-reference/endpoint/usage), [Tavily tarifs](https://docs.tavily.com/documentation/api-credits), [reset mensuel Tavily](https://help.tavily.com/articles/3116968635-when-do-my-monthly-api-credits-reset), [change ECB](https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml), [tarifs OpenAI](https://developers.openai.com/api/docs/pricing).
