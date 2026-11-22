> **ARCHIVE / REMPLACÉ LE 22/11/2026 :** cette proposition de lecture cloisonnée est désormais obsolète. La nouvelle décision produit autorise la consultation globale des trois niveaux, sans filtrage d'identité ni de canal. Voir [`2026-11-22-jade-global-memory.md`](2026-11-22-jade-global-memory.md). Ne pas rétablir les restrictions décrites plus bas.

# Jade — incident mémoire Discord, diagnostic et correction (22/11/2026)

**Branche :** `develop`. **État :** code intégré ; validation Discord/PyCharm réelle à effectuer, **pas** une recette physique validée.

## Reproduction et causes

- Logs Discord vocal du 22/11 vers 10:41 : Jade dit ignorer son anniversaire alors que des tentatives de mémorisation ont eu lieu. Vers 10:42:27 et 10:42:56 : `Local Jade memory write was refused or failed: refusé`.
- `MemoryService.context_for` renvoie volontairement une chaîne vide dans les salons publics, même pour les souvenirs du **même interlocuteur, même salon**. Ce cloisonnement évite les fuites, mais Jade ne disposait **d'aucun outil de lecture** pour récupérer à la demande ses souvenirs SQLite.
- L'ancien `core_self` ne pouvait être écrit que depuis l'identité du microphone propriétaire ou une identité explicitement liée, alors que Jade pouvait décider d'une Core autobiographique depuis Discord. Un nom Discord ne suffit pas à démontrer la liaison propriétaire.
- `jade_self_core` déduplique par empreinte globale ; il faut distinguer le fait autobiographique unique des contextes authentifiés autorisés à le relire.

## Implémentation

1. Nouvel outil `jade_search_memory` dans les Responses LLM (écrit et vocal). Recherche lexicale avec quelques équivalences françaises, filtre par `kind`, `scope` et curseur, jusqu'à 15 entrées/page. Requête vide : parcourir toute la mémoire L2/L3 autorisée. Il n'y a pas de limite fixe de 8/512 souvenirs à cette recherche SQL ; plusieurs appels de modèle permettent de parcourir les pages, au plus six tours d'outil par réponse.
2. **Permissions de lecture vérifiées dans SQLite** à chaque appel : même compte et salon en contexte public, tous les scopes de la personne liée seulement en conversation privée ; Core autobiographique global visible en privé du propriétaire ; en public, Core self seulement si l'origine dispose d'un accès explicite pour ce compte et ce salon. Les profils changés ne sont pas réutilisés.
3. Jade choisit librement `core_self` depuis tout interlocuteur Discord authentifié et inscrit, sans autoriser cet interlocuteur à **imposer** une Core. L'inscription L2 obligatoire reste réservée à Goldaj authentifié. Les secrets restent filtrés. Les Core restent sans expiration.
4. Migration SQLite **v7** sans suppression de souvenirs : `jade_self_core.source_scope` et `jade_self_core_access` pour garantir la confidentialité intercanaux et autoriser le même fait autobiographique dans plusieurs contextes indépendants sans le dupliquer. Les anciens souvenirs sans scope connu sont classés `legacy_private`, lisibles en privé par le propriétaire, jamais automatiquement exposés publiquement.
5. Confirmation **optimiste inchangée** : `jade_save_memory` est mis en file sans attendre SQLite. Jade ne reçoit pas un statut réel du commit. Après une demande d'écriture acceptée, la recherche SQLite est interdite jusqu'au tour suivant (pas de vérification automatique).
6. La sauvegarde/importation portable accepte maintenant les schémas 1 à 7. Motifs de refus loggés en catégories sans contenu personnel.

## Tests livrés (hors appels payants)

- `tests/test_jade_memory_browsing.py` : pagination L2, recherche de souvenirs anciens, isolation de deux locuteurs, limitation publique, accès privé lié, ancienne DB v5, Core de plusieurs salons, doublons avec droits d'accès, refus de lecture après écriture acceptée.
- `tests/test_jade_discord_voice_core_self.py` : enregistrement volontaire en vocal, non-propriétaire, liaison/déliaison, curation par lot.
- `tests/test_luna_memory_tool_reasoning.py` : outil de recherche dans les Responses API simulées, plusieurs étapes de recherche, TTS progressif, confirmation optimiste sans vérification.
- `tests/test_jade_economy_memory.py` : Core de Jade venant d'un utilisateur tiers conservée comme autobiographie, pas mélangée à la mémoire relationnelle de cet utilisateur.

**Commande locale conseillée :**
```powershell
poetry run pytest -q tests/test_jade_memory_browsing.py tests/test_jade_discord_voice_core_self.py tests/test_luna_memory_tool_reasoning.py tests/test_jade_persistent_memory.py tests/test_jade_economy_memory.py
```

## Recette physique restant à effectuer

1. Sauvegarder la base `.sqlite3` privée avant la première ouverture en v7 ; faire `git pull origin develop` dans le répertoire PyCharm réellement lancé puis relancer Jade.
2. Depuis **le même Discord vocal et le même compte** : demander un souvenir L2 ancien, y compris un souvenir au-delà des premières pages ; vérifier la recherche dans les logs techniques et la restitution à l'auteur.
3. Faire choisir une Core autobiographique, puis **au tour suivant** lui demander de la retrouver ; contrôler `jade_self_core` (fait) et `jade_self_core_access` (accès contextualisés). Une Core relationnelle est en revanche dans `memories`.
4. Avec un second utilisateur puis un autre salon, vérifier qu'aucun souvenir privé de la première identité ou du premier salon n'est prononcé.
5. Simuler un échec SQLite : Jade conserve sa réponse optimiste, l'échec reste uniquement en diagnostic. Vérifier aussi les autres canaux, la latence vocale et le démarrage Windows.

Ne pas valider ces recettes tant qu'elles n'ont pas réellement été exécutées. Ne pas promouvoir automatiquement vers `main`.
