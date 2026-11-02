# Passation des pistes Jade provenant de Notepad — 2026-11-01

**Destination :** dépôt privé Jade, branche `develop`. **Origine :** entrées historiques B-0016 et B-0020 de `goldaj/Notepad`, supprimées de son registre et de ses archives actifs après migration. Les identifiants sont de provenance, non des index vivants.

**Aucune évolution ci-dessous n'est considérée comme codée, testée ou intégrée par cette migration.** Relire la PR de refonte en cours avant d'intervenir : pas de fusion/déploiement automatique. Se conformer au processus Codex/Jade et préserver la priorité aux services OpenAI.

## B-0016 — Évaluer speech-to-speech natif

# B-0016 — Jade : expérimentation speech-to-speech
Date : 2026-10-28 (heure exacte inconnue)
Source : conversation « Bloc notes conversation ».
Catégories : piste-projet-existant, action-recherche, rappel.
Fidélité : texte utilisateur intégral (verbatim).

> Pour Jade, quand on reprendra les développements, il faudra qu'on pense à tenter un modèle speech to speech au lieu du modèle actuel qui fait speech to text et text to speech avec l'inférence au milieu bien sûr. J'ai l'impression que ça change quand même énormément le taux de latence. Et il existe maintenant des modèles qui font ça. Il faudra juste voir si c'est facile à intégrer si on veut l'intégrer, si on y a confiance. Et le coût finalement du token par rapport à l'API OpenAI qu'on a privilégiée actuellement sur la branche GPT-6

Note de classement : évaluer ultérieurement la latence, les modalités d'intégration, la fiabilité et le coût par rapport à la chaîne STT → inférence → TTS actuelle. Projet Jade déjà démarré ; ne pas ajouter aux idées de projets autonomes.

---

## B-0020 — Les cinq modules Jade retenus

# B-0020 — Cinq évolutions fonctionnelles de Jade : Showrunner, Smart Chat, MoodSync, Control Room, Rehearsal Lab

- **Date :** 2026-11-01, Europe/Paris ; heure précise du message non vérifiée.
- **Source :** conversation ChatGPT « Avancement pour Codex » (conversation présente), et non le fil historique intitulé « Bloc notes conversation ».
- **Catégories :** piste-projet-existant, action-recherche, consigne.
- **Projet existant concerné :** [Jade](https://github.com/goldaj/jade-ai-vtuber), en particulier la [PR de refonte #2](https://github.com/goldaj/jade-ai-vtuber/pull/2).
- **Décision :** les cinq propositions intéressent le propriétaire et doivent être conservées pour la suite ; **pas de demande de développement immédiat, ni d'inscription comme projets autonomes**.
- **Fidélité :** demande utilisateur ci-dessous verbatim ; description et scores repris fidèlement de la réponse visible de l'assistant, reformattés en Markdown pour archivage. Notes subjectives, non mesures.

## Demande et validation du propriétaire

**Demande initiale (utilisateur, verbatim) :**
> T'aurais d'autres idées à me proposer ?
> D'une utilité d'au moins 5/10 en pertinence ou en aide d'avancement pour Jade
> Et d'une difficulté de maximum 5/10, ou quelque chose dont tu es SÛR de pouvoir le développer toi-même au besoin, parce que toutes les infos nécessaires existent déjà quelque part.
>
> Fait moi 5 proposition. Réfléchis bien, je ne veux pas des idées nazes.

**Décision ultérieure (utilisateur, verbatim) :**
> tout est intéressant, mets tout ça dans le bloc notes

## 1. JADE SHOWRUNNER — Animatrice autonome

- **Utilité estimée : 9,5/10 ; difficulté MVP estimée : 4/10.**
- **Promesse :** transformer Jade en véritable animatrice capable de prendre des initiatives, même sans sollicitation d'un spectateur.

Le bot Jade est surtout réactif : un spectateur écrit, Jade décide si elle répond. Showrunner ajouterait un planificateur d'initiatives contrôlé : sujets spontanés, relances après des périodes de silence, sondages improvisés, transitions entre séquences et animations, sans monopoliser la parole.

**MVP visé :** moteur de cinq types d'initiatives, détection des silences, machine à états lisible, quotas d'appels IA, refroidissements entre événements et commande pause ; simulation d'une émission de trente minutes entièrement hors ligne.

**Intégration envisagée :** orchestrateur, moteur de dialogue et sorties texte/voix de Jade. Distinguer les initiatives internes des messages de Twitch/Discord pour éviter les boucles et les interactions superflues. Les initiatives restent désactivables.

**Tests de succès proposés :** zéro boucle infinie, pas d'initiative si arrêt/pause actif, fréquence bornée, non-interruption abusive d'un message prioritaire, journal chronologique contrôlable.

## 2. JADE SMART CHAT — Gestionnaire d'attention

- **Utilité estimée : 9/10 ; difficulté MVP estimée : 4/10.**
- **Promesse :** choisir intelligemment les messages auxquels Jade répond, au-delà de la simple probabilité aléatoire du code actuel.

Prioriser les messages selon leur intérêt conversationnel, ancienneté, pertinence, situation du live et diversité des personnes ; regrouper les demandes semblables ; prévenir les réponses répétitives au même intervenant et les réactions trop tardives.

**MVP visé :** moteur de scoring déterministe et explicable, dédoublonnage/groupement, équité entre auteurs, gestion de l'obsolescence des messages et comparaison avec la sélection aléatoire actuelle sur des conversations simulées.

**Intégration envisagée :** événements des connecteurs Twitch et Discord, modèle `Incoming`, file d'attente et `Dialogue`, en préservant les mécanismes de sécurité existants et le caractère optionnel des réponses.

**Tests de succès proposés :** réponse prioritaire à une question pertinente simulée, absence de famine d'un auteur, comportement stable malgré une arrivée massive de messages, budget d'appels plafonné et décisions auditables.

## 3. JADE MOODSYNC — Cohérence émotions / voix / expressions

- **Utilité estimée : 8,5/10 ; difficulté MVP estimée : 4/10.**
- **Promesse :** rapprocher ce que Jade dit et la manière dont elle apparaît et s'exprime.

Jade possède des expressions dans le modèle Live2D et le nouveau runtime sait déjà transmettre des hotkeys à VTube Studio. Il manque une couche qui relie la réponse à une intention émotionnelle et qui lisse les transitions.

**MVP visé :** catégoriser une réponse en nombre réduit d'états (neutre, amusement, surprise, agacement, tristesse), faire correspondre ces états à des expressions configurables et à des consignes vocales lorsque le TTS le permet, limiter les changements incohérents via temporisations, états et retour au neutre.

**Intégration envisagée :** `Reply`, sortie OpenAI TTS et connecteur VTube Studio déjà présents ; ne pas modifier les assets ou le rig Cubism pendant ce MVP.

**Tests de succès proposés :** bon ordre des transitions sur messages simulés, comportement de repli sans VTS, aucun appel externe dans les tests automatisés, correspondances configurables et validées ensuite visuellement sur la machine utilisateur.

## 4. JADE CONTROL ROOM — Cockpit de supervision pendant le direct

- **Utilité estimée : 9/10 ; difficulté MVP estimée : 4/10.**
- **Promesse :** permettre à l'opérateur de contrôler Jade sans interrompre ni redémarrer son application.

Afficher les états de la capture, du dialogue, de la synthèse vocale, de la lecture, de la queue, des connexions et des erreurs ; disposer d'actions sûres : pause/reprise, coupure de la voix, désactivation d'un connecteur ou des réponses et arrêt d'urgence des sorties. Suivre les volumes d'appels et des coûts **estimés** et distincts des montants réellement facturés.

**MVP visé :** panneau web local, endpoints de télémétrie anonymisée et de commandes authentifiées, tests de permissions et contrôles d'arrêt. **Aucun accès Internet public ni exposition en clair sur le réseau local.**

**Intégration envisagée :** API HTTP loopback et interface locale présentes dans la PR Jade. Distinguer interface de supervision et client conversationnel du téléphone ; conserver les garde-fous sur les clés et tokens.

**Tests de succès proposés :** aucune commande non authentifiée, aucune donnée confidentielle dans les logs ou métriques, arrêt fiable des sorties simulées et reprise contrôlée.

## 5. JADE REHEARSAL LAB — Répétition de lives hors ligne

- **Utilité estimée : 8,5/10 ; difficulté MVP estimée : 3/10.**
- **Promesse :** tester des situations de live suffisamment réalistes avant une diffusion Twitch.

Injecter des messages et situations simulées (plusieurs spectateurs, questions successives, silence, interruptions, ralentissements et erreurs de services, coupures Discord/Twitch), enregistrer les décisions, erreurs et chronologie, rejouer les incidents, générer un rapport exploitable.

**MVP visé :** dix scénarios reproductibles, faux connecteurs, horloge/événements simulés, captures de traces sans données réelles et rapport HTML avec indicateurs de fonctionnement.

**Intégration envisagée :** utiliser les contrats du runtime asynchrone de Jade et ses doubles de test ; aucun compte OpenAI ou Twitch requis. Les tests simulés ne prouvent pas que le matériel et les plateformes réelles fonctionnent.

**Tests de succès proposés :** relecture fidèle d'un scénario, invariants de file, absence de blocage, mesure des erreurs et distinction stricte entre résultat mock et preuve live.

## Synthèse d'arbitrage conservée

| Proposition | Utilité Jade (/10) | Difficulté du MVP (/10) | Développement hors ligne envisageable |
| --- | ---: | ---: | --- |
| Showrunner | 9,5 | 4 | Oui |
| Smart Chat | 9 | 4 | Oui |
| MoodSync | 8,5 | 4 | Oui, sauf validation visuelle |
| Control Room | 9 | 4 | Oui, sauf déploiement réel |
| Rehearsal Lab | 8,5 | 3 | Oui |

**Recommandation initiale de l'assistant :** les trois modules Showrunner + Smart Chat + MoodSync pourraient faire passer Jade d'un bot réactif à un personnage qui anime, choisit ses interactions et exprime visuellement sa personnalité ; Control Room et Rehearsal Lab faciliteraient la supervision et la validation. Il serait préférable de les développer **dans le dépôt Jade**, sur une branche d'évolution séparée, avec tests et passation à Codex, plutôt que créer cinq dépôts autonomes.

## Contraintes, vérifications et suites

- Le dépôt Jade contient déjà un runtime de messages, des adaptateurs Twitch/Discord, un service OpenAI TTS/STT, une API loopback, une interface web et une intégration VTube Studio préparatoire dans une **PR non fusionnée**. Ne pas dupliquer ces fondations et relire l'état réel des branches avant de commencer.
- Respecter la priorité à OpenAI pour STT/TTS, au temps de réaction court, aux coûts contrôlés et à la préservation de la personnalité de Jade.
- Aucun test effectué, aucun code écrit et aucune promesse d'intégration matérielle validée par cette seule archive.
- Ne pas confondre les estimations subjectives de difficulté avec une assurance absolue ; les tests hors ligne sont réalisables sans comptes, mais les scénarios live restent à vérifier.
- Ces cinq éléments sont **des évolutions d'un projet existant** : **ne pas** créer cinq entrées `N-XXXX` dans `idees.md`, ni cinq projets dans l'incubateur. Le propriétaire a demandé leur conservation dans Notepad.

## Contrats de reprise

- Développer les modules seulement après réévaluation de l'état effectif de `develop` et des PRs, sur branche isolée avec tests offline.
- Respecter les coûts et la latence, ne pas publier d'interface d'administration ou de secret sur Internet.
- La validation visuelle VTube Studio / Live2D, les tests d'API réels et les tests Twitch/Discord nécessitent leur propre preuve ; les mocks ne suffisent pas.
