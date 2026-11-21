# Mission : souvenirs transversaux privés entre comptes liés — 21/11/2026

- **Rôle :** ChatGPT, PO senior, backend/SQLite, tests et documentation.
- **Décision propriétaire :** développer un MVP utile sans sur-ingénierie, pousser directement sur `develop` et laisser la recette Discord/Android réelle au propriétaire.
- **Base :** `develop` au commit `6b936fa61d26de45e3f81bc71a1386c928deaf7d`, sans toucher `main`.
- **Critères :** un souvenir condensé enregistré dans un canal lié apparaît dans une autre conversation **privée** ; la mémoire fonctionne dans les deux sens ; sans lien ou après déliaison/effacement, plus de rappel transversal. Aucune reprise d'historique brut entre salons et aucune injection de souvenirs d'autres canaux en public.
- **Solution :** `recall_linked` réutilise `person_id` SQLite v4 et vérifie au moins deux comptes liés, avec filtrage TTL ; `context_for` ne l'appelle que sur mobile, micro et MP Discord ; quatre souvenirs liés et quatre locaux au plus. Aucun nouvel appel IA, aucune migration, Core autonomes préservées.
- **Sources modifiées :** `memory_store.py`, `memory_service.py`, `mobile_web/index.html`, `tests/test_jade_cross_channel_memory.py`, état/guide/technique, journal et cette passation.
- **Preuves automatiques :** cas liés/non liés, Discord MP/public, Twitch, tiers non lié, déliaison, effacement, TTL, historiques et autobiographie. Suite GitHub Actions Linux/Windows à vérifier après push.
- **Limites :** il s'agit de souvenirs sélectionnés, pas d'une synchronisation brute de toutes les conversations. Les salons publics gardent le rappel local uniquement. L'utilisateur doit contrôler les comptes qu'il lie : un compte lié volontairement peut lire en privé les souvenirs de ce profil. Pas de validation physique réalisée ici.
- **Livraison et reprise :** redémarrage de Jade sur la dernière `develop`, recette par le propriétaire avec souvenir Discord→mobile, mobile→MP Discord, puis vérification qu'un salon public ne récupère pas les faits privés. Validation des cartes éventuelles selon la DoD et les preuves réelles.
