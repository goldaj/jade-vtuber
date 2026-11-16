# Accès au chat Jade depuis le téléphone, sans exposition publique

**État : guide de mise en place, pas de tunnel activé automatiquement.**
Cette procédure se fait sur le **PC qui exécute Jade**, connecté à un
compte Tailscale privé, et sur le téléphone connecté au même tailnet.

## 1. Vérifier Jade localement (sans API facturée)

```powershell
python main.py --preflight --live --http
```

Les erreurs indiquent quels paramètres sont absents, sans imprimer les secrets.
Configurer `OPENAI_API_KEY`, `JADE_HTTP_ENABLED=1` et un
`JADE_HTTP_TOKEN` aléatoire de 32 caractères minimum dans la configuration
privée. Puis **seulement lorsque souhaité**, démarrer les appels payants :

```powershell
python main.py --live --http
```

Sur ce même PC, vérifier `http://127.0.0.1:8765/`. La page demande le
jeton, sans le conserver sur disque. Les nouvelles conversations se
séparent par identifiant côté runtime, mais **ne sont pas persistantes**.

## 2. Tunnel chiffré réservé à vos appareils

Installer Tailscale sur les deux appareils ; vérifier les autorisations du
tailnet, les ACL et HTTPS (Serve peut demander d'activer les certificats).
Dans un terminal **sur le PC Jade**, après avoir vérifié qu'aucun autre
service Serve n'utilise le port 443 ou cette règle :

```powershell
tailscale serve status
tailscale serve --bg 8765
tailscale serve status
```

La commande doit afficher une URL HTTPS en `*.ts.net` accessible au
téléphone **uniquement dans le tailnet**. Ne pas publier cette adresse avec
des droits ouverts aux autres membres du tailnet ; limiter l'accès dans les
ACL si nécessaire. Saisir manuellement le jeton Jade dans le navigateur
du téléphone, sur cette page HTTPS.

**À ne jamais utiliser :** `tailscale funnel`, redirection de port du
routeur, `0.0.0.0` dans Jade, publication du token dans une URL, dépôt,
capture d'écran ou stockage du navigateur. L'API doit rester liée à
`127.0.0.1` et n'être atteignable depuis le téléphone qu'à travers Serve.
Les appels `POST /message` sont facturables via le LLM OpenAI.

## 3. Arrêt

```powershell
tailscale serve off
tailscale serve status
```

Vérifier que l'URL du téléphone n'atteint plus Jade. Le serveur local
peut être arrêté par Ctrl+C. Ne pas désactiver toute autre configuration
Serve existante sans l'identifier préalablement.

## Validation de recette non effectuée ici

- PC connecté à Tailscale + certificats HTTPS.
- Téléphone connecté, ACL vérifiées, pas d'accès anonyme/public.
- Réponses reçues en sessions séparées depuis PC et téléphone.
- Absence de fuite du jeton dans console, stockage navigateur et URLs.
- Arrêt Serve vérifié et quota/facturation OpenAI contrôlés.

Source technique : [documentation Tailscale Serve](https://tailscale.com/docs/features/tailscale-serve)
et [commande Serve](https://tailscale.com/docs/reference/tailscale-cli/serve).
