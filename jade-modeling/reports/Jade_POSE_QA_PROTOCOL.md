# Jade — QA d'une capture pose par pose 1280×720

Le contrôle prend une vidéo et un manifeste donnant le centre temporel de
chaque pose stable. Il échantillonne une courte médiane autour de chaque
timestamp, puis mesure à la fois la luminance et les contours.

```powershell
Copy-Item reports\Jade_POSE_QA_manifest.example.json reports\Jade_POSE_QA_manifest.json
# Renseigner tous les timestamps null dans la copie.
python tools\qa_jade_pose_manifest.py `
  reports\Jade_POSES_raw_1280x720.mp4 `
  reports\Jade_POSE_QA_manifest.json `
  --output reports\Jade_POSES_raw_1280x720.qa.json
```

Résultat exigé : code retour `0` et `overall_pass: true`.

Le contrôle refuse la preuve si :

- un seuil des yeux ne diffère pas visiblement du seuil voisin ;
- une oreille ne montre pas trois poses distinctes par rapport au neutre ;
- une mèche ne change pas entre ses poses positive et négative ;
- une mèche ciblée ne bouge pas davantage que les quatre autres mèches dans
  sa propre paire de poses ;
- la pose bouge trop pendant la fenêtre de mesure ;
- la vidéo réelle est sous 24 i/s.

Les régions normalisées sont définies dans le manifeste exemple et peuvent
être ajustées si le cadrage change. Conserver une fenêtre stable d'au moins
0,25 s autour de chaque timestamp et ne pas laisser le pointeur traverser Jade.
