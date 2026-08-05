# Padel Deal Finder

Agent personnel qui trouve les **meilleures offres de chaussures de padel**
dans ta taille, disponibles en France, classées par remise réelle.

Profil par défaut (modifiable dans `config.json`) : taille **44,5** (accepte
aussi `44 2/3`, la coupe Adidas équivalente), **toutes marques padel**
(Adidas, Asics, Bullpadel, Head, Wilson, Nox, Joma…), pas de plafond de prix,
frais de port ≤ 5 € ou offerts.

## À la demande

```bash
python3 finder.py --top 15                 # top 15 offres du moment
python3 finder.py --size 45 --min-discount 40
python3 finder.py --gender homme            # homme + unisexe (defaut config)
python3 finder.py --gender all              # inclut les modeles femme
```

Le filtre `gender` (défaut `homme` dans `config.json`) garde les modèles
homme **et** unisexe et écarte les versions femme.

Produit un classement console + `report.md` / `report.json`.

## Veille (ne montrer que les nouveautés)

```bash
python3 finder.py --new-only --min-discount 40
```

`--new-only` mémorise les offres déjà vues dans `state.json` et n'affiche
que les **nouvelles** apparues depuis le dernier passage — idéal pour une
exécution périodique qui n'alerte que sur du neuf.

## Comment ça marche

Les boutiques Shopify exposent `/products.json`, qui liste chaque produit et
chaque **taille** (variant) avec `price`, `compare_at_price` (prix barré) et
`available`. On filtre les chaussures disponibles dans ta taille, on calcule
la remise, on estime le port (config), on classe. Pas de navigateur, pas de
contournement anti-bot.

## Sources actuelles (toutes en EUR)

- Esprit Padel — `esprit-padel-shop.com`
- Padel Market — `padelmarket.com`
- Padel Point — `padel-point.fr`
- Padel Pro Shop — `padelproshop.com`

Ajouter une boutique = une entrée dans `config.json` (`"platform": "shopify"`
suffit si le site tourne sous Shopify). L'adaptateur détecte automatiquement
l'option « taille » (Taille / Size / Pointure / Shoe size), même quand la
boutique met la couleur en première option.

### Sites volontairement non inclus

- **Decathlon, i-Run, Alltricks, Zalando, Tennispro** : protégés par
  anti-bot (403) → nécessiteraient un navigateur furtif (Playwright), fragile.
- **Ventes privées (Veepee, Private Sport Shop)** : catalogue derrière
  compte/login → pas d'accès programmatique fiable ni conforme aux CGU.
- **The Padel Shop (UK)** : prix en GBP → exclu pour ne pas mélanger les devises.

Un adaptateur Playwright pour un gros site (ex. Decathlon) est possible sur
demande, en acceptant lenteur et fragilité accrues.

## Limites à connaître

- Les **prix barrés** viennent du marchand : une remise affichée peut être
  survendue. Vérifie le prix de référence avant d'acheter.
- Les **seuils de frais de port** dans `config.json` sont indicatifs
  (`"note": "seuils a confirmer"`) — ajuste-les selon la politique réelle.
- Les tailles Adidas/Asics utilisent souvent `44 2/3` plutôt que `44,5` :
  c'est volontairement inclus, mais essaie/renseigne-toi sur la coupe.
