# Ewigo → annonce

Extraction d'une fiche véhicule depuis un site de concession Ewigo
(app Inertia.js) vers des données structurées réutilisables pour republier
l'annonce (Leboncoin, Lacentrale, multidiffusion…).

## Utilisation

```bash
python3 extract_ewigo.py https://saint-maximin-ewigo.com/vehicule/189804 --out ./189804
```

Produit dans le dossier de sortie :

- `annonce.json` — toutes les données normalisées (marque, modèle, version,
  année, km, énergie, boîte, puissance, équipements, prix, VIN, URLs photos…) ;
- `annonce.md` — annonce formatée prête à copier/coller ;
- `photos/` — toutes les photos de la galerie en pleine résolution.

Options :

- `--no-photos` : n'écrit que les données, sans télécharger les images.

## Fonctionnement

La page véhicule est une application Inertia.js : les données sont
sérialisées en JSON dans l'attribut `data-page` de `#app`. Le script parse ce
JSON directement — pas besoin de navigateur headless ni de contournement
anti-bot côté source.

## Remarque

N'utilisez ces données/photos que pour des véhicules dont vous êtes le
vendeur ou pour lesquels vous avez un mandat de diffusion. Les photos et
textes d'une annonce appartiennent à leur auteur (la concession).
