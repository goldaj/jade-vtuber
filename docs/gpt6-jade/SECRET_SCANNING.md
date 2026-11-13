# Contrôle des secrets du dépôt public

Le workflow `Jade secret scan` s'exécute sur chaque push de `main` et `develop`,
sur toute pull request et à la demande. Il utilise Gitleaks 8.30.1, téléchargé
depuis sa publication officielle et vérifié avec une empreinte SHA-256 fixée.
L'action de récupération est également fixée à un commit précis et n'enregistre
pas le jeton GitHub dans la configuration Git.

Le checkout récupère l'historique complet des références disponibles ; la
commande examine les branches et tags récupérés ainsi que `HEAD`, y compris le
commit de fusion des PR. Un autotest dans un dépôt temporaire crée un secret
fictif, le retire dans un second commit et vérifie que le scanner le retrouve
dans l'historique tout en expurgeant ses sorties. Le workflow n'affiche pas les
résultats détaillés et ne les publie pas comme artefacts.

En cas d'échec, relancer l'analyse localement avec un Gitleaks de confiance et
`--redact=100`, dans une copie privée, puis corriger la cause sans coller de
valeur ou de rapport contenant des secrets dans GitHub, la CI ou une discussion.
Le scanner n'utilise pas et ne doit jamais recevoir les secrets réels de Jade.

Un contrôle sur push se produit **après** l'envoi : il ne peut pas empêcher une
divulgation déjà faite. Les règles de détection ont des limites et le scan Git
ne lit que les pointeurs LFS, pas les fichiers LFS eux-mêmes ni les archives
binaires internes. Maintenir les secrets hors du dépôt, contrôler les fichiers
à partager et vérifier séparément les ressources binaires avant publication.
