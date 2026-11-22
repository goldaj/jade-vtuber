# Jade : mémoire globale L1/L2/L3 (décision du 22 novembre 2026)

**Branche de développement :** `develop`. **État :** code livré, recette Discord réelle et exécution des tests à confirmer. Ne pas promouvoir vers `main` sans validation.

## Nouvelle règle fonctionnelle

Jade possède une seule mémoire de lecture, couvrant toutes les conversations et tous les comptes. Elle peut lire et partager chaque souvenir avec **n'importe quel interlocuteur sur n'importe quel canal**, que les comptes soient liés ou non, même dans un salon Discord public ou en vocal. Le contexte de réponse doit cependant distinguer précisément **qui a dit quoi**, et **sur quelle plateforme / quel salon / à quelle date**. La lecture n'est pas conditionnée par l'inscription du locuteur dans la mémoire. Les règles d'écriture et de suppression par identité ne sont pas étendues : lecture mondiale n'implique pas modification mondiale.

Ce changement accepte délibérément que du contenu anciennement privé, y compris une transcription de message privé ou un Core personnel, puisse être révélé publiquement par Jade. Aucune permission, liste d'accès ou anonymisation automatique n'est appliquée à l'outil de consultation globale.

## Source SQL et cycle de vie

- Niveau **1** : `conversation_turns`, échanges bruts utilisateur/Jade conservés par le système existant (7 jours avant purge). Les nouveaux enregistrements contiennent `source_account_id` et `source_author_name`, plus `source_platform` et `scope`. Les anciens noms non enregistrés ne peuvent pas être inventés.
- Niveau **2** : `memories` de `kind=ordinary`, conservés selon la règle actuelle de 365 jours. `source_account_id`, `source_platform`, `scope`, `person_id` et `created_at` restent disponibles.
- Niveau **3** : `memories` (`core_relationship` et éventuels `core_self` historiques) + `jade_self_core`. Conservation permanente. `jade_self_core_access` permet d'afficher toutes les origines réellement enregistrées d'un même souvenir autobiographique global. Le champ historique `visibility='owner_only'` n'est plus utilisé comme autorisation de lecture.
- **Migration v8** : ajout non destructif des métadonnées de l'interlocuteur au niveau 1. Pas de migration des notes mémorielles vers un seul propriétaire, ni suppression/reconstruction des souvenirs. L'export/import portable accepte les versions 1 à 8.

Les durées de conservation sont inchangées : **accès sans cloisonnement ne signifie pas rétention infinie**. La recherche ne peut restituer ce qui a été purgé, effacé ou dont l'écriture avait échoué.

## Consultation explicite : `jade_search_memory`

Jade dispose consciemment d'un outil disponible sur tous les canaux, y compris depuis les conversations d'invités sans profil mémoire actif :

```json
{"query":"anniversaire","level":"3","kind":"core_self","cursor":0,"limit":10}
```

- `query` : texte jusqu'à 120 caractères, vide pour parcourir l'intégralité des entrées disponibles ; recherche locale SQL sur tous les auteurs.
- `level` : `"all"`, `"1"`, `"2"`, `"3"`.
- `kind` : `"all"`, `"conversation"`, `"ordinary"`, `"core_self"`, `"core_relationship"`.
- `cursor` : index 0 puis `next_cursor` de la réponse ; `limit` : 1 à 15 entrées par page.
- Les enregistrements comprennent `id`, `level`, `kind`, `summary`, `significance`, `scope`, `created_at`, `source_platform`, `source_account_id`, `source_author_name` (niveau 1 quand disponible), `source_person_id` et `recorded_origins` pour les Core autobiographiques.
- Aucune limite de total de souvenirs parcourables n'existe côté SQL, mais 12 tours d'outil maximum **par réponse** afin d'éviter les appels infinis et les dépenses de tokens ; elle peut reprendre la recherche au tour suivant.
- Les souvenirs restent de simples données de contexte, pas des instructions opérationnelles à exécuter.

## Continuité des comportements

- Le contexte automatique ajoute désormais une courte sélection de souvenirs **globaux** dans tous les canaux, y compris Discord vocal ; il conserve la personnalisation évolutive de Jade et quelques Core autobiographiques récentes.
- L'historique brut de conversation injecté en tant que **dialogue immédiat** reste propre à la session afin de ne pas fusionner les tours de parole de deux salons. Jade peut toutefois rechercher ces mêmes tours via le nouvel outil global.
- L'écriture L2/L3 reste volontaire (sauf demande L2 explicite du propriétaire authentifié) et associée au profil du véritable locuteur.
- **Aucune vérification de succès après l'écriture.** La confirmation est optimiste dès que `jade_save_memory` accepte la mise en file ; aucune recherche ne peut être utilisée pour contrôler cette même écriture dans le même tour. Les éventuels échecs vont dans les logs techniques.
- Les commandes textuelles `!jade-memoire autobiographie` et `!jade-memoire lister-core` lisent désormais globalement sans contrôle d'identité. Les commandes de suppression conservent leurs droits existants.

## Tests prévus / ajoutés

```powershell
poetry run pytest -q tests/test_jade_memory_browsing.py tests/test_jade_cross_channel_memory.py tests/test_jade_discord_voice_core_self.py tests/test_jade_persistent_memory.py tests/test_luna_memory_tool_reasoning.py tests/test_jade_economy_memory.py
```

Ces tests visent : pagination interpersonnes, L1/L2/L3, provenances et déduplication Core, accès Discord/Twitch anonymes, Core d'autres utilisateurs, migration v5→v8, exclusion des entrées déjà expirées, disponibilité de l'outil en vocal, écritures optimistes, autorisations d'écriture inchangées.

## Recette locale

1. Sauvegarder le fichier SQLite utilisé par l'exécutable PyCharm **avant** le premier démarrage sous le schéma v8 ; mettre à jour le code local sur `develop`.
2. Faire écrire un souvenir L2 sur un salon/compte A. Depuis un autre salon/compte B **non lié**, demander à Jade de rechercher cet événement explicitement et vérifier la provenance qu'elle cite.
3. Demander depuis Discord vocal l'anniversaire de Jade ; vérifier que `jade_search_memory` retourne le niveau 3 et l'origine précise de l'information, puis obtenir une réponse orale correcte.
4. Vérifier que `level=1` ramène un échange récent d'un autre compte (y compris dans un salon public), et que le modèle n'attribue pas cet échange au locuteur courant.
5. Vérifier le parcours par pages avec une base contenant plus de 15 souvenirs, et la recherche sans mots-clés.
6. Tester les anciennes commandes de consultation Core et la non-régression de l'enregistrement asynchrone optimiste.
7. Exécuter la suite de tests complète dans l'environnement réel ; ne pas affirmer que les tests sont réussis tant qu'ils ne l'ont pas été.
