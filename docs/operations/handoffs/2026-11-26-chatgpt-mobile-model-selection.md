# PWA : préparation du choix de modèle — 26 novembre 2026

- **Demande :** préparer le choix entre le modèle actuel et un futur second modèle dans Profil, sans raccorder le nouveau paquet maintenant.
- **Base :** `develop` au SHA `4522f39722d3f085254a803fd05c5ec6bf126a3e`, branche de travail `work/mobile-model-selection-20261126`. Intégration directe sur `develop` demandée par le propriétaire ; aucune modification de `main`.
- **Réalisation :** agent principal pour le renderer, le chargeur exclusif et le cadrage ; sous-agent catalogue/Profil/cycle du corps ; sous-agent backend/CI ; contre-revue PO/QA indépendante.
- **Backlog :** demande directe, distincte du raccordement réel du r21. Aucune carte existante n’est clôturée ou déplacée par cette mission.

## Critères et preuves

| Critère | Réalisation et vérification |
| --- | --- |
| Choix dans Profil | Sélecteur « Modèle de Jade », « Modèle actuel » sélectionné au démarrage, « Nouveau modèle — à venir » désactivé. Vérifié par tests UI et dans Chromium. |
| Second modèle non branché | `JADE_MOBILE_SECOND_MODEL_DIR=` vide ; catalogue `next.available=false`, manifeste `null`. Aucune détection automatique du r21/v45.1 et aucune requête `/models/next/` au démarrage livré. |
| Aucun préchargement des deux modèles | Le catalogue ne contient que des métadonnées. Ouvrir Profil ne charge rien de plus. Le choix est propre à la session et le classique reste le défaut au prochain lancement. |
| Une seule instance de modèle à la fois | Destruction du sortant avant chargement du suivant, chargements sérialisés et candidats obsolètes détruits avant de poursuivre. Maximum observé dans Chromium : un modèle vivant et un canvas. |
| Corps classique retiré | Retrait du corps DOM et de sa texture Pixi avant remplacement. Un profil `full` ne reçoit ni corps statique, ni isolation de tête, ni expressions/Idle propres au r20. Le retour classique recrée sa composition. |
| Conservation du décor | La pièce choisie est conservée ; le portrait validé et ses animations dépendent de `portraitReady`, indépendamment du corps. Les images de corps tardives ne peuvent pas réapparaître après une sélection. |
| État exact et échecs récupérables | L’interface reflète le modèle réellement actif. Un chargement raté est nettoyé avant le retour au classique ; si sa propre récupération échoue, arrêt sans boucle. Une libération non confirmée bloque toute nouvelle allocation jusqu’au rechargement du salon. |

## Décisions techniques

Le serveur expose `GET /assets/avatar-models.json`, catalogue v1 fermé aux profils `classic` et `next`. Le second emplacement exige un dossier portable explicitement configuré ; seules les ressources déclarées dans `Jade.model3.json` sont servies. La validation refuse les chemins sortants, liens symboliques du paquet, fichiers manquants ou vides, pointeurs LFS et formats invalides. La limite de textures est commune au serveur et au client : 1 à 64. Les nouvelles routes conservent la protection Tailscale existante et ne divulguent aucun chemin local.

`avatar-models.js` valide et gèle le catalogue, avec repli classique si la lecture échoue ou dépasse cinq secondes. Il ne charge aucun manifeste de modèle. Le sélecteur attend la disponibilité du renderer et se désactive pendant une sélection ; `JadeAvatar.state` et `jade-avatar-state` portent l’état réellement obtenu.

`avatar-model-loader.js` détient toutes les textures avant le montage SDK. Il attend la fin de tous leurs chargements, conserve le handle du modèle avec `fromSync`, puis nettoie aussi les échecs partiels. Le remplacement libère les ressources du modèle, du Core, du MOC et du corps Pixi. Un garde ciblé sur le constructeur de l’adaptateur 0.4.0 traite le cas où la construction interne échoue après allocation du Core. Un seul canvas, un observateur de taille et un ticker d’application sont conservés pour la session.

Les sélections rapides sont sérialisées : un chargement devenu obsolète se termine puis est détruit sans être monté avant le suivant. Une destruction échouée reste bloquante, même si un nouveau choix est demandé. Les transports de conversation et d’audio restent indépendants du remplacement visuel, ainsi que la pièce, l’onglet et le plein écran.

`JadeSeatedScene.deactivate()` retire immédiatement le corps, annule son image en cours et invalide ses continuations par génération. Le décor portrait déjà validé reste identifié par `data-portrait-ready=true`. Le premier démarrage classique conserve la validation atomique du couple décor/corps ; ensuite un échec du corps ne retire plus le décor. Le cadrage du modèle actuel conserve le repère assis existant ; le profil complet reçoit un cadrage générique avec priorité à sa partie supérieure dans les mini-scènes.

## Vérifications effectuées

- **Suite Python complète : 747 tests réussis en 33,982 s**, aucun échec ni test ignoré dans la suite principale. Les tests de l’export autonome et de sa copie passent aussi.
- **13 suites JavaScript réussies**, dont les trois nouveaux tests de catalogue/UI, de ressources du chargeur et de cycle de vie. Syntaxe des 12 modules PWA vérifiée. Les deux workflows `jade-rebuild.yml` et `jade-economy-tests.yml` exécutent les nouveaux tests.
- **Preflight : 263 fichiers Python/TOML**, compilation Python, contrat documentaire et contrôle du diff réussis.
- Tests de ressources : textures en échec et encore en vol, destruction unique des textures partagées, échec SDK avant/après construction interne, destruction Core/MOC, refus de toute allocation après une libération non confirmée et validation des références locales.
- Tests de cycle : disponibilité et choix identique, demandes rapides ou obsolètes, erreur et retour classique, échec de récupération borné, chargement initial raté puis nouvelle tentative, arrêt en onglet masqué, retrait et restauration du corps, rejet des images tardives.
- **Chromium avec WebGL et SDK réel : dix points de contrôle du cycle de sélection**, notamment défaut indisponible sans requête future, profil complet sans corps classique, retour classique, remplacement retardé, plein écran sans rechargement, panne HTTP 503 d’une texture puis récupération annoncée. Trois allers-retours supplémentaires conservent un seul modèle vivant, un seul canvas et des nombres stables d’entrées dans les caches Texture/BaseTexture. Aucune exception JavaScript non interceptée ni requête `/api/`.
- Caches Pixi mesurés : classique **3 textures / 3 baseTextures**, profil complet **2 / 2**, retour classique après les bascules **3 / 3**. Contrôle du modèle actuel en paysage **800 × 393** : **16,20 px** au-dessus de la tête et **22,86 px** sous le menton, fond sans couture.
- La dernière contre-revue a corrigé deux défauts du repli DOM : le tick doit conserver le masquage du corps debout même sans compositeur ; un échec de création du compositeur doit libérer son conteneur arrière et la texture/baseTexture du sprite partiel. Le test de cycle provoque cet échec après allocation, vérifie le repli, la libération complète et la bascule suivante ; les tests ciblés de rendu, visibilité, ressources et le contrat Python de scène ont été rejoués avec succès.

Les contrôles navigateur utilisent le paquet r20 réel sous une deuxième route **uniquement dans le banc de test local**, afin d’exercer le futur emplacement sans raccorder le nouveau modèle. La panne de texture est injectée dans un contexte neuf, pour ne pas être masquée par le cache d’images du navigateur. Les avertissements de cette panne provoquée et du service worker désactivé dans le banc sont attendus.

## Validation distincte et limites

**Avis PO/QA indépendant favorable le 26/11/2026, sans défaut bloquant restant.** La contre-revue confronte l’interface, le cycle réel du SDK et les tests aux critères ci-dessus. Le périmètre préparatoire est couvert : classique par défaut, nouveau choix indisponible, corps séparé, remplacement exclusif et erreurs visibles. Les résultats distants sont à consulter sur les workflows associés au commit qui introduit cette passation ; ils ne sont pas anticipés par les résultats locaux consignés ici.

Aucun second modèle réel n’est déclaré compatible et aucun essai sur le Redmi physique n’est revendiqué. La configuration privée du PC n’a pas été modifiée. Les SDK et les scripts du banc de test restent hors du dépôt ; aucun fournisseur facturé n’est appelé par la recette.

## Branchement ultérieur

Le branchement du nouveau paquet reste une mission explicite. Son répertoire devra être configuré dans `JADE_MOBILE_SECOND_MODEL_DIR`, avec un manifeste `Jade.model3.json` et ses ressources matérialisées. Il faudra alors valider sa compatibilité SDK, son cadrage réel et ses capacités propres ; les expressions et l’Idle du classique ne lui sont pas appliqués automatiquement.

Sources mises à jour : [état fonctionnel](../../handbook/BRANCH_STATE.md), [guide technique](../../handbook/TECHNICAL.md#sélection-du-modèle-mobile-26112026), [journal technique](../CHANGELOG.md) et [index des passations](README.md).
