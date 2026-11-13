# Revue croisée PO / architecture / QA / audio — Étincelle et moteur d'intentions

> **Addendum ultérieur :** cette revue décrit l'état **avant** l'intégration du pitch. Le filtre +2 demi-tons est désormais codé sur `develop` sous réserve de FFmpeg Rubber Band ; les tests et les prérequis sont consignés dans [PITCH-SHIFT-ETINCELLE-20261113.md](PITCH-SHIFT-ETINCELLE-20261113.md). Aucun rendu vocal réel n'a été validé ; conserver les conclusions de recette ouverte.

**Date :** 13 novembre 2026  
**Branche :** `develop` uniquement, pas de déploiement local.  
**Référence fonctionnelle :** [VOICE-PROFILES-20261113.md](VOICE-PROFILES-20261113.md).

## Verdict de la revue

**Développement et tests hors ligne : intégrés. Recette audio réelle : pas encore validée.**

### Contrôle produit (PO / UX)

- Voix **Étincelle** sélectionnée par défaut : `shimmer`, vitesse `1.25`. Friponne (`coral`) et Rosée (`marin`) restent des alternatives **documentées**.
- Intention explicite à **chaque réponse** via `[INTENT:label]`, produite par le LLM ; **une seule intention dominante par réponse**, pas un changement d'émotion au milieu de chaque phrase. C'est volontaire pour préserver le délai et le coût. La granularité par phrase serait une **évolution de contrat** distincte.
- Texte effectivement publié à partir de `Reply.text` **sans métadonnées** ; l'intention est `Reply.intent`. Les sorties console, chat, Discord, HTTP, sous-titres OBS et TTS reçoivent cette version nettoyée.
- Un tag absent ou un label inconnu entraîne `neutral`; ne jamais exploiter des instructions vocales arbitraires produites par le modèle.
- La voix garde son rôle de personnage espiègle et jeune adulte ; pas de féminisation caricaturale, voix enfantine ou affection systématique.

### Architecture et revue de code

- `intent_engine.py` constitue la source de vérité : liste fermée de 7 labels, directions TTS **statiques**, contrat de prompt et parseur streaming/non-streaming.
- Le parseur attend que le préfixe soit décidé avant de délivrer le texte au découpage en phrases. Les tags fractionnés sont correctement retenus ; un tag supplémentaire qui apparaît **dans le corps** est éliminé sans changer l'intention déjà fixée. Les crochets ordinaires sont conservés. Les métadonnées manifestement incomplètes entraînent une erreur au lieu d'être émises comme parole.
- Les chemins WAV et PCM progressif conservent leur rôle ; la chaîne early-speech reçoit l'intention **avant la première phrase**. La synthèse classique conserve le traitement neutre si une autre API TTS est explicitement choisie.
- Les paramètres provenant du LLM ne sont **jamais interpolés directement** dans les instructions TTS : un identifiant autorisé déclenche une consigne écrite dans le code.
- Les sessions Realtime peuvent recevoir des instructions modifiées entre tours ; un contrôle hors ligne vérifie deux intentions successives sur une même connexion WebSocket, sans doubler les appels audio.
- **Pas d'algorithme de pitch** activé. Le +2 demi-tons reste une hypothèse à tester ; le moteur OpenAI ne fournit pas ce réglage numérique.
- Les variables privées locales et profils d'environnement restent prioritaires sur les valeurs publiques du dépôt. `develop` ne constitue pas une preuve du modèle, de la voix ou de la vitesse réellement lancés sur le PC.

### Assurance qualité

**Tests automatisés, sans requête OpenAI réelle :**

- Préfixe valide, absent, inconnu, mal formé, incomplet ; découpage caractère par caractère.
- Suppression des tags inline supplémentaires, y compris lorsqu'ils sont scindés en fragments.
- Préservation des expressions ordinaires entre crochets.
- Absence de métadonnées dans `Reply.text` et dans l'historique.
- Routage de la direction statique jusqu'au payload `session.update`, avec voix `shimmer`, vitesse `1.25`, et **texte TTS propre**.
- Reconnexion non nécessaire quand l'intention change sur une connexion Realtime déjà établie.
- Régressions existantes (Discord, audio, interruption, pipeline, sous-titres, sécurité) conservées.

**Résultat observé sur le commit applicatif :** [GitHub Actions](https://github.com/goldaj/jade-vtuber/actions/runs/43485778125), Ubuntu : **422 tests, 2 ignorés**, compilation Python et parcours hors ligne réussis. Le scan des secrets est également réussi. La CI ne permet **pas** de confirmer l'effet acoustique des instructions ni le comportement sur un vrai salon Discord.

## Ce qui n'est PAS validé et reste à recetter

| Point | État | Conséquence / décision |
| --- | --- | --- |
| Perception des 7 intentions par `shimmer` en français | **Non testé à l'écoute** | Le catalogue est une liste de *directions demandées*, non d'émotions natives garanties. Supprimer/fusionner celles qui ne donnent aucun contraste audible. |
| Exactitude des mots réellement prononcés (TTS Realtime) | **Non garantie** | Instructions strictes ; les réponses du fournisseur peuvent différer malgré tout. Écoute nécessaire. |
| Latence fin de parole → premier son sur téléphone | **Non mesurée** | Le préfixe ajoute quelques tokens et attend sa fermeture ; ne pas annoncer une amélioration sans mesure avant/après. |
| Dépense API réelle par tour | **Non mesurée** | Pas d'appel LLM/TTS de classification supplémentaire, mais le prompt d'intention et les consignes vocales consomment des ressources. |
| Configuration privée réellement chargée sur l'ordinateur | **Non vérifiée** | Confirmer `JADE_TTS_VOICE` et `JADE_TTS_SPEED` dans le fichier privé / environnement, sans en publier les secrets. |
| Pitch post-traité +2 demi-tons | **Non implémenté** | N'activer qu'après contrôle des formants, des artefacts et du délai CPU. |
| Changement d'intention au sein d'une même réponse | **Hors périmètre actuel** | V2 : concevoir des métadonnées par segment si les tests utilisateurs le justifient, avec plafonnement du nombre de synthèses. |

## Critères d'acceptation proposés pour la recette réelle

1. **7 cas vocaux** (neutral, playful, excited, curious, tender, reassuring, serious), même texte de base avec formulations adaptées si nécessaire, écoute sur téléphone / Discord. Vérifier par écoute que chaque intention retenue est **reconnaissable, intelligible et naturelle**.
2. **3 cas de robustesse** : réponse sans balise, avec label non reconnu, avec balise fragmentée. Aucune chaîne `INTENT` ne doit être audible ou visible.
3. **2 cas de continuité** : passage direct `playful` → `tender` entre deux tours, puis interruption/révocation de session Discord, sans reprise de phrase ni doublon.
4. **Coûts / latence** : mesurer nombre d'appels, tokens, durée fin de parole → première trame Discord et première syllabe audible sur téléphone. Comparer au témoin antérieur `coral` / 1,5×.
5. **Validation personnelle** : confirmer que le jeu d'acteur correspond au caractère de Jade et que les moments tendres restent rares et spontanés.

**Go/no-go :** la CI donne le feu vert pour **un essai encadré sur `develop`**, pas un go automatique pour la production. Ne fusionner vers `main` ou déployer comme configuration définitive qu'après recette réelle et accord du propriétaire.

## Améliorations futures à garder dans le backlog, pas dans ce patch

- V2 du contrat : émotions **par phrase** en conservant un seul modèle de dialogue, sans multiplier inconsidérément les appels TTS ; définir un changement de schéma testable et une politique de repli.
- Catalogue versionné des directions réellement **validées à l'écoute**, au lieu de confondre instructions possibles avec capacités garanties de chaque voix.
- Évaluation de la pertinence du label généré par le LLM sur un lot de conversations représentatives, sans coût de classification au fil de l'eau.
- Possibilité de conserver plusieurs presets accessibles via configuration, seulement si l'usage justifie l'interface.
