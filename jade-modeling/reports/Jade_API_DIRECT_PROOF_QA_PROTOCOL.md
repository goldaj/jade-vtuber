# Jade — contrôle de la future capture API directe

La capture n'est recevable que si l'appel API confirme le lancement de
`Jade_explicit_proof.motion3.json` et fournit l'instant de déclenchement utilisé
par le contrôle. Les captures idle actuelles sont rejetées dans
`Jade_IDLE_CAPTURES_REJECTION.json`.

## Capture

1. Conserver le cadrage rapproché 1600×900 de Jade, échelle 2.
2. Figer le tracking et la physique pendant cette seule preuve.
3. Démarrer la vidéo à 30 i/s, déclencher la motion par API et noter le temps
   vidéo du succès API à l'image près.
4. Enregistrer au moins 24 secondes après cet instant.

## Contrôle automatique

Si l'API confirme le déclenchement à `2.367 s` :

```powershell
python tools\qa_jade_api_direct_capture.py `
  reports\Jade_API_DIRECT_raw.mp4 `
  --motion-start 2.367 `
  --roi-config reports\Jade_API_DIRECT_QA_ROIS_1600x900.json `
  --output reports\Jade_API_DIRECT_raw.qa.json
```

Le code retour doit être `0` et `overall_pass` doit être `true`. Le JSON exige
neuf réussites séparées : œil gauche, œil droit, oreille gauche, oreille droite,
centre arrière, gauche intérieure/extérieure et droite intérieure/extérieure.

Le rapport fournit aussi le trim exact :

```powershell
ffmpeg -ss 2.367 -i reports\Jade_API_DIRECT_raw.mp4 -t 24.000 -c:v libx264 -crf 16 -pix_fmt yuv420p reports\Jade_API_DIRECT_proof.mp4
```

Ne produire ni GIF ni vidéo finale si un seul signal échoue. Si le cadrage a
changé, ajuster uniquement le fichier ROI normalisé puis relancer le contrôle.
