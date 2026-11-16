# Plan d’exécution après la revue Astra

> Revue Astra terminée le 2 novembre : appliquer [06-ASTRA-REVIEW.md](06-ASTRA-REVIEW.md), qui précise arrêt, audio, HTTP, dépendances et Git. Le lot 0 est accompli. La publication du candidat sur la branche source de PR intervient **avant** la CI finale ; le lot 6 conserve seulement la fusion et la mise en service.

**Plan préparé, non exécuté.** Cette passe s’arrête à la documentation demandée. Aucun service Jade n’est actuellement en production selon le propriétaire. La proposition est une seule intégration du code consolidé vers `develop`, puis une première mise en service privée avec fonctions activées progressivement. Si le propriétaire choisit plus tard une autre branche de release, reporter la cible explicitement avant toute mutation distante.

## Lot 0 — Contre-lecture Astra

Lire `AGENTS.md`, le journal et les cinq documents de ce dossier. Revoir le graphe, les huit reproductions, les quatre constats de code et la portée de la validation. Décider la politique d’arrêt, l’expiration HTTP et le périmètre des connecteurs de la première mise en service. Produire un avis daté avec réserves et modifications du plan. Aucun travail d’asset 2D.

**Sortie attendue :** plan et liste de corrections relus, incertitudes explicitement conservées. La bascule de modèle est effectuée manuellement par le propriétaire, comme il l’a demandé dans le présent chat.

## Lot 1 — Geler les références et préparer l’intégration locale

1. Relever l’état propre/sale de chaque worktree utile. Ne pas actualiser ou changer de branche le clone historique sans en préserver le travail éventuel.
2. Relire l’état distant des branches/PR avant `fetch` : si les SHA diffèrent de `snapshot.json`, refaire les comparaisons et revoir la portée du plan.
3. Conserver la branche documentaire et son commit. Créer une branche d’exécution isolée depuis cette branche, pour emporter la documentation et le code consolidé.
4. Intégrer les **six commits documentaires** de `develop` à cette branche d’exécution, par un merge explicite conservant l’historique. Vérifier le diff indexé, les journaux et le maintien des quatre documents ; aucun arbitrage aveugle `ours`/`theirs`.
5. Conserver les références historiques. Aucune suppression, réécriture d’histoire, récupération automatique du coffre ou nettoyage de l’espace disque.

Exemple de commandes **à exécuter seulement à la reprise autorisée**, depuis la copie d’audit propre et après contrôle de dérive :

```powershell
Set-Location 'D:\Codex\projects\jade-migration-20261102'
git status --short --branch
git fetch origin
git rev-parse origin/develop origin/research/gpt6-jade-publication-readiness-20261028
git rev-list --left-right --count origin/develop...origin/research/gpt6-jade-publication-readiness-20261028
# Si les références ont changé : revoir le relevé avant de continuer.
git switch -c codex/jade-runtime-integration-20261102 codex/migration-audit-20261102
git merge --no-ff --no-commit origin/develop
git diff --cached --stat
git diff --cached --name-only -- jade-modeling
# Relire le contenu et l’historique documentaire avant de créer le commit de merge.
```

Ces commandes ne constituent ni une demande de push ni une autorisation de déploiement. Le clone partiel n’est pas une sauvegarde ; toute sauvegarde privée de Git/LFS/configuration doit être traitée séparément, sans journaliser les données.

## Lot 2 — Corriger arrêt, échéances et ressources

Premier sous-lot : F03 arrêt immédiat/gracieux, F02 terminaison du lecteur et fermeture des clients/services. Le consommateur doit refuser de nouvelles admissions après fermeture ; le mode immédiat ne doit plus démarrer de travail fournisseur. Conserver un mode de drainage explicite si utile.

Deuxième sous-lot : F05 requêtes expirées, annulation des travaux en file, erreurs de réponse, cohérence entre délai HTTP et délai du pipeline. La fermeture du navigateur ou un 504 ne doivent pas provoquer une relance opaque du même travail. Définir le résultat d’une annulation lorsque l’appel fournisseur a déjà commencé : l’absence de facturation ne peut pas être garantie rétroactivement.

Troisième sous-lot : F04 sessions globalement bornées et F12 test d’erreur fournisseur réellement représentatif. Ajouter les régressions déterministes au rythme de chaque correctif ; consigner les résultats réels dans `TASKS.md`.

**Acceptation :** arrêt borné sous queue pleine/sortie bloquée, pas de nouveau travail après arrêt ou échéance, aucune tâche/processus orphelin, mémoire bornée sous sessions renouvelées, historique cohérent après erreur.

## Lot 3 — Corriger voix et connecteurs séparément

1. F01 coordination capture/lecture et D04 fermeture Discord/FFmpeg ; couvrir les deux ordres de concurrence et les erreurs lecteur.
2. F09 isolation des sorties : un canal facultatif défaillant ne doit pas supprimer le texte ; erreurs observables sans contenu privé.
3. F07 surcharge Twitch : conserver le PONG et la connexion, définir abandon et métriques. Revoir D03 authentification/expiration avant endurance.
4. F06/F08 cycle de vie Discord vocal et slots des participants ; F10 mentions explicitement désactivées pour le texte. Définir D05 périmètre des salons/participants.
5. Revoir D06 admission HTTP et limites globales ; garder l’écoute sur loopback.

**Acceptation :** tests de chaque défaut d’abord rouge sur la baseline puis vert après correction, suite complète toujours verte, modes externes toujours opt-in. Discord vocal peut rester désactivé à la première mise en service si ses incertitudes persistent ; ne pas le présenter comme validé.

## Lot 4 — Installer et migrer la configuration sans perte

Créer un venv de déploiement séparé de l’audit et de Python global sous D:. Choisir seulement les extras utiles, produire un verrou de dépendances compatible Python 3.11/Windows et l’outil d’installation retenu, vérifier `pip check` et une installation neuve depuis ce verrou. La liste de versions observée pendant l’audit n’est **pas** ce verrou de production.

Le chargement doit conserver la priorité : environnement du processus → fichier privé sélectionné → profil non secret choisi → valeurs par défaut. Préserver le chemin privé existant via `JADE_SECRETS_FILE` ; ne pas déplacer le coffre sous prétexte que les nouveaux outils sont sur D:. Ne pas recopier `.env.example` par-dessus le coffre. Préparer une proposition de configuration **sans valeurs sensibles** avant modification.

| Réglage ou comportement | Migration à prévoir |
| --- | --- |
| `OPENAI_API_KEY`, `BOT_NAME` | Noms conservés ; vérifier présence sans affichage |
| LLM/STT/TTS/voix | `JADE_LLM_MODEL`, `JADE_STT_MODEL`, `JADE_TTS_MODEL`, `JADE_TTS_VOICE`, modèles configurables ; aucune promesse de latence |
| Ancienne voix ElevenLabs | Valeurs privées conservées dans l’archive ; plus utilisées par le chemin actif OpenAI |
| Twitch | `TWITCH_TOKEN`, `TWITCH_CHANNEL` conservés ; `TWITCH_BOT_LOGIN` requis pour IRC ; `JADE_TWITCH_ENABLED` puis option CLI, envoi séparé `JADE_TWITCH_SEND` |
| OAuth Twitch historique | Anciens client/refresh conservés hors Git ; nouveau connecteur sans refresh automatique à résoudre ou documenter |
| Discord texte/vocal | `DISCORD_TOKEN`, `DISCORD_VOICE_CHANNEL` conservés ; activations distinctes ; l’ancien `DISCORD_GUILD` n’est pas un filtre de salons du runtime actuel |
| Audio et OBS | Choisir `JADE_AUDIO_OUTPUT=ffplay` si souhaité, chemin `JADE_SUBTITLE_PATH` explicite et accessible en écriture ; préserver le câblage OBS existant avant toute modification |
| Queue, mémoire, délais | Paramètres actuels + nouvelles bornes retenues lors des correctifs ; relever les valeurs souhaitées sans inventer celles du poste |
| HTTP/téléphone | Désactivé par défaut ; token dédié hors Git, loopback ; tunnel et accès distant différés |
| Persona | `JADE_PROMPT_FILE` ou `JADE_ASSETS_ROOT` facultatifs ; préserver le prompt privé, tester fichier explicite absent/illisible |
| VTS et asset 2D | Conserver désactivés pour cette migration ; pas d’export, mapping, rig, animation ou recette visuelle |

Ne pas activer simultanément tous les modes pour vérifier une installation. Les vérifications hors ligne ne nécessitent aucune valeur du coffre ni aucun compte.

## Lot 5 — Recette privée progressive et CI

1. Réexécuter suite, compilation, diagnostic et CLI depuis l’installation verrouillée. Ajouter Windows à la preuve et vérifier l’installation des extras retenus sans ouvrir les connecteurs.
2. Le diagnostic Actions commence dès le lot 1. Après validation locale, pousser le candidat relu sur la source de PR #2 sans force-push, puis obtenir les exécutions finales en relevant source, cible et commit testé. Ne pas qualifier l’échec sans étape comme une régression Python ; ne pas remplacer la CI distante par une ancienne réussite.
3. Lors de l’étape réelle autorisée, tester OpenAI texte à faible volume, puis WAV/lecture, puis micro ; relever temps de capture, STT, LLM, TTS et lecture, erreurs et consommation observée. Préparer les limites de dépense avant les appels.
4. Tester Twitch seul et Discord texte seul, dans un contexte privé et périmètre défini. Tester envoi uniquement lorsque souhaité. Discord vocal ensuite seulement si F06/F08/D04/D05 sont clos.
5. Faire une répétition prolongée avec ralentissements, reconnexions et arrêt opérateur. Le temps de recette et les seuils de latence attendus doivent être choisis avant de conclure ; aucun chiffre de réussite n’est fixé arbitrairement ici.

**Acceptation :** preuves par fonction activée, arrêt efficace, absence de boucle audio et d’erreur fatale, ressources bornées, configuration privée préservée et versions reproductibles. Les fonctions non validées restent désactivées et signalées.

## Lot 6 — Une seule intégration et première mise en service

1. Comparer la branche d’exécution à la dernière tête `develop` ; à la reprise autorisée, conserver si possible la PR #2 en avançant normalement sa branche source avec le travail relu, sans force-push. Une PR de remplacement reste une solution si l’état distant a changé ou rend cette voie inadaptée. Ne pas rouvrir la PR #1. Consigner la PR unique de référence.
2. Réconcilier les documents historiques en conservant leur origine, vérifier le lock, la CI finale et les choix de connecteurs. L’asset 2D doit rester identique.
3. Après validation de la reprise, fusionner une seule fois vers `develop` avec un **merge commit**, sans squash/rebase, sans force-push et sans fusion additionnelle des ancêtres. Préserver `speechtotext-discord` avec la matrice de reprise fonctionnelle.
4. Créer une référence de release privée au commit accepté, installer dans un répertoire neuf avec son venv et ses paramètres sélectionnés. Prévoir un lancement manuel supervisé avant tout mécanisme de démarrage automatique. Aucun stream public implicite.
5. Consigner le commit réellement lancé, la commande, le venv et les modes activés, sans secrets ni transcriptions. Définir la branche de production durable à ce moment si une branche distincte de `develop` est souhaitée.

## Retour arrière

Avant première mise en service : conserver les références exactes de départ, l’ancien clone, le venv et la proposition de configuration. Un échec de recette se traite par arrêt du nouveau runtime et reprise hors ligne ; **ne pas relancer automatiquement l’ancien runtime de 2025**, dont la sûreté n’est pas validée.

Après intégration Git : annuler un correctif ou la fusion par un commit de revert relu sur une branche dédiée, puis PR ; aucun `reset --hard` ou force-push sur la branche partagée. Après première release : arrêter ses entrées/sorties et revenir à une release antérieure seulement si celle-ci a elle-même été validée ; sinon rester arrêté. Les frais déjà engagés ne sont pas annulables par un revert.

Le chantier F11/publication de sources, la purge historique, la rotation générale des anciens secrets, les nouveaux modules produit et le travail 2D restent des lots séparés. Ils ne doivent pas étendre silencieusement cette migration applicative privée.
