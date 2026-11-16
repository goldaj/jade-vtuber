# Expérience produit, client mobile et poste local

| ID | Priorité / état | Amélioration proposée / condition de réussite |
| --- | --- | --- |
| UX-01 | P0 / C | **Recette PC neuf / réel** : installer Python/Poetry, dépendances Discord/DAVE, STT/TTS, modèle r20, VTube Studio, ffplay/Rubber Band et vérifier les chemins D: ; la Démo Express simulée ne prouve pas Jade réelle. |
| UX-02 | P1 / E | Stabiliser le **launcher unique --all-channels**, sans sélecteur de mode ; choisir branche, préflight honnête, messages d'erreur exploitables et configuration facultative des connecteurs sans masquer un prérequis absent. |
| UX-03 | P2 / P | Contrôler la **version du launcher installé hors dépôt**, diagnostiquer PID périmé, crash/reboot et reprise contrôlée sans boucle de frais API. |
| UX-04 | P1 / C | **PWA Android/Tailscale Serve** : tester URL HTTPS réelle, compte propriétaire, Bearer séparé, ACL, Wi-Fi et données mobiles ; aucune exposition Funnel ni détour par le VPS du bot trading. |
| UX-05 | P2 / E | Remplacer la **PWA push-to-talk** (capture WAV complète, réponse JSON/Base64) par l'audio streaming / interruption, une fois le parcours simple confirmé en réel. |
| UX-06 | P2 / E | Améliorer la **conversation mobile unifiée texte↔micro**, en conservant même session Goldaj, historique, intentions, option voix coupée et aucune sortie audio doublée sur PC. |
| UX-07 | P2 / P | **PWA visibilité / contrôle** : afficher un avatar sur décor sans fond vert quand l'écran le justifie, et s'éteindre à l'arrière-plan ; fournir un mode uniquement texte/voix. |
| UX-08 | P1 / C | Tester la **participation naturelle sans wake word** : 100 % de réponses attendues en solo admissible, 30 % de suivi spontané en groupe, sollicitations explicites prioritaires, silence/arrête/reprends, absence de gêne sociale. |
| UX-09 | P1 / C | Vérifier Twitch IRC en vrai : scopes OAuth, renouvellement du token, reconnexions, chat écrit et rate limits ; les spectateurs silencieux ne sont pas observés comme participants actifs IRC. |
| UX-10 | P2 / P | Panne réseau/mobile : affichage d'indisponibilité, reconnexion sans double génération payante, reprise du contexte autorisé, annulation lorsque client quitte l'écran. |
| UX-11 | P2 / P | Interface de commande **« personnes prévues aujourd'hui »** dans l'application privée, état de préchargement mémoire, suppression d'une préparation et diagnostics lisibles. Voir MEM-05. |
| UX-12 | P2 / P | **Interface utilisateur des souvenirs** : consulter, corriger précisément, supprimer et exporter ce qui appartient à l'identité authentifiée ; contrôles d'opt-in explicites pour tiers. Voir MEM-16. |
| UX-13 | P2 / C | Documenter et vérifier **mini-démos** séparées : Démo Express simulée et installation réelle avec préflight, coût autorisé et fonctionnalités effectivement utilisables. |
| UX-14 | P3 / D | Étudier un client mobile plus riche ou natif seulement après validation PWA, dépendances SDK Live2D et comparaison latence/batterie ; ne pas créer un APK par principe. |

**Sources :** [guide PC/Android](../history/gpt6-jade/HANDOFF-CODEX-MOBILE-20261115.md), [audit PWA](../history/gpt6-jade/AUDIT-REVUE-MOBILE-MEMOIRE-20261115.md), [launcher](../operations/reference/LAUNCHER-WINDOWS-20261115.md), [roadmap MVP](../history/gpt6-jade/ROADMAP-MVP-DISCORD-PRODUIT-MOBILE.md), [priorités historiques](../history/gpt6-jade/NEXT-PRIORITIES.md) (ne pas reprendre ses statuts littéralement).
