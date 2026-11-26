# DEV-032 — Création et livraison de fichiers (22 novembre 2026)

## Objectif validé par Goldaj
Pièce jointe téléchargeable sur demande explicite : mobile texte / oral (oral + réponse écrite), Discord MP texte, salon texte, vocal (oral + chat texte natif au même salon). Goldaj seul par défaut avec son lien de compte Discord préexistant ; droits futurs configurables ; format explicite respecté, HTML par défaut pour code/site non précisé, ZIP multi-fichiers ; expiration au bout de 24 heures, y compris suppression des messages Discord porteurs de fichiers. Pas d'URL brute envoyée par Jade.

## Clôture REC-039, validation fonctionnelle du 22/11/2026

**Validateur : propriétaire Goldaj, sur son installation réelle.** Après la correction et l'ouverture par défaut du mode `all` sur `develop` (commit `c4eba34a`), le propriétaire affirme : « je confirme et valide la recette de l'ensemble de cette US. Tout marche, tu peux mettre à done ». Les essais mobiles écrits/oraux avaient déjà été confirmés ; les trois parcours Discord (MP écrit, public écrit, vocal public) précédemment KO sont compris dans l'acceptation finale. Les scénarios précédemment décrits comme en échec sont conservés dans la passation pour l'historique, pas comme défauts actuels. La validation est globale : aucun détail inédit sur l'expiration minute par minute, les caches Discord ou les métriques réelles n'est ajouté. **REC-039 passe en Done ; DEV-032 reste une référence historique.**

## Décision de modification du 22/11/2026 : génération ouverte par défaut

Sur décision explicite du propriétaire, **tout compte utilisateur réellement identifié par le transport Discord a le droit de générer un fichier par défaut**, en MP, salon public ou vocal, même sans liaison avec Goldaj. Le mode `all` devient le réglage initial du code et de la configuration ; `owner` et `allowlist` sont conservés comme modes restrictifs à activer volontairement. Le service n'a plus besoin de consulter SQLite pour autoriser un utilisateur Discord dans le mode ouvert. Les événements synthétiques et les identités de transport absentes restent exclus ; la PWA demeure protégée par son authentification habituelle. **La version précédente du besoin « Goldaj seulement » est remplacée, et non simultanément active.** L'expiration 24 h, les canaux de livraison et la confidentialité des fichiers publics restent inchangés. Les éventuelles valeurs privées `JADE_DOCUMENT_ACCESS_MODE=owner` explicitement définies dans un environnement continueront de primer sur le défaut et devront être ajustées sur ce poste pour appliquer la nouvelle politique.

## Retour de recette et correctif ciblé du 22/11/2026

- **Recette réelle par le propriétaire :** mobile écrit OK, mobile vocal OK ; **Discord MP écrit KO, salon public écrit KO, vocal public KO**. Sur Discord, Jade dit explicitement que la fonctionnalité est indisponible ; aucune pièce jointe observée. REC-039 reste **À valider** avec échec Discord documenté, sans revenir sur les parcours mobile réussis.
- **Cause de code identifiée :** la politique `owner` reconnaissait automatiquement la PWA mais dépendait exclusivement du sous-système de mémoire pour Discord. Si celui-ci était désactivé, un compte Discord pourtant lié était systématiquement refusé. Même lorsqu'il était activé, le prompt ne précisait pas que l'outil était disponible pour un compte lié. Les paramètres privés réels n'ont pas été consultés : ne pas prétendre que cette condition est confirmée sur le PC.
- **Correction :** source persistante SQLite des identités réutilisée en lecture seule même si la mémoire est désactivée ; décision d'autorisation tracée en métadonnées uniquement (`document_access_decision` : origine, permis, raison sans identifiant ni texte). Prompt explicite pour compte Discord autorisé ; refus libellé comme un refus de permission pour un compte non associé, jamais comme une limitation générale de Discord. Tests avec vrais comptes liés fictifs, trois parcours et émission native de fichiers simulée. Aucune association de compte supprimée, aucune permission globale accordée.
- **À confirmer en recette :** après mise à jour/redémarrage du runtime sur `develop`, essayer un petit fichier TXT en MP, en salon public puis dans le vocal. Si Jade refuse encore, exploiter le champ `reason` de `document_access_decision` pour distinguer `verified_link` de `not_linked` / `identity_lookup_failed` sans recopier d'identifiants privés. Ne pas réexiger de liaison des comptes déjà validée.

## État technique
Travail poussé sur `develop`, non mergé sur `main`. Nouvelle couche `src/jade_runtime/documents.py`, outil de fonction Responses, contexte documentaire dans Dialogue, modèle Reply avec pièces jointes, boucle Runtime, relais PWA/Discord, réglages et tests `tests/test_jade_documents.py`. Pas de fournisseur supplémentaire ni de fichiers stockés dans Git.

## Risques et points à valider
- **Vérifications achevées le 22/11 :** [CI Linux/Windows verte sur dc8f0fb2](https://github.com/goldaj/jade-vtuber/actions/runs/45043574769), contrôles Responses API et secrets réussis, tests unitaires de génération/permissions/rétention réussis. Une erreur de syntaxe initiale a été réparée dans `64d3c374` ; les derniers correctifs sont inclus dans `dc8f0fb2`.
- Vérifier en recette réelle les cinq parcours, la visibilité des boutons PWA, le chat natif vocal, les permissions et suppression Discord ; ne pas redemander la validation de liaison des comptes que Goldaj a déjà confirmée fonctionnelle.
- Vérifier l'expiration à 24 h, après redémarrage et en cas d'indisponibilité Discord. Copies téléchargées et caches Discord non effaçables hors contrôle de Jade.
- **Limites acceptées expressément par le propriétaire :** taille des fichiers bornée par le budget de sortie du modèle, intentionnelle ; PDF stdlib minimal en Latin-1, Unicode complet non requis pour cette US.
- Pas de conversion/lecture de fichiers entrants, pas de code généré exécuté ; dossier de sortie privé par défaut dans `D:/Jade/private/jade-documents/` sous Windows.
- Les documents publics doivent éviter la divulgation de contexte privé d'autres canaux ; validation de non-divulgation en recette.
- Un fichier créé sans livraison réussie doit être signalé comme indisponible et supprimé au plus tard à expiration. L'envoi n'est pas égal à un téléchargement effectif.

## Décision de suivi mise à jour

**DEV-032 a été transférée à REC-039 le 22/11/2026, puis REC-039 a été clôturée Done sur validation explicite du propriétaire**, suivant la règle de suivi unique approuvée par le propriétaire. Aucune implémentation supplémentaire attendue sur le périmètre convenu. Les vérifications de confidentialité et les comportements Android/Discord réels relèvent désormais de REC-039 ; aucun test humain n'est inventé. En cas d'échec de recette, ouvrir une anomalie DEV distincte et ciblée. Tâches Twitch/OBS/microphone physique non touchées.
