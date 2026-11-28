# Débit spontané de Friponne dans GPT-Live

Le 28 novembre 2026, le propriétaire demande que Friponne adopte spontanément le débit qu’elle atteint quand il lui dit d’aller « le plus vite possible ». Il demande d’inscrire ce débit dans le prompt d’origine de Jade et autorise la publication sur `develop`. Le lot part de `develop` à `9370d3d`, sur `codex/friponne-debit-rapide`. L’écoute du résultat reste suivie en [REC-052 · À valider](../../backlog/02-RECETTE.md#rec-052--voix-friponne-avec-lavatar-de-jade-ancienne-dev-041). [Échanges accessibles](../../history/conversations/2026-11-27-evolution-voix-jade.md#débit-spontané-de-friponne-le-28-novembre-2026)

## Consigne validée par le propriétaire

> Parle le plus vite possible dès le premier mot et jusqu’au dernier. C’est ton débit habituel à chaque réponse, même pour une salutation, un aparté ou une réponse longue. Tu vas en mode "rap god". Enchaîne les mots et les phrases avec très peu de pauses. Garde cette vitesse sur toutes tes expressions et intentions. Fais passer l’émotion par le timbre, le volume et la mélodie de la voix.

Le profil de session `friponne` associe désormais la description de la voix enregistrée à cette direction de débit. Les indications de pause obligatoire et d’articulation ont été retirées du profil. La consigne s’applique à toutes les intentions, y compris celles qui pourront s’ajouter au catalogue. La direction silencieuse des résultats d’outils rappelle aussi le débit rapide. Les sessions Live mobiles et Discord utilisent le profil commun. GPT-Live interprète la consigne et le débit n’est pas calibré en multiplicateur. [Configuration Live](../../../src/jade_runtime/live_config.py) · [Direction vocale](../../../src/jade_runtime/live_voice.py) · [Pont des réponses déléguées](../../../src/jade_runtime/live_bridge.py)

Le prompt d’origine définit aussi la parole rapide comme un trait permanent de Jade. Il invite à varier les inflexions selon le sens et l’intention de la réplique. [Personnalité de Jade](../../../prompt_chat.txt)

## Écoute à réaliser

Les 49 tests ciblés passent hors réseau. Un contrôle distinct confirme que la personnalité chargée et la consigne validée sont présentes dans les requêtes Live des deux canaux, et que les anciennes indications de ralentissement et d’articulation ne sont plus transmises à Friponne.

Dans une nouvelle session Live, demander une salutation, un résultat d’outil et une réponse plus longue sans donner de consigne de vitesse à voix haute. Comparer le débit obtenu sur mobile et Discord Live au débit que Friponne prend quand on lui demande explicitement d’aller le plus vite possible.
