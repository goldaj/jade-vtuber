# Passation — UX mobile Jade (22/11/2026)

- **Mission :** demande propriétaire sur `develop` : retirer rappels de l'accueil et onglet Activités, montrer les rappels en liste directement avec création repliée, remplacer les deux boutons de push par des radios, espacer les redémarrages, rendre le plein écran réellement immersif et restaurer l'icône d'en-tête.
- **Base :** `4b34841f4d5503a1d5fe7199a232d3e3d63897dd` ; aucun travail sur `main`.
- **Architecture :** HTML/JS/CSS de la PWA uniquement. Liste du scheduler PC inchangée ; les radios gèrent exclusivement l'abonnement aux notifications Android, dont l'état est lu depuis le navigateur sans permission automatique. Sur échec, la sélection revient à l'état confirmé.
- **Immersion :** classe `is-room-only` sur le shell existant ; les autres panneaux sont masqués, mais le DOM Live2D reste monté avec son ResizeObserver. Demande Fullscreen API facultative, repli CSS si API non disponible, bouton de sortie persistant.
- **Icône :** `/icon.svg` déjà servi localement, utilisé en en-tête ; les icônes installées Android ne changent pas.
- **Vérification :** structure et syntaxe contrôlées avant publication ; test Python de contrat adapté. Pas de test physique Android, pas de push réel ni de redémarrage du PC réalisé. Contrôler sur Redmi le rendu, la sortie immersive, le clic notification et les notifications activées/désactivées avant Done.
- **Suivi unique :** `REC-040` `À valider`. Pas de nouvelle carte DEV ; aucune modification backend, secrets, audio, mémoire ou Discord.
