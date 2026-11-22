# Audit technique, fonctionnel, non-régression et CI — PR brouillon #38

**Date :** 22 novembre 2026. **Source :** `goldaj/jade-vtuber`, branche `feature/jade-multicanal-memoire-observabilite-20261122` dérivée de `develop`. **Statut : revue statique ciblée et tests hors ligne ; aucune recette physique.** Ce document est une photographie du diagnostic, non un procès-verbal de validation utilisateur. Les statuts de backlog ne sont pas modifiés.

## 1. Verdict produit par ticket

| Carte | Code/livraison dans la branche | Écart ou vérification encore exigée | Conclusion |
| --- | --- | --- | --- |
| DEV-021 — conscience et actions intercanaux | Tâches propriétaire privées persistées en SQLite, reprise entre identités réellement liées, ordres explicites et envoi texte Discord uniquement vers la liste des destinations permises ; isolation des salons publics. | Le langage naturel arbitraire n'est pas interprété (limite **acceptée**, devenue RTE-18 P3) ; qualité des transferts sur vrai Discord / utilisateurs simultanés à vérifier. | **Implémentation A limitée, recette réelle ouverte**. |
| DEV-022 — recherche de souvenirs | Candidats SQL vérifiés par personne/portée, classement lexical avec récence et importance, repli conservateur, cache invalidé à l'écriture. | Pas d'index FTS5 ni recherche sémantique profonde ; maximum 512 candidats récents peut écarter un fait plus ancien. Absence de benchmark corpus long/homonymes et contradictions multi-sessions complet. | **Partiel**. |
| DEV-023 — mémoire préchargée | Cache LRU/TTL révisé par SQLite, vérification à chaque hit, invalidation identité/suppression/expiration, préchauffage propriétaire au lancement et membre Discord authentifié à l'entrée vocale. | Préchargement ciblé **L2 seulement** (pas L1 complet) ; ouverture effective de la PWA ne déclenche pas un nouveau préchargement après le lancement du processus ; voix Discord publique n'injecte volontairement aucune mémoire individuelle ; benchmark froid/chaud à obtenir. | **Partiel**. |
| DEV-024 — métrologie | Jalons serveur + durées de phases mémoire/LLM/livraison, durée STT mobile, tokens réellement renvoyés, p50/p95 par modalité, échecs/annulations, endpoint propriétaire. | Première lecture client non prouvée ; aucun son *humainement entendu* certifiable (LAT-21 P3) ; facture exacte par tour indisponible (LAT-22 P3) ; pas encore de référence représentative 10 tours par canal ni coût de mesure documenté sur PC. | **Partiel, limites acceptées**. |
| DEV-025 — conversations de groupe | Indices explicites de mention et réponse à un tiers + contexte récent borné du même salon, contrôle social facultatif sous budget. | Pas de suivi structuré de sujets parallèles, score précis sur corpus annoté, ni recette Discord réelle à plusieurs participants. | **Partiel**. |
| DEV-026 — personnalité évolutive | Profil versionné et reconstruit depuis mémoire consentie, priorisation, correction de préférences, Core sous l'autonomie de Jade et aucune curation LLM supplémentaire hors interaction. | Évolution expérientielle approfondie/reportée à NEW-37 P3 avec accord propriétaire ; continuité de la personnalité sur plusieurs semaines à observer en pratique. | **Implémentation conservatrice, validation longitudinale ouverte**. |
| DEV-010 — fenêtre / rideau | Repli statique qui évite de déformer le cadre existant. | Deux calques artistiques maîtres indépendants **absents** et animation finale non testable. | **Non terminé**. |
| DEV-020 — déploiement PWA | Superviseur local distinct du processus Jade, API loopback privée, liste de branches, confirmation, rollback best-effort et commandes mobiles. | Aucune installation ni recette réelles sur Windows, Tailscale/Android ; rollback peut échouer si dépendances modifiées, version Windows non validée. | **Code présent, pas accepté**. |
| OPS-015 — audit d'assets | Script d'inventaire en lecture seule, doublons SHA-256 et noms apparentés. | Comparaison sémantique CMO3/KRA/PSD et tableau artistique garder/archiver/supprimer **non réalisés**. | **Partiel**. |

## 2. Défauts techniques détectés lors de cette passe et corrections

1. **Dégradation indue des conversations privées par panne SQLite** : les accès au suivi de tâches pouvaient propager une exception jusqu'au runtime. Ajout d'une voie `_safe_tasks` : conversation ordinaire conservée, commande de tâche refusée avec message honnête et contenu privé absent des journaux. Test de non-régression d'une conversation normale lorsque la base des tâches lève `OSError`.
2. **Démarrage fragilisé par modules facultatifs** : si la création des tables de continuité ou le préchargement propriétaire échoue, Jade peut conserver son ancien dialogue et ses transports au lieu d'échouer pour cette amélioration. Tests d'injection de panne du préchargement.
3. **Jalons cumulés confondus avec durées** : la télémétrie calcule aussi `memory_duration_ms`, `llm_duration_ms` et `delivery_duration_ms` sur des marqueurs présents ; aucune durée inventée sur marqueur manquant. Test à horloge contrôlée.
4. **Réponse OpenAI incomplète avec consommation réelle** : si le fournisseur renvoie `incomplete`/`max_output_tokens`, les tokens existent parfois malgré le texte de repli. Ils sont enregistrés **sans réessai payé** ni montant de facture supposé. Test avec réponse synthétique plafonnée.

Ces correctifs ont été limités aux composants concernés : pas de refonte d'orchestrateur, de streaming, d'identification ou de prompt global.

## 3. Vérification CI et non-régression

Référence démontrée **avant** les correctifs de cette passe : commit `57177dd8`, trois jobs verts sur la même version :
- [Tests hors ligne économiques](https://github.com/goldaj/jade-vtuber/actions/runs/45004515348) : **637 tests**, **14 ignorés**.
- [Reconstruction CI Linux/Windows](https://github.com/goldaj/jade-vtuber/actions/runs/45004515408) : **637 tests**, Linux **3 ignorés**, Windows **2 ignorés**.
- [Scanner de secrets](https://github.com/goldaj/jade-vtuber/actions/runs/45004515358) : réussi.

**Important :** ces résultats anciens ne valident **pas** les nouveaux commits. Pour le verdict final, contrôler sur GitHub que le **HEAD actuel** de la branche est celui des trois exécutions réussies après les corrections. Un workflow annulé par commit plus récent n'est pas vert.

Les suites incluent simulations de mémoire, auth/identité, Discord, PWA HTTP/voix, outillage OpenAI, garde-fous de transcription, PCM, files, streaming et tests des fonctions introduites. Les messages `ERROR jade.runtime` dans les logs peuvent correspondre à des tests de pannes **délibérées** ; ne pas les compter comme bugs sans regarder la conclusion du test associé.

## 4. Recette physique impossible à conclure depuis GitHub Actions

- **Discord :** identités liées et déliées réelles, MP, salon autorisé, participants en groupe, interruptions, erreurs de permissions, non-divulgation de contexte et confirmation de livraison.
- **Android/PWA :** login Tailscale, voix (STT/TTS), streaming/annulation, long texte, autorisation de déploiement, affichage fenêtre/rideau (statiques tant qu'assets absents).
- **Windows :** superviseur lancé séparément et propriétaire du processus Jade, demande de restart, choix `develop` ou autre branche sans affecter le checkout de travail, échec de `git fetch`, échec de lancement, état du processus, rollback, déconnexion/rétablissement PWA.
- **Performance :** au moins dix tours représentatifs par modalité réelle, comparaison avant/après, latence perçue par le navigateur/périphérique et consommation totale fournisseur. Ne jamais prétendre mesurer le son réellement entendu si le matériel ne le permet pas.
- **Graphique/art :** produire et revoir les calques sources indépendants et l'inventaire sémantique avant suppression ou validation de DEV-010 et OPS-015.

## 5. Décision de gouvernance

**Ne pas passer les neuf cartes à Done, ne pas fusionner la PR #38 sur `develop` ou `main` sur le seul fondement de tests hors ligne.** Le propriétaire a expressément privilégié la stabilité ; les limites RTE-18, NEW-37, LAT-21 et LAT-22 sont conservées **P3** dans le catalogue des améliorations et n'entraînent pas de développement additionnel. Pour les autres écarts des cartes opérationnelles, demander une qualification de recette ou un arbitrage ultérieur seulement après validation de la branche.
