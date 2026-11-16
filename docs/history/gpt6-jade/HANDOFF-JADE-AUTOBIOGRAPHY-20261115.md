# Jade : mémoire autobiographique autonome (15 novembre 2026)

## État courant sur develop

La table autobiographique `jade_self_core`, le rappel privé de Goldaj, les commandes et le schéma SQLite v3 sont **intégrés au code** de `develop`. La présente passation conserve les décisions et la provenance des PR #6/#8/#9/#11, et non un état « à merger ».

## Pourquoi un autre stockage ?
Les `core_self` initiaux étaient stockés dans les souvenirs d'une *personne*, dans la portée de son salon. Ce n'est pas une mémoire autobiographique propre à Jade. La nouvelle table `jade_self_core` possède une identité globale de Jade séparée du registre des personnes et du journal des conversations. Une Core n'a **aucune expiration automatique**. Une provenance et un identifiant permettent sa correction/suppression.

## Périmètre de confidentialité choisi pour V1
Le global ne signifie **pas visible par tout le monde**. Pour éviter de réutiliser des détails d'un DM, d'un vocal ou d'une autre personne dans un salon public :
- les souvenirs globaux sont **owner_only**, créés et rappelés seulement pour l'identité locale `('microphone','goldaj')`, qui est également utilisée par la passerelle mobile privée de la PR #6/#7 après intégration ;
- l'identité est assignée par les connecteurs de confiance, jamais par le pseudo « Goldaj » ;
- Discord et Twitch conservent leurs `core_self` dans les mémoires relationnelles propres au compte/salon, sans promotion globale automatique ;
- un souvenir global reste sur le PC de Jade dans le fichier SQLite privé ; jamais dans Git, dans le VPS de trading ni dans une requête publique Discord ;
- `!jade-memoire oublier` depuis le propriétaire supprime aussi les épisodes globaux dont il est la source ; l'autobiographie ne rétablit pas un souvenir effacé ;
- un profil non activé ne permet aucune création ni lecture de l'autobiographie ; l'option du curator reste désactivée par défaut.

Une future promotion *publique* des expériences purement propres à Jade demanderait une classification explicite et un examen des éléments privés ; **ce lot n'autorise aucune diffusion à tous les interlocuteurs**.

## Moteur et commandes
Le moteur de curation de la PR #6 sélectionne déjà `none`, `ordinary`, `core_self`, `core_relationship` via JSON strict après une réponse. Pour une entrée de Goldaj provenant du micro local ou du mobile privé, un `core_self` est désormais écrit dans la table autonome. `core_relationship` reste associé à la personne. Pas d'appel modèle supplémentaire au-delà de la curation existante. Les mémoires `core_self` historiques rattachées aux profils restent intactes.

Commandes **uniquement via l'identité locale Goldaj reconnue** :
- `!jade-memoire autobiographie` : six derniers souvenirs et leurs IDs, sans requête au modèle.
- `!jade-memoire supprimer-self <id-hex-32>` : effacement d'un souvenir.
- `!jade-memoire oublier` : suppression des mémoires du compte propriétaire, y compris souvenirs autobiographiques issus de ce compte.

## SQLite et sauvegardes
Le lot historique ajoutait la table en v2 ; le schéma actuel de develop est **v3**, avec migration additive `CREATE TABLE IF NOT EXISTS` au premier démarrage (sans suppression des souvenirs existants). Export/import accepte une archive v1 ou v2 avec empreinte SHA-256 et vérification de la cohérence du numéro de schéma ; un import v1 est migré lors de l'ouverture suivante par `MemoryStore`. Aucun écrasement de base existante. Les archives ne sont **pas chiffrées**, même si elles peuvent contenir des souvenirs privés.

Les flags d'activation ne changent pas :
```dotenv
JADE_MEMORY_ENABLED=1
JADE_MEMORY_DB_PATH=D:\\Jade\\data\\jade-memory.sqlite3
JADE_MEMORY_CURATOR_ENABLED=1
```
Ce chemin est un exemple et doit pointer vers un dossier privé de l'utilisateur sur D:. La curation via OpenAI est optionnelle et facturable : une requête en plus par tour éligible, comme pour la PR #6.

## Recette/risques
1. **Intégration déjà réalisée** dans develop. En cas de migration d'une ancienne base de poste, sauvegarder la SQLite avant changement de schéma et utiliser les procédures courantes.
2. Tests offline Windows/Linux : nouveau stockage, déduplication, lecture owner-only, refus Discord/Twitch, effacement ciblé, export/import v1 et v2.
3. Depuis le micro local, puis depuis l'application mobile une fois intégrée, évoquer une expérience significative. Vérifier le `core_self`, le rappel au redémarrage et l'absence de divulgation sur Discord.
4. Tester la suppression individuelle, l'oubli du profil Goldaj, les sauvegardes et le contrôle du coût des appels de curation.
5. Faire une revue qualitative du tri par IA : le filtre de secrets est **heuristique**, il ne garantit pas l'absence de données privées dans les résumés. Ne jamais présenter les Core comme des faits objectifs certains.

**Aucune recette en conditions réelles n'a été effectuée par ce chantier distant.**


## Contre-revue complémentaire : suppression multi-identités (15 novembre)

Défaut corrigé : si Goldaj avait lié son profil local à un compte Discord/Twitch, `forget` appelé depuis l'autre compte supprimait la fiche relationnelle mais laissait `jade_self_core` en base. Un nouveau `enable` du compte local pouvait alors faire réapparaître une Core supposée oubliée. L'effacement recherche maintenant **l'appartenance du propriétaire dans toutes les identités du même `person_id`**, avant de retirer ses Core globales. Un compte non lié ne peut pas supprimer la biographie du propriétaire. Deux tests couvrent l'effacement lié et l'effacement indépendant.

**Attention :** les anciennes sauvegardes chiffrées ou non chiffrées peuvent toujours contenir des données oubliées. Il faut gérer leur durée de conservation et éviter de restaurer une sauvegarde dépassée après suppression.
