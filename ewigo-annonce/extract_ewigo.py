#!/usr/bin/env python3
"""
Extraction d'une annonce vehicule Ewigo -> donnees structurees + photos.

Le site Ewigo est une application Inertia.js : toutes les donnees du vehicule
sont serialisees en JSON dans l'attribut data-page de la balise #app.
On parse ce JSON (aucun rendu navigateur necessaire) puis on :
  1. ecrit annonce.json         (donnees brutes normalisees)
  2. ecrit annonce.md           (annonce formatee, prete a copier/coller)
  3. telecharge toutes les photos dans photos/

Usage:
    python3 extract_ewigo.py https://saint-maximin-ewigo.com/vehicule/189804
    python3 extract_ewigo.py <url> --out ./sortie --no-photos
"""
import argparse
import html
import json
import os
import re
import sys
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")


def fetch(url: str, binary: bool = False):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    return data if binary else data.decode("utf-8", "replace")


def parse_page(url: str) -> dict:
    """Recupere et decode le JSON Inertia (data-page) de la page vehicule."""
    doc = fetch(url)
    m = re.search(r'id="app"[^>]*\sdata-page="(.*?)"\s*>', doc, re.S)
    if not m:
        raise RuntimeError("data-page introuvable : la page a peut-etre change de structure.")
    return json.loads(html.unescape(m.group(1)))


def clean(v):
    if isinstance(v, str):
        v = re.sub(r"<[^>]+>", "", v).strip()
    return v


def normalize(ad: dict, title: str) -> dict:
    """Selectionne et met a plat les champs utiles pour une annonce."""
    eq = ad.get("equipments") or {}
    equipements = []
    if isinstance(eq, dict):
        for group in ("exterior", "interior", "security", "other", "autoscout"):
            equipements.extend(eq.get(group) or [])
    # dedoublonne en conservant l'ordre
    seen = set()
    equipements = [x for x in equipements if not (x in seen or seen.add(x))]

    return {
        "id": ad.get("id"),
        "titre": title or f"{ad.get('make','')} {ad.get('model','')} {ad.get('version','')}".strip(),
        "marque": ad.get("make"),
        "modele": ad.get("model"),
        "version": ad.get("version"),
        "categorie": ad.get("category"),
        "annee": ad.get("year"),
        "mise_en_circulation": (ad.get("market_release_date") or "")[:10],
        "kilometrage": ad.get("kms"),
        "energie": ad.get("energy"),
        "boite": ad.get("gear"),
        "rapports": ad.get("gear_count"),
        "puissance_din": ad.get("horse_power"),
        "puissance_fiscale": ad.get("horse_power_tax"),
        "co2": ad.get("co2"),
        "portes": ad.get("doors_count"),
        "places": ad.get("seats_count"),
        "mains": ad.get("hands_count"),
        "couleur_ext": ad.get("color_exterior"),
        "couleur_int": ad.get("color_interior"),
        "provenance": ad.get("origin"),
        "vin": ad.get("serial_number"),
        "immatriculation": ad.get("immatriculation"),
        "prix": ad.get("price"),
        "prix_format": ad.get("price_format"),
        "description": clean(ad.get("description")) or "",
        "equipements": equipements,
        "photos": ad.get("gallery") or [],
        "url_source": ad.get("full_url"),
    }


def to_markdown(a: dict) -> str:
    L = []
    L.append(f"# {a['titre']}\n")
    L.append(f"**Prix : {a.get('prix_format') or a.get('prix')} €**\n")
    L.append("## Caracteristiques\n")
    rows = [
        ("Marque", a["marque"]), ("Modele", a["modele"]), ("Version", a["version"]),
        ("Categorie", a["categorie"]), ("Annee", a["annee"]),
        ("Mise en circulation", a["mise_en_circulation"]),
        ("Kilometrage", f"{a['kilometrage']} km" if a["kilometrage"] else None),
        ("Energie", a["energie"]), ("Boite", f"{a['boite']} {a['rapports']} rapports".strip()),
        ("Puissance", f"{a['puissance_din']} ch ({a['puissance_fiscale']} CV)"),
        ("CO2", f"{a['co2']} g/km" if a["co2"] else None),
        ("Portes", a["portes"]), ("Places", a["places"]),
        ("Nombre de mains", a["mains"]), ("Couleur", a["couleur_ext"]),
        ("Provenance", a["provenance"]),
    ]
    for k, v in rows:
        if v not in (None, "", "None"):
            L.append(f"- **{k}** : {v}")
    if a["equipements"]:
        L.append("\n## Equipements\n")
        L.extend(f"- {e}" for e in a["equipements"])
    if a["description"]:
        L.append("\n## Description\n")
        L.append(a["description"])
    L.append(f"\n## Photos ({len(a['photos'])})\n")
    L.extend(f"{i}. {u}" for i, u in enumerate(a["photos"], 1))
    return "\n".join(L) + "\n"


def download_photos(urls, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    ok = 0
    for i, u in enumerate(urls, 1):
        ext = os.path.splitext(u.split("?")[0])[1] or ".jpg"
        path = os.path.join(out_dir, f"photo_{i:02d}{ext}")
        try:
            with open(path, "wb") as f:
                f.write(fetch(u, binary=True))
            ok += 1
            print(f"  [{i:02d}/{len(urls)}] {os.path.basename(path)}")
        except Exception as e:  # noqa: BLE001
            print(f"  [{i:02d}] ECHEC {u} : {e}", file=sys.stderr)
    return ok


def main():
    ap = argparse.ArgumentParser(description="Extraction annonce vehicule Ewigo")
    ap.add_argument("url")
    ap.add_argument("--out", default=".", help="dossier de sortie (defaut: courant)")
    ap.add_argument("--no-photos", action="store_true", help="ne pas telecharger les photos")
    args = ap.parse_args()

    page = parse_page(args.url)
    props = page.get("props", {})
    ad = props.get("ad") or {}
    if not ad:
        sys.exit("Aucune donnee 'ad' dans la page.")

    annonce = normalize(ad, props.get("title"))
    os.makedirs(args.out, exist_ok=True)

    with open(os.path.join(args.out, "annonce.json"), "w", encoding="utf-8") as f:
        json.dump(annonce, f, ensure_ascii=False, indent=2)
    with open(os.path.join(args.out, "annonce.md"), "w", encoding="utf-8") as f:
        f.write(to_markdown(annonce))

    print(f"Vehicule : {annonce['titre']}")
    print(f"Prix     : {annonce['prix_format']} €  |  {annonce['kilometrage']} km  |  {annonce['annee']}")
    print(f"Ecrit    : annonce.json, annonce.md  (dans {args.out})")
    print(f"Photos   : {len(annonce['photos'])}")

    if not args.no_photos and annonce["photos"]:
        print("Telechargement des photos ->", os.path.join(args.out, "photos"))
        n = download_photos(annonce["photos"], os.path.join(args.out, "photos"))
        print(f"{n}/{len(annonce['photos'])} photos telechargees.")


if __name__ == "__main__":
    main()
