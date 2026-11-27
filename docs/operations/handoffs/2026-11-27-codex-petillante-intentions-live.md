# Intonations et mouvements de Pétillante en Live

- Branche `fix/live-petillante-intentions-20261127`, depuis `develop@3b07700`. Contrôles rattachés à REC-049 et REC-052.
- Le serveur mobile actif annonçait une voix personnalisée sans repli. La configuration privée charge le profil `petillante` et les créations mobile et Discord Live incluent son identifiant personnalisé et la consigne du propriétaire. Le réglage propriétaire de GPT-Live Discord était sur OFF au contrôle. Un tour Discord en classique utilise la voix de cette chaîne. La nouvelle journalisation technique compare la voix demandée à celle annoncée par le fournisseur quand celui-ci renvoie sa configuration, avec résultat seul.
- GPT-Live reçoit la direction vocale de Pétillante et des indications pour distinguer les intentions à l’oral, avec un débit légèrement plus vif et une articulation nette. Les réponses déléguées envoient en plus une consigne silencieuse limitée au résultat du tour. Le modèle vocal garde la maîtrise du débit et de l’intonation. [Guide GPT-Live](https://developers.openai.com/api/docs/guides/live-prompting#pace)
- Sur la PWA, le trajet natif estime localement une intention visuelle à partir du début de la transcription de Jade et laisse l’intention déléguée piloter sa réponse lorsqu’elle existe. Le JavaScript exploite les expressions et mouvements A/B déjà intégrés au r21. La lecture déclenche le mouvement et la fin de parole ramène au repos. Sur Discord Live, les mêmes événements sont reliés à l’avatar local lorsqu’il est lancé.
- Recette restante. Comparer sur le téléphone plusieurs répliques enjouées, curieuses et rassurantes dans une même session, ainsi qu’une réponse déléguée. Comparer le débit et entendre les contrastes. Pour la recette Discord, vérifier le moteur réellement sélectionné avant d’évaluer la voix.

## Échanges accessibles

- **Propriétaire** (synthèse du 27 novembre) Confirme que le GPT-Live fonctionne. Demande de vérifier la voix choisie, de retrouver les intonations et les mouvements par intention, et d’accélérer légèrement le débit par défaut.
- **Assistant** (synthèse) Vérifie les réglages du serveur sans exposer d’identifiant. Identifie l’ancienne chaîne TTS propre au classique, le manque d’intention sur les tours natifs, et applique la direction de jeu puis la projection des intentions sur le modèle.

Les heures individuelles de la conversation, les identifiants de voix et les données privées ne sont pas repris.
