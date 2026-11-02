# Contexte de projet ChatGPT : Jade

> Journal pour Codex créé le 2026-10-24. **Partiel**, car les exports complets de toutes les conversations ChatGPT ne sont pas accessibles dans cette session. Les résumés ci-dessous ne sont pas des citations.

## Périmètre et état vérifiables
- Dépôt : `goldaj/jade-ai-vtuber`.
- Objet d'après le README : Personnage VTuber IA, bot Python 3.11 (Twitch/Discord/LLM/audio) et art/rig Live2D VTube Studio. État r21, jalon natif v30, runtime animé r20, fichiers volumineux LFS.
- Invariants : Lire jade-modeling/MODEL_GUIDE.md, manifestes d'assets et PRIVATE_CONFIGURATION.md ; ne pas toucher aux éléments de coffre privé ou à l'historique sensible ; pas d'appels payants non requis.
- Entrée de vérification : `poetry run python -m unittest discover -s tests -v` ; `python jade-modeling/verify_assets.py` après récupération Git LFS.

## Échanges et références retrouvés

2026-09-21 — Utilisateur, résumé non verbatim : récupérer les échanges et l'état de Jade depuis GitHub/Codex. Assistant, résumé non verbatim : séparation du corps client et du moteur d'inférence local, avec feuille de route V1/V2 et migration depuis services cloud.

2026-10-18 13:24:13 UTC — Utilisateur (extrait exact) : « N'écrase aucun repo existant. »

2026-10-24 — Utilisateur (verbatim, heure indisponible) : « je te demande de lire mes repo git où tu es le dernier utilisateur, de rajouter un AGENTS.md pertinent s’il n’y en a pas. Mais en plus, tu rajoutera un document repérable par codex [...] où tu mets l’intégralité de nos échanges liés à ce projet. Mes questions, tes réponses [...] et les horodatages si tu les as. » (extrait avec ellipses signalées, donc non intégral).

## À compléter avec les transcriptions sources
**Manquent :** questions/réponses intégrales de chaque session de conception, horaires individuels de certains messages et échanges Codex non publiés. Ne jamais reconstituer un dialogue en prétendant citer des propos exacts.

Lorsque des exports ChatGPT authentiques sont fournis, les archiver par session, avec date ISO/fuseau, rôles et texte intégral en préservant leur ordre. Revoir toute donnée sensible avant de pousser sur GitHub. Après chaque modification, ajouter les échanges exacts nouvellement disponibles, puis actualiser les décisions et l'état vérifié.

## Reprise du 24 octobre 2026 : accès navigateur local
- **Utilisateur (verbatim, heure non fournie)** : « Est-ce qu'il y aurait d'autres choses à faire sur d'autres repo ? Notamment sur Jade ou n'importe lequel autre - juste ne touche pas au bot hyperliquid pour le reste de la journée (on pourra revenir dessus une autre fois). »
- **Assistant (résumé non verbatim)** : poursuit sur Jade, en restant dans sa
  branche de refonte et sans intervenir sur aucun bot Hyperliquid. Ajoute une
  page de chat sur HTTP loopback, la séparation des conversations par session
  et des tests simulés ; aucun appel OpenAI facturé ni déploiement.
- **Note de sécurité** : le navigateur local ne conserve ni token ni messages ;
  l'accès téléphone par tunnel chiffré/authentifié reste à faire.

## 2026-10-24 : diagnostic matériel/API préparatoire
- **Utilisateur (verbatim, heure indisponible)** : « vas-y avance sur toutes tes propositions ».
- **Assistant (résumé non verbatim)** : poursuivi sur la même branche isolée ;
  commande de diagnostic `--preflight` qui ne lance ni réseau ni microphone
  et teste les conditions avant activation, tests unitaires, guide d'accès
  téléphone par HTTPS/Tailscale Serve sans exposition publique. Les API,
  appareils et tunnels réels sont **à tester sur le PC**.
- Aucun secret lu dans les comptes, aucun appel facturé, aucun déploiement,
  aucun merge et aucune modification de dépôt Hyperliquid.


## 2026-10-29 — Intégration de la passation Codex MODE L2D


## Projet de protocole Codex pour le rig — 2026-10-28 (en attente de validation)

- Utilisateur (résumé non verbatim, heure précise non attestée) : demande que le dépôt conserve les consignes de relais entre Astra, Terra et Sol et qu'il les examine avant qu'elles soient utilisées par Codex. Souhaite entendre une explication détaillée et pouvoir demander des modifications.
- Assistant (résumé non verbatim) : propose un plan directeur global produit par Astra, l'exécution ordinaire par Terra, le dépannage intermédiaire par Sol, des relais manuels annoncés et des validations de jalons par Astra.
- Réalisation vérifiée : les fichiers `jade-modeling/RIG_CODEX_PLAYBOOK.md` et `jade-modeling/RIG_CODEX_STATE.md` ainsi qu'un renvoi dans `AGENTS.md` ont été ajoutés à la branche `develop`. Ils ont ensuite été **expressément marqués comme BROUILLONS NON VALIDÉS**, l'état étant `approval_pending` ; ils ne doivent pas être appliqués avant validation explicite du propriétaire.
- Le plan directeur de rig `jade-modeling/RIG_MASTER_PLAN.md` n'a **pas** été créé et aucun rig, export Cubism ou VTube Studio n'a été modifié/testé dans ce travail documentaire. Les branches de refonte applicative n'ont pas été modifiées.


La politique Tera par défaut du 29/10 remplace les directives antérieures imposant Astra en début de projet. Les preuves et validations matérielles doivent rester explicites.

## 2026-11-02 — Préparation de migration applicative

- Utilisateur (résumé non verbatim, heure individuelle indisponible) : contrôle rapide de la refonte, documentation de migration, erreurs et incertitudes ; visuel/animation 2D laissés de côté ; relecture manuelle Astra avant retour Terra pour les travaux réels.
- Utilisateur (verbatim, clarification, heure individuelle indisponible) : « Il n’y a pas encore de production active ».
- Assistant (résumé non verbatim) : copie d’audit isolée sur D:, carte des branches, plan, reproductions synthétiques et tests. Aucun correctif runtime, merge, push, appel payant ou changement d’asset.
- [Index des conversations](conversations/INDEX.md), [dossier de migration](migration/2026-11-02/README.md). Les anciennes décisions sont conservées comme historique.

## 2026-11-02 — Relecture Astra et retour Terra

- Utilisateur : demande accessible intégralement dans [le journal de revue](conversations/2026-11-02-astra.md), avec instruction de limiter les tokens.
- Assistant (résumé non verbatim) : confirme le graphe et les reproductions, précise les pièges d’implémentation et corrige l’ordre push/CI ; valide le plan amendé pour la reprise Terra. Aucun code applicatif modifié.
