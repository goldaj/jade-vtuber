# Contre-revue du dépôt public — reprise Terra

Revue achevée le 2 novembre 2026. Périmètre contrôlé : `main` à `d653c77`
et `develop` à `0a00624`, avant ajout du présent compte rendu. Le dépôt officiel
est `goldaj/jade-vtuber`. Les travaux suivants doivent rester sur `develop`.

## Verdict et limites

La migration publique conserve la version applicative intégrée et les sources
du personnage ; le démarrage et les tests hors ligne réussissent. Aucun secret
connu ni clé privée n'a été découvert dans les éléments contrôlés. La sauvegarde
privée est accessible et vérifiée.

Cela ne prouve pas une équivalence complète avec tous les comportements du bot
historique. Deux écarts fonctionnels sont décrits ci-dessous. Les connexions et
appareils réels restent à recetter ; aucun nouvel appel payant, microphone ou
envoi de message externe n'a été déclenché pendant cette revue.

## Préservation vérifiée

- Comparaison avec la dernière version intégrée avant export public (`2de15c6`) :
  324 fichiers suivis avant, 328 sur `main`, aucun chemin suivi retiré. Les quatre
  ajouts sont documentaires. `main.py`, `src/`, `tests/`, `config/`, le prompt,
  `pyproject.toml` et `poetry.lock` sont identiques après normalisation des fins
  de ligne. Les modifications de métadonnées et de documentation assainissent
  les chemins personnels ; elles ne changent pas le runtime.
- Les ensembles de 103 objets LFS avant/après sont identiques. Le vérificateur
  des ressources contrôle 202 fichiers et 23 références, sans erreur ;
  `git lfs fsck HEAD` réussit.
- Dans le miroir historique, huit des neuf branches sont déjà incluses dans
  l'ancien `develop`. Seule `speechtotext-discord` possède sept commits divergents.
  Son delta de neuf fichiers est conservé dans
  [l'archive assainie](../../archives/BRANCHE-DISCORD-HISTORIQUE.md).
- Le dépôt privé de sauvegarde conserve les configurations, l'historique original
  et les instantanés des branches. Quatorze fichiers distants correspondent
  exactement aux copies locales ; les treize références du miroir original
  figurent dans le bundle privé. Les objets LFS sont stockés séparément dans le
  dépôt officiel et dans les copies locales, pas dans les bundles.
- Cette garantie ne couvre pas les anciennes versions supplémentaires et deux
  commits inatteignables du clone C: supprimé avec l'autorisation antérieure du
  propriétaire. Elle couvre les branches récupérées et leur historique accessible.

## Sécurité vérifiée

- Le dépôt officiel est public et ne possède que `main` et `develop`. Aucun
  ancien commit sensible n'a été importé dans cette nouvelle histoire.
- Gitleaks 8.30.1 : zéro alerte sur les deux commits publics contrôlés.
- Recherche exacte de vingt valeurs de référence privées, dont l'identifiant
  Twitch historique précédemment oublié, en UTF-8 et UTF-16 : zéro occurrence
  dans les 377 objets Git accessibles et les 103 objets LFS. Aucun bloc de clé
  privée PEM trouvé. Les deux archives KRA, soit 939 membres décompressés, ne
  contiennent aucune de ces valeurs.
- Les anciens commits testés ne sont pas résolus par l'API anonyme du nouveau
  dépôt. Les anciens dépôts original et transitoire retournent 404 publiquement
  et ne sont plus accessibles au compte propriétaire lors du contrôle.
- La configuration active correspond à sa sauvegarde GitHub privée. Les clés
  n'ont pas été remplacées, conformément au choix explicite du propriétaire.
  Cette sauvegarde en clair dans un dépôt privé est le risque accepté ; elle
  n'est pas synchronisée automatiquement après une modification locale.

Ces contrôles ne certifient pas l'absence de secrets inconnus dans tout format
binaire propriétaire ou contenu encodé. Ne jamais copier les valeurs privées
de référence dans une CI, un rapport, un test ou le dépôt public.

## Points pour Terra

### P2 — Compléter le contrôle des secrets sur les futurs changements

Le workflow `.github/workflows/jade-publication.yml` ne se déclenche que sur
certaines PR filtrées par chemins ou manuellement. Son scanner analyse le contenu
courant par des règles limitées ; l'option `--history` de
`tools/jade_publication_audit.py` ne contrôle que les noms de fichiers historiques.
Le workflow de tests sur push n'exécute pas un scan spécialisé de tous les blobs.
La CI verte actuelle ne constitue donc pas une protection complète contre un
futur secret ajouté, notamment dans une archive documentaire.

1. Sur `develop`, prévoir un contrôle spécialisé sur chaque push de `develop` et
   `main`, et sur les PR, sans restriction de chemins qui exclurait une archive
   ou un document. Utiliser une version déterminée du scanner et des permissions
   GitHub minimales en lecture.
2. Définir explicitement la portée de l'historique récupéré et scanné ; ne pas
   présenter un checkout superficiel comme un contrôle de toute l'histoire.
3. Garder les sorties expurgées. Ne jamais injecter les vrais secrets de Jade
   dans GitHub Actions pour effectuer ce contrôle.
4. Vérifier le blocage avec des valeurs synthétiques dans des fichiers temporaires
   non publiés, y compris dans un document hors des chemins filtrés actuels.
5. Conserver une revue des identifiants privés : les scanners génériques peuvent
   ignorer un identifiant client qui n'est pas lui-même un secret d'authentification.

Il s'agit d'un défaut de prévention, pas d'une fuite actuelle découverte.

### P2 — Réconcilier explicitement les deux comportements historiques

Les sources sont préservées, mais une archive n'est pas une fonctionnalité active.
Ces écarts proviennent de la refonte antérieure, pas de l'export public.

- **Obtention initiale Twitch OAuth :** l'ancien WIP proposait une procédure
  manuelle. Le code actuel conserve le rafraîchissement dans
  `src/twitch/twitch_auth.py`, mais pas un parcours sûr d'obtention initiale.
  Ne pas recopier l'ancien script qui affichait les jetons. Pour restaurer cette
  capacité, vérifier la documentation Twitch actuelle, écrire directement dans
  la configuration privée sélectionnée et ne jamais journaliser les identifiants
  ni les réponses contenant des jetons. Tester avec un fournisseur simulé avant
  toute connexion réelle autorisée.
- **Routage vocal Discord :** `src/jade_runtime/output.py` envoie au lecteur
  Discord secondaire uniquement les réponses issues de `discord_voice`.
  L'ancien WIP visait une diffusion plus large dès qu'il était connecté.
  Conserver le comportement sûr par défaut ; documenter la portée actuelle.
  Si le propriétaire veut restaurer la diffusion d'autres origines, la rendre
  explicitement configurable et tester séparément les sources autorisées et
  interdites. Ne pas activer une diffusion large implicitement.

Le remplacement d'ElevenLabs par OpenAI est conforme à la décision utilisateur ;
ce n'est pas une perte à corriger. Ne pas remettre en service l'ancien runtime.

### Recette restante, hors de cette passe

La voix OpenAI, le micro physique, les connexions Twitch/Discord, le vocal Discord
et l'intégration VTube Studio/OBS n'ont pas été validés en conditions réelles
pendant cette revue. Suivre une recette distincte et autorisée, avec dépenses
minimales. Ne pas confondre les tests simulés avec cette validation.

## Preuves de fonctionnement

- 84 tests unitaires locaux réussis pendant cette contre-revue.
- Démo effectivement lancée : saisie d'un message, réponse en mode démo, sortie
  normale. Aucune clé requise pour ce parcours.
- [CI main réussie](https://github.com/goldaj/jade-vtuber/actions/runs/41500138863).
- [CI develop réussie](https://github.com/goldaj/jade-vtuber/actions/runs/41500903491).

## Consigne de reprise

La passe Astra est terminée. Aucun changement applicatif n'est requis pour
conserver le démarrage actuel ; les améliorations ci-dessus se feront sous Terra
sur `develop`. Pas de nouvelle recréation du dépôt ni de fusion automatique vers
`main`. Si le chat est relancé en restant sous Astra, demander seulement le
passage à Terra, conformément à l'instruction de suivi du propriétaire.
