# Passation ChatGPT · DEV-036 · 22 novembre 2026

## Demande propriétaire
Unifier dans DEV-036 : création/gestion locale des rappels, réception push Android quand la PWA est fermée normalement ou écran verrouillé, clic ouvrant le rappel. Le propriétaire accepte les critères de recette 1 à 6 ainsi que les limites liées au téléphone et au PC.

## Conception et fichiers
- Code serveur et actions Jade : src/jade_runtime/reminders.py, config.py, dialogue.py, responses_chat.py, web_search.py, orchestrator.py, main.py.
- Serveur mobile et interface : mobile_gateway.py, mobile_web/app.js, sw.js, index.html, styles.css.
- Exploitation : scripts/setup_web_push.py, .env.example, docs/handbook/INSTALLATION.md, docs/handbook/BRANCH_STATE.md et tests/test_jade_reminders.py.
- Stockage privé SQLite séparé, création et changements transactionnels ; scheduler toutes les cinq secondes, 12 tentatives maximum, reprise des opérations en vol après 120 s. Provider push accepté ≠ notification Android observée. Les abonnements expirés sont supprimés.
- Permission/auth : compte PWA du propriétaire avec Tailscale + Bearer, ou Discord lié au même propriétaire. Destination de création immuable, tenant de l'identité du transport ; pas de diffusion intercanaux non demandée.
- Déploiement externe : pas d'action Windows/Android/secret ou réseau réel effectuée. Pas de changement main.

## Contrôles et suite
Tests hors ligne ajoutés. Exécuter lint/compile/CI et les recettes physiques détaillées dans la carte DEV-036. Vérifier l'installation facultative pywebpush et la cohérence VAPID sur le PC réel. L'état de livraison physique reste **non vérifié** ; la carte DEV-036 reste En cours sans validation Done.

## Limites assumées
Google/Outlook et récurrence non implémentés. Aucune garantie OS en fermeture forcée, batterie agressive ou téléphone déconnecté. Remise Web Push chiffrée, notification générique, jeton de consultation temporaire en mémoire seulement. Un crash immédiatement après l'acceptation fournisseur peut produire un double envoi.
