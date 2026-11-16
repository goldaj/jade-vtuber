# Validation réellement observée

Date : 2 novembre 2026. Machine Windows, Python 3.11, copie source `df544ed78976096c522912a56ef9086c554e52ac`. Cette passe ajoute des documents et scripts de constat, sans changer le runtime.

| Vérification | Résultat observé | Portée |
| --- | --- | --- |
| Installation editable sans extras dans un venv neuf sur D: | Réussie | Installation de la base, pas un verrou de release |
| `unittest discover -s tests -v` | **51 tests, 8,211 s, OK** | Contrats simulés existants ; HTTP de test sur loopback |
| `tools/jade_ci_preflight.py` | **109 fichiers Python/TOML vérifiés**, contrôle basique réussi | Syntaxe et motifs courants des fichiers suivis, pas l’historique |
| `main.py --preflight`, profil offline | Réussi | Diagnostic local sans compte ni périphérique |
| CLI démo, entrée `/exit` | Réussie | Import et arrêt hors ligne |
| Compilation `src` et `main.py` | Réussie | Syntaxe Python 3.11 |
| `pip check` | Aucune dépendance cassée signalée | Cohérence de l’installation de base |
| Reproductions cœur | **F01/F02/F03/F04 présents** | Micro, arrêt, annulation, accumulation de sessions |
| Reproductions connecteurs | **F05/F06/F07/F08 présents** | HTTP expiré, workers Discord, surcharge Twitch, slots vocaux |
| Références Git | Neuf branches, PR #1 incluse dans #2, six commits docs propres à develop | Ordre d’intégration aux SHA enregistrés |

Le venv est `D:\Codex\caches\venvs\jade-audit-20261102`. Caches pip/bytecodes et temporaires sont sous D:. L’installation a sélectionné notamment OpenAI **3.42.1**, python-decouple **3.8**, python-dotenv **1.2.4**, requests **2.34.2** dans les plages du manifeste. Les versions sont consignées dans `snapshot.json` ; cette liste ne verrouille ni hashes, ni plateformes, ni extras.

Le harnais cœur observe une capture pendant une sortie active, un arrêt attendant cette sortie, 600 entrées dans chacun des trois dictionnaires et zéro terminaison du faux lecteur après annulation. Les quatre scénarios connecteurs vérifient leurs conditions par assertions. **Une reproduction qui réussit indique un défaut présent, pas un correctif validé.**

## Rejouer sans configuration privée

Le fichier synthétique vide évite le coffre par défaut. Les variables projet héritées sont retirées seulement du processus PowerShell courant, sans changement persistant Windows. Choisir un nouveau chemin si le fichier synthétique existe et contient des octets.

```powershell
Set-Location 'D:\Codex\projects\jade-migration-20261102'
$jadeAuditPython = 'D:\Codex\caches\venvs\jade-audit-20261102\Scripts\python.exe'
$jadeAuditPrivate = 'D:\Codex\tmp\jade-migration-20261102\empty-audit.env'
New-Item -ItemType Directory -Force -Path (Split-Path $jadeAuditPrivate) | Out-Null
if (-not (Test-Path -LiteralPath $jadeAuditPrivate)) {
    New-Item -ItemType File -Path $jadeAuditPrivate | Out-Null
}
if ((Get-Item -LiteralPath $jadeAuditPrivate).Length -ne 0) {
    throw 'Le fichier synthétique doit être vide ; choisir un autre chemin.'
}
Get-ChildItem Env: | Where-Object {
    $_.Name -match '^(JADE_|OPENAI_|TWITCH_|DISCORD_|ELEVENLABS_)' -or $_.Name -eq 'BOT_NAME'
} | ForEach-Object { Remove-Item -LiteralPath ('Env:' + $_.Name) }
$env:JADE_SECRETS_FILE = $jadeAuditPrivate
$env:JADE_PROFILE = 'offline'
$env:TEMP = 'D:\Codex\tmp'
$env:TMP = 'D:\Codex\tmp'
$env:PYTHONPYCACHEPREFIX = 'D:\Codex\caches\pycache\jade-audit-20261102'
$env:PYTHONUTF8 = '1'
& $jadeAuditPython -m unittest discover -s tests -v
& $jadeAuditPython tools/jade_ci_preflight.py
& $jadeAuditPython main.py --preflight
'/exit' | & $jadeAuditPython main.py
& $jadeAuditPython -m compileall -q src main.py
& $jadeAuditPython -m pip check
& $jadeAuditPython -B docs/migration/2026-11-02/repros/runtime_repros.py (Get-Location).Path
& $jadeAuditPython -B docs/migration/2026-11-02/repros/connector_repros.py (Get-Location).Path
```

Les reproductions utilisent seulement des doubles en mémoire ; le script cœur remplace le chargement privé avant import. Après correction, écrire des tests du comportement attendu inverse ; ne pas conserver « défaut reproduit » comme objectif de validation finale.

## CI distante du SHA exact

| Run GitHub | Résultat | Job observé |
| --- | --- | --- |
| [40924327854 — rebuild](https://github.com/goldaj/jade-ai-vtuber/actions/runs/40924327854) | completed / failure | `123625672277`, runner 0, nom vide, zéro étape |
| [40924327803 — publication](https://github.com/goldaj/jade-ai-vtuber/actions/runs/40924327803) | completed / failure | `123625672687`, runner 0, nom vide, zéro étape |

Ces runs du 29 octobre ciblent `df544ed`. Leur lecture du 2 novembre n’apporte aucune preuve de test exécuté. Aucun workflow relancé ici. **Cause exacte inconnue** : absence de runner/étapes enregistrées confirmée, raison non confirmée. La réussite locale est une preuve distincte, pas une CI distante verte.

La CI ne couvre que Python 3.11 Ubuntu sans extras. Le workflow rebuild filtre les pushes sur l’ancienne branche rebuild ; vérifier les événements PR/manuels et les filtres de chemins pour que le SHA final incluant lock et workflows soit effectivement testé.

## Hors validation

Aucun appel OpenAI réel, fournisseur vocal tiers, login Twitch/Discord, micro/audio, FFmpeg/ffplay réel, tunnel ou stream. Les tests VTS existants utilisent des mocks, sans recette visuelle. Aucun rig, binaire LFS, droit d’asset, sauvegarde complète, rotation de secret ou scan exhaustif de l’historique validé.

Le Python global présente des implémentations Discord concurrentes ; il ne doit pas servir de preuve d’installation. Ses paquets et les autres services du poste ont été préservés.

## Vérification de la livraison documentaire

Après ajout des deux scripts au suivi Git : préflight réussi sur **111 fichiers Python/TOML**, liens relatifs du dossier et du journal tous résolus, JSON et scripts analysables, `git diff --check` sans erreur. Les huit reproductions ont été rejouées depuis leurs chemins livrés avec les mêmes constats. Le diff ne touche aucun fichier de runtime, de test, de dépendance, de workflow ou d’asset.
