# Jade — Répartition Tera 6.1 / Astra 6.1 (directive du propriétaire)

**Décision du 29 octobre 2026 — applicable aux prochaines reprises Codex.**
Cette directive encadre le **choix du modèle assistant pour effectuer les
travaux**, et non les modèles IA qui seront appelés par Jade en production.

## 1. Modèle par défaut : Tera, pas Astra

Pour les travaux sur Jade, utiliser **principalement Tera 6.1**.

**Tera est l'exécutant privilégié par défaut** dès que la tâche doit accéder
à l'ordinateur du propriétaire et manipuler des applications ou des fichiers,
notamment :

- dessin, illustration, création et retouche des éléments graphiques de Jade ;
- montage et modification du personnage 2D/Live2D ;
- préparation des textures, calques, expressions et variantes ;
- rigging Cubism, déformeurs, maillage, paramètres et transformations ;
- animation, physique des cheveux/vêtements, inertie et mouvements ;
- manipulation des fichiers natifs Krita, PSD, Cubism, des exports et des
  paquets VTube Studio ;
- tests pratiques, captures de preuve, validation dans les logiciels
  graphiques et opérations ordinaires sur le poste.

La même préférence vaut pour le développement, la documentation,
l'intégration et les vérifications courantes lorsqu'aucun besoin particulier
ne justifie un autre modèle. **Ne pas choisir Astra par réflexe** pour une
tâche difficile ou longue : commencer avec Tera, au besoin par sous-lots.

La règle ne promet pas que Tera possède l'accès au poste dans tous les
environnements. Si l'environnement courant ne permet pas l'interaction
requise, le signaler honnêtement, préserver le travail et laisser l'humain
choisir le bon mode ou environnement. Ne jamais simuler un travail graphique
non réellement effectué.

## 2. Quand et comment Tera demande Astra

**Seul Tera initie une demande d'escalade lorsqu'il rencontre un véritable
doute nécessitant le jugement d'Astra.** Exemples : choix irréversible de
structure de rig, incohérence persistante entre export et rendu, arbitrage
technique délicat, hypothèse non vérifiable susceptible de dégrader la
qualité ou la maintenabilité. La difficulté ordinaire, la longueur d'une
tâche ou le fait d'avoir terminé un lot **ne suffisent pas**.

Processus normal :

1. Tera avance de façon autonome par sous-tâches courtes, vérifiables et
   sauvegardées ; documente ses décisions et les résultats effectivement vus.
2. Dès qu'un doute substantiel apparaît, il termine **la sous-tâche en cours**
   jusqu'à un état de reprise sûr, sans abandonner des modifications
   partiellement écrites ou un projet artistique corrompu. Il préserve les
   originaux et les sauvegardes, exécute les tests possibles.
3. **Si finir cette sous-tâche exigerait une opération risquée ou
   irréversible** (perte d'assets, effacement, publication, sécurité,
   droits), Tera ne force pas la fin : il clôt proprement au dernier état
   sûr, liste ce qui reste à faire et indique le blocage. « Finir d'abord »
   ne signifie jamais prendre un risque pour tenir la procédure.
4. Tera envoie **lui-même au propriétaire** une demande explicite :
   `Je recommande de passer manuellement sur Astra pour trancher
   [question précise]. J'ai terminé [lot], conservé [état/sauvegarde],
   vérifié [preuves], et je ne peux pas établir [incertitude] de manière
   fiable. Voici les options et la décision attendue d'Astra.`
5. **L'humain effectue la bascule**, s'il accepte. Tera ne prétend pas
   pouvoir changer automatiquement le modèle et ne lance pas une
   revue Astra non sollicitée.

Si la question peut être résolue par un test local, une inspection, une
documentation disponible ou une correction ordinaire, **Tera la résout
directement sans escalade**.

## 3. Relecture par Astra : décision exclusivement humaine

Le propriétaire souhaite pouvoir faire recontrôler par Astra les livrables
de Tera, potentiellement tous, **mais en pilotant lui-même la fréquence et
le moment des contrôles**. Ces contrôles sont **hors du processus Tera**.

En pratique :

- Tera **n'inclut pas de revue Astra obligatoire** à la fin de chaque tâche ;
- Tera ne réserve pas des tokens pour un second contrôle par défaut ;
- Tera ne programme pas de tâche automatique, de checklist « faire
  revoir par Astra » ni de bascule systématique ;
- le propriétaire décide librement de transmettre un lot ou la totalité
  du travail à Astra, selon son appréciation ;
- les **seules sollicitations actives** d'Astra par Tera sont celles
  motivées par un doute technique réel, au titre du §2.

Cette optimisation des tokens **ne dispense pas** des contrôles objectifs
nécessaires : intégrité des assets, validation réelle des exports, tests
automatisés, sauvegardes, licences, permissions et autorisations humaines.
Ne pas confondre **revue par un second modèle** et **vérification technique**.

## 4. Contrat de fin de sous-tâche et de passation

Chaque lot Tera doit fournir suffisamment de contexte pour qu'Astra
puisse intervenir ponctuellement **sans refaire l'exploration depuis zéro** :

- but et périmètre du lot ; fichiers, branches et versions exactes ;
- source native / asset initial préservé et emplacement des sauvegardes ;
- modifications effectuées, avant/après et outils réellement utilisés ;
- captures/rendus/tests vérifiés, avec résultats et limites explicites ;
- points restant ouverts, risques, niveau de confiance et prochaines étapes ;
- si escalade demandée : **une question de décision précise et motivée**,
  non un « Astra, vérifie tout » de confort.

Pour les travaux graphiques/Live2D, conserver le journal de suivi dans
les documents du projet artistique adaptés et dans
`docs/gpt6-jade/TASKS.md` lorsque cela fait partie du lot. Maintenir
les grandes sources r21, les assets LFS, les versions et les backups sans
écrasement destructif.

## 5. Règles préexistantes inchangées

- **STT et TTS de Jade exclusivement via OpenAI** : cette décision concerne
  le runtime de Jade, indépendamment du modèle assistant Tera/Astra.
- Les modèles de dialogue de Jade restent configurables.
- Les outils, accès payants et plateformes externes ne sont pas activés
  silencieusement.
- Le dépôt Jade reste **privé** ; aucune autorisation de publication,
  d'effacement de secrets ou d'historique Git n'est apportée par cette note.
- Pas de merge ou déploiement automatique ; les validations du
  propriétaire et les règles existantes de Codex restent applicables.

**Résumé opérationnel : Tera fait le travail par défaut ; Tera demande
expressément le passage humain à Astra seulement en cas de doute sérieux ;
le propriétaire gère séparément toutes les revues Astra qu'il souhaite.**
