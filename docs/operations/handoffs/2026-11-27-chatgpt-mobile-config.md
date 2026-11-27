# Mission : Config mobile épurée et réglages persistants

- **Demande :** Jason/Goldaj, 27 novembre 2026 ; modifications directes de l’application et sauvegarde automatique de ses configurations.
- **Branche :** `feat/mobile-config-cleanup-20261127`, depuis `develop` à `0122897af7135fe5498e60c4978d6bc4aad20543`. Intégration cible : `develop`.
- **Organisation :** réalisation HTML/CSS, persistance et intégration conversationnelle réparties entre trois agents ; contre-revue distincte des contrôles et scénarios par `mobile_qa`.
- **Backlog :** modification de l’interface de fonctions existantes. REC-050 conserve sa recette Live réelle ; REC-041/043 et les autres recettes physiques ne changent pas de statut. Aucun Done matériel déduit des tests de ce lot.

## Critères et réalisation

| Demande | Résultat |
| --- | --- |
| Profil → Config, Mon espace privé → Paramètres | Navigation et titres changés ; modèle libellé « Modèle ». |
| Live sans encart, sous forme de case | Case Mode Live dans Paramètres, au-dessus de Voix activée et des animations ; descriptifs permanents retirés. |
| Voix déplacée du Chat | Case cochée au premier usage dans Config ; préférence appliquée avant les requêtes. |
| Rappels sur le téléphone | Case unique ; autorisations et inscription réelles déterminent l’état confirmé, sans paragraphes de succès. |
| Suivi OpenAI | Jour, mois, date du relevé, lien de facturation ; aucun bouton de rafraîchissement ni commentaire permanent. |
| Gestion GIT | Nouveau titre, logs actualisés et défilants automatiquement, filtre conservé, lien « page de secours ». |
| Associer un compte | Trois étapes reformulées comme demandé ; génération et copie de commande conservées. |
| Décor/Recentrer | Bandeau au-dessus de la scène d’Accueil ; absent des mini-scènes et du plein écran. |
| Boutons enfoncés | Assombrissement, réduction/translation et ombre intérieure sur les boutons actifs, connexion et secours compris. |
| Conservation des configurations | Voix, notifications, modèle, décor, animation, secousses et filtre des logs sauvegardés automatiquement ; Live déjà persistant côté Jade. |

## Périmètre technique

`mobile_web/salon.html`, `app.js`, `preferences.js`, `avatar-models.js`, `room-motion.js`, `portrait-bedroom-motion.js`, `avatar-shake.js`, `live-client.js`, `login-guard.js`, feuilles de style et page de secours. Route statique ajoutée dans `mobile_gateway.py` et allowlists d’export actualisées dans `tools/jade_publication_export.py`. Aucun fichier artistique modifié.

Le record `jade.mobile.preferences.v1` est borné, versionné et limité à des booléens/valeurs énumérées. Les lectures rejetent les champs inconnus ; les échecs de stockage gardent le salon utilisable. Le modèle et le décor ne sont sauvegardés qu’après réussite. Un modèle temporairement indisponible conserve son choix enregistré malgré le repli. L’URL de décor explicite prime sur ce choix. Les permissions ne sont pas redemandées à l’ouverture ; aucun jeton, message, fichier privé, audio, identifiant de compte ou état de capture n’est conservé.

## Vérifications exécutées

- Suites Node de préférences : plusieurs ouvertures partageant le stockage, écrasement volontaire d’un réglage, validation des types/champs, stockage corrompu/refusé, deux onglets préservant leurs champs distincts.
- Modèle/décor : réouverture, sélection ratée, option indisponible, priorité d’URL ; cycles de libération des modèles inchangés.
- Animations/secousses : choix restaurés et aucune demande de permission au chargement ; paragraphes normaux masqués, échecs utiles visibles.
- Client réel chargé dans un DOM de test : Live/son/rappels en cases, anciens éléments supprimés réellement absents, voix OFF réappliquée avec `speak:false`, aucune reprise micro en revenant ON, inscription des rappels refusée/réussie/retirée et restauration.
- **27 commandes navigateur du workflow et des nouveaux scénarios : toutes réussies.**
- **Chromium : 20 vérifications de géométrie réussies**, Accueil/Chat/Rappels/Config/plein écran, aux dimensions 393×852, 320×640, 852×393 et 1280×900. Bandeau au-dessus de la scène, aucune superposition ou largeur débordante, plein écran exactement aux dimensions du viewport.
- **Huit états d’appui vérifiés**, navigation, Git, association, Recentrer, micro et plein écran. Captures inspectées par l’agent de présentation et l’agent principal ; vrai décor local, contrôles simulés, aucun Live2D actif ou appel réseau réel.
- **Suite Python complète : 980 tests, zéro échec, 12 ignorés** (transports Discord optionnels absents de cet environnement). L’export autonome exécute également sa propre suite avec succès. La première passe a détecté le nouveau fichier non encore indexé dans l’export ; indexation et allowlist des nouveaux tests corrigées avant la passe complète finale.
- `compileall`, préflight hors ligne (289 fichiers Python/TOML), `scripts/check_docs.py` et `git diff --cached --check` : réussis.

## Passe distincte de validation

`mobile_qa` a vérifié séparément les parcours Live/voix/rappels/logs/facturation et les contrôles retirés, exécuté les régressions frontend et signalé le style autonome de la page de secours. Ce dernier point est corrigé. `mobile_ui` a validé la géométrie et les états visuels à partir de captures Chromium. **Conclusion de la revue du 27/11 : périmètre demandé implémenté, contrôles automatiques et visuels réussis.** Aucune recette matérielle Redmi/OpenAI/Discord n’est déclarée réussie dans cette mission.

## Livraison et limites

Le lot est destiné à un commit cohérent sur `develop`, sans modification de `main` et en conservant les travaux concurrents. Les choix locaux survivent à la fermeture, au rechargement et au redémarrage sur la même origine ; l’effacement des données du navigateur ou une nouvelle installation implique un nouveau stockage. Le son est ON en l’absence de choix, et reste OFF si l’utilisateur l’a décidé. Les gestes de cadrage temporaires ne sont pas de nouveaux paramètres de Config.

Sources actuelles mises à jour : [état de develop](../../handbook/BRANCH_STATE.md), [guide utilisateur](../../handbook/USER_GUIDE.md), [technique](../../handbook/TECHNICAL.md), [architecture Live](../../architecture/LIVE_MOBILE.md), [journal](../CHANGELOG.md).
