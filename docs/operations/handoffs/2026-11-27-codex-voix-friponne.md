# Friponne dans GPT-Live

Le 27 novembre 2026, le propriétaire a choisi Jade G · Friponne après l’avoir entendue dans le Playground OpenAI. La candidate avait été créée avec une hauteur de 94/100 et un débit de 73/100. L’essai initial a duré 21 secondes. Le propriétaire a demandé une légère accélération supplémentaire puis a approuvé cette version pour `develop`. [Échanges du chat](../../history/conversations/2026-11-27-evolution-voix-jade.md#nouvelle-audition-et-choix-de-friponne)

## Application du réglage

Sur `develop`, base `800b504`, le profil `friponne` associe la voix enregistrée à sa direction de jeu. `live_voice.py` décrit le timbre, l’accent d’Île-de-France et la façon de parler un peu plus vite. `live_config.py` transmet ces instructions aux sessions mobiles et Discord Live. La configuration privée associe `JADE_LIVE_VOICE_STYLE=friponne` au `JADE_LIVE_VOICE_ID` de la voix. Une installation configurée pour Pétillante peut continuer à s’en servir. [Guide de configuration](../../handbook/TECHNICAL.md#configuration-privée-live)

Le réglage porte sur l’enchaînement des mots dans chaque phrase. La courte pause avant une pique et l’articulation de la dernière syllabe font partie de la consigne de session. Le moteur vocal en interprète le tempo à chaque réponse.

## Vérifications et recette

Les 36 tests ciblés de configuration, de voix et de fournisseur Discord ont réussi avec Poetry. Un contrôle hors ligne de la configuration privée résolue a confirmé que les deux transports sélectionnent l’identifiant exact de la voix retenue et transmettent sa consigne complète.

Le contrôle documentaire a également relevé du texte libre dans la cellule de dépendances d’ART-015. La description de coordination a rejoint ses critères, avec ART-011 conservé comme prérequis dans la colonne dédiée.

Dans le Playground, la session de la voix retenue avec le débit ajusté a duré 25 secondes et a joué le passage jusqu’à la fin. Le propriétaire a validé la nouvelle Friponne à l’issue de cette écoute.

La [REC-052](../../backlog/02-RECETTE.md#rec-052--voix-friponne-avec-lavatar-de-jade-ancienne-dev-041) reste **À valider** sur l’application. Écouter une réponse native puis une réponse déléguée. Sur le téléphone, observer la bouche de r21 et son retour au repos pendant une pause ou une interruption. Sur Discord, écouter le débit et l’accent lorsque la politique du serveur sélectionne Live.
