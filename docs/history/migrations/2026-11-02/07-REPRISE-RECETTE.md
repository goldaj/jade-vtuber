# Reprise : recette réelle puis fusion

**Mise à jour du propriétaire :** la recette micro simulée est acceptée comme recette incomplète. Le test texte réel a été tenté et refusé (HTTP 429, solde épuisé). Il souhaite recharger le compte et prévenir avant un nouvel essai. Attendre ce message ; ensuite retester une réponse texte courte, vérifier les checks du SHA final, puis fusionner si le texte passe. Aucun nouvel essai micro physique n’est requis pour cette fusion. Les étapes initiales ci-dessous sont conservées comme historique et cèdent devant cette instruction plus récente.

**Reprise effectuée :** le propriétaire a confirmé la recharge ; une génération texte réelle courte via le runtime a réussi avec `gpt-4.1-mini` en 1,72 s. Deux tests de pipeline vocal synthétique ont réussi ; 81 tests hors ligne passent. Le propriétaire autorise la fusion après cette recette incomplète. Microphone physique, STT/TTS réels et lecture audio restent à valider avant leur activation effective.

État du 2 novembre 2026. PR #2 ouverte en brouillon, source `research/gpt6-jade-publication-readiness-20261028`, cible `develop`. Les corrections applicatives, le lock Poetry et les tests hors ligne sont intégrés à la branche de PR. Le commit `b890eff` a passé les CI GitHub Windows/Linux et hygiène ; vérifier les checks et SHA actuels avant toute fusion.

Le propriétaire a choisi **texte, voix et micro OpenAI à budget minimal**, puis demandé à tester le micro plus tard. **Ne pas lancer de capture ni de génération avant la reprise de cet essai avec lui.** Aucun stream public, aucune connexion Twitch/Discord ni opération sur les assets 2D n’ont été réalisés.

## Ce qui est déjà validé

- Windows local, Python 3.11, environnement Poetry 2.2.1 verrouillé avec extras : 79 tests hors ligne, compilation, démo et `pip check` OK.
- CI distante du candidat `b890eff` : jobs Windows et Linux, ainsi que l’hygiène, réussis ; le diagnostic runner fonctionne à nouveau.
- La configuration privée par défaut ne contenait pas de clé utilisable dans le processus. Une valeur OpenAI issue d’un ancien `.env` de l’historique privé a été authentifiée par lecture de métadonnées de modèle, sans génération, affichage ni copie de la valeur. Cette présence historique est un risque connu à traiter dans le chantier distinct de rotation/sécurisation ; ne pas publier l’historique.
- Un exécutable ffplay existant a été repéré sur le poste ; sounddevice détecte une entrée et une sortie. Ce sont des vérifications de présence, pas des essais de capture ou d’écoute.

## Recette prévue

1. Reprendre avec le propriétaire et obtenir sa disponibilité pour parler. Vérifier les SHA distants, l’état de la PR et la CI du SHA final ; relire le plan Astra.
2. Préparer un processus isolé avec une clé valide fournie via configuration privée ou en mémoire, sans l’afficher, l’écrire dans le dépôt ou la journaliser. Réutiliser ffplay existant en ajustant seulement le PATH du processus ; temporaires sur D:.
3. Faire une seule capture de trois secondes. Si elle est silencieuse, terminer sans appel facturé. Sinon : une transcription OpenAI, une réponse texte courte, une synthèse OpenAI et une lecture locale, sans répétition automatique. Le helper local `D:\Codex\tmp\jade-migration-20261102\recette_reelle_unique.py` prépare cette séquence, mais il est temporaire et ne doit être lancé que lors de la reprise. Il ne remplace pas un essai du runtime intégré.
4. Vérifier ensuite le fonctionnement intégré et l’arrêt avec un nombre d’appels borné ; relever erreurs, durées et nombre d’appels, sans transcription, secret ni promesse de coût exact. Consigner la preuve observée et laisser désactivés les connecteurs qui n’ont pas été recettés.
5. Si la recette ou la CI échoue, corriger en branche et revalider le nouveau SHA. En cas de succès, appliquer la procédure de fusion unique du plan Astra : revérifier `develop`, source, checks et ascendance ; intégrer la PR par merge commit, puis vérifier l’arbre et les parents. Aucun squash/force-push.
6. La première mise en service reste une étape distincte, privée et supervisée. Les modes non testés restent désactivés. Aucun ancien runtime ne doit être relancé automatiquement comme retour arrière.

La valeur historique n’est pas à copier dans ce document, la PR, les logs ou un script. Le coffre éventuellement rétabli doit conserver ses protections et ne pas être remplacé aveuglément.
