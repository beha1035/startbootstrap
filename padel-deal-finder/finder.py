#!/usr/bin/env python3
"""
Padel Deal Finder — trouve les meilleures offres de chaussures de padel
dans ta taille, en France, chez des boutiques Shopify, classees par remise.

Usage:
    python3 finder.py                      # utilise config.json
    python3 finder.py --size 44.5 --top 15
    python3 finder.py --json report.json --md report.md

Fonctionnement:
    Les boutiques Shopify exposent /products.json : pour chaque produit et
    chaque taille (variant), on obtient le prix, le prix barre
    (compare_at_price) et la disponibilite. On filtre les CHAUSSURES
    disponibles dans ta taille, on calcule la remise reelle, on estime les
    frais de port (config) et on classe.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.request

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
HERE = os.path.dirname(os.path.abspath(__file__))

SHOE_HINTS = ("chaussure", "shoe", "footwear", "zapatilla")
# exclut les packs/lots (raquette + chaussures) qui contiennent "zapatillas" dans le titre
NOT_SHOE_HINTS = ("pala ", "pack", "raquette", "bundle", "lot ", " + ")
# marques de chaussures padel/court connues (pour deviner la marque si vendor vide)
KNOWN_BRANDS = ("adidas", "asics", "bullpadel", "head", "wilson", "nox",
                "babolat", "nike", "puma", "joma", "mizuno", "kelme",
                "siux", "dunlop", "lacoste", "kuikma")


def http_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def http_json_retry(url, tries=3, base_delay=1.5):
    """http_json avec retries (certaines boutiques renvoient des 500 transitoires)."""
    last = None
    for attempt in range(tries):
        try:
            return http_json(url)
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < tries - 1:
                time.sleep(base_delay * (attempt + 1))
    raise last


def norm_size(s):
    """Normalise une taille pour comparaison : '44,5' '44 1/2' -> '44.5'."""
    if s is None:
        return ""
    s = str(s).strip().lower().replace(",", ".")
    s = s.replace("eu", "").replace("uk", "").strip()
    frac = {"1/2": ".5", "1/3": ".33", "2/3": ".67"}
    for k, v in frac.items():
        if k in s:
            s = re.sub(r"\s*" + re.escape(k), v, s)
    s = s.replace(" ", "")
    m = re.match(r"^(\d+(?:\.\d+)?)", s)
    return m.group(1) if m else s


def size_matches(variant_opt, accept_norm):
    return norm_size(variant_opt) in accept_norm


SIZE_OPT_NAMES = ("taille", "size", "pointure", "talla", "shoe size", "größe")


def size_option_index(p):
    """Retourne l'index (1-3) de l'option 'taille' d'un produit Shopify.

    1) par le nom de l'option (Taille / Size / Pointure / Shoe size...)
    2) repli : l'option dont les valeurs ressemblent le plus a des pointures EU.
    """
    opts = p.get("options") or []
    for o in opts:
        if any(n in (o.get("name", "") or "").lower() for n in SIZE_OPT_NAMES):
            return o.get("position", 1)
    best, best_score = 1, -1
    for o in opts:
        vals = o.get("values") or []
        score = sum(1 for v in vals if re.match(r"^\s*(3[6-9]|4[0-9])([.,]\d| \d/\d)?\s*$", str(v)))
        if score > best_score:
            best, best_score = o.get("position", 1), score
    return best


WOMEN_HINTS = ("femme", "women", "woman", "mujer", "dama", "wmn", "w's", "ladies")
MEN_HINTS = ("homme", " men", "hombre", "man ", "herren", "mens", "men's", "men2")


def product_gender(p):
    """Devine le genre d'une chaussure : 'femme', 'homme' ou 'unisexe'."""
    blob = (p.get("title", "") + " " + " ".join(p.get("tags", []) or [])).lower()
    is_w = any(h in blob for h in WOMEN_HINTS)
    is_m = any(h in blob for h in MEN_HINTS)
    if is_w and not is_m:
        return "femme"
    if is_m and not is_w:
        return "homme"
    return "unisexe"


def is_shoe(p):
    title = (p.get("title", "") or "").lower()
    ptype = (p.get("product_type", "") or "").lower()
    if any(h in title for h in NOT_SHOE_HINTS) and "zapatilla" not in ptype and "chaussure" not in ptype:
        return False
    blob = ptype + " " + title + " " + " ".join(p.get("tags", []) or []).lower()
    return any(h in blob for h in SHOE_HINTS)


def guess_brand(p):
    v = (p.get("vendor") or "").strip()
    if v and v.lower() not in ("", "esprit padel", "padel market"):
        return v
    blob = p.get("title", "").lower()
    for b in KNOWN_BRANDS:
        if b in blob:
            return b.capitalize()
    return v or "?"


def shipping_cost(source, price):
    sh = source.get("shipping") or {}
    if sh.get("free_from") is not None and price >= sh["free_from"]:
        return 0.0
    return float(sh.get("flat", 0) or 0)


def scan_shopify(source, prof, accept_norm):
    """Retourne la liste des offres (chaussures dispo dans la taille) d'une boutique."""
    base = source["base"].rstrip("/")
    offers, page, empty_streak = [], 1, 0
    while page <= 15:  # garde-fou
        try:
            data = http_json_retry(f"{base}/products.json?limit=250&page={page}")
        except Exception as e:  # noqa: BLE001
            # page defaillante apres retries : on la saute au lieu d'abandonner la boutique
            print(f"  ! {source['name']} page {page} ignoree ({e})", file=sys.stderr)
            page += 1
            empty_streak += 1
            if empty_streak >= 3:  # plusieurs pages KO d'affilee -> on arrete
                break
            continue
        prods = data.get("products", [])
        if not prods:
            break
        empty_streak = 0
        for p in prods:
            if not is_shoe(p):
                continue
            brand = guess_brand(p)
            if prof.get("brands"):
                if not any(b.lower() in brand.lower() for b in prof["brands"]):
                    continue
            gender = product_gender(p)
            want = (prof.get("gender") or "all").lower()
            if want == "homme" and gender == "femme":
                continue  # on garde homme + unisexe
            if want == "femme" and gender == "homme":
                continue
            sidx = size_option_index(p)
            for v in p.get("variants", []):
                opt = v.get(f"option{sidx}") or v.get("option1") or v.get("title")
                if not size_matches(opt, accept_norm):
                    continue
                if not v.get("available"):
                    continue
                try:
                    price = float(v.get("price"))
                except (TypeError, ValueError):
                    continue
                comp = v.get("compare_at_price")
                comp = float(comp) if comp else None
                disc = round((comp - price) / comp * 100) if comp and comp > price else 0
                if prof.get("max_price") and price > prof["max_price"]:
                    continue
                if disc < prof.get("min_discount_pct", 0):
                    continue
                ship = shipping_cost(source, price)
                if prof.get("max_shipping") is not None and ship > prof["max_shipping"]:
                    continue
                offers.append({
                    "brand": brand,
                    "gender": gender,
                    "title": p.get("title"),
                    "size": opt,
                    "price": price,
                    "original": comp,
                    "discount_pct": disc,
                    "shipping": ship,
                    "total": round(price + ship, 2),
                    "shop": source["name"],
                    "url": f"{base}/products/{p.get('handle')}",
                    "image": (p.get("images") or [{}])[0].get("src"),
                })
        page += 1
    return offers


def rank(offers):
    # meilleures affaires d'abord : plus forte remise, puis prix total le plus bas
    return sorted(offers, key=lambda o: (-o["discount_pct"], o["total"]))


def to_md(offers, prof):
    L = [f"# Meilleures offres chaussures padel — taille {prof['size_eu']}\n",
         f"_{len(offers)} paires disponibles dans ta taille, classees par remise._\n"]
    for i, o in enumerate(offers, 1):
        orig = f" ~~{o['original']:.0f}€~~" if o["original"] else ""
        disc = f" **-{o['discount_pct']}%**" if o["discount_pct"] else ""
        ship = "port offert" if o["shipping"] == 0 else f"port {o['shipping']:.2f}€"
        L.append(f"{i}. **{o['brand']} — {o['title']}** (T.{o['size']})  \n"
                 f"   **{o['price']:.2f}€**{orig}{disc} · {ship} · total ~{o['total']:.2f}€ · {o['shop']}  \n"
                 f"   {o['url']}")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Trouve les meilleures offres chaussures padel")
    ap.add_argument("--config", default=os.path.join(HERE, "config.json"))
    ap.add_argument("--size", help="surcharge la taille EU (ex: 44.5)")
    ap.add_argument("--max-price", type=float)
    ap.add_argument("--gender", choices=["homme", "femme", "all"],
                    help="filtre genre (par defaut : valeur du config)")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--min-discount", type=int, help="ne garder que les remises >= X%")
    ap.add_argument("--new-only", action="store_true",
                    help="pour la veille : ne montrer que les offres jamais vues (via --state)")
    ap.add_argument("--state", default=os.path.join(HERE, "state.json"),
                    help="fichier memoire des offres deja vues")
    ap.add_argument("--json", help="ecrit le rapport JSON")
    ap.add_argument("--md", help="ecrit le rapport Markdown")
    args = ap.parse_args()

    cfg = json.load(open(args.config, encoding="utf-8"))
    prof = cfg["profile"]
    if args.size:
        prof["size_eu"] = args.size
        prof["size_accept"] = [args.size]
    if args.max_price is not None:
        prof["max_price"] = args.max_price
    if args.min_discount is not None:
        prof["min_discount_pct"] = args.min_discount
    if args.gender:
        prof["gender"] = args.gender

    accept_norm = {norm_size(s) for s in prof.get("size_accept", [prof["size_eu"]])}
    accept_norm.add(norm_size(prof["size_eu"]))

    all_offers = []
    for src in cfg["sources"]:
        print(f"Scan {src['name']} ...", file=sys.stderr)
        if src.get("platform") == "shopify":
            found = scan_shopify(src, prof, accept_norm)
            print(f"  -> {len(found)} offres taille {prof['size_eu']}", file=sys.stderr)
            all_offers.extend(found)

    ranked = rank(all_offers)

    # veille : ne garder que les offres jamais vues (cle = boutique|titre|taille|prix)
    if args.new_only:
        def key(o):
            return f"{o['shop']}|{o['title']}|{o['size']}|{o['price']}"
        seen = set()
        if os.path.exists(args.state):
            try:
                seen = set(json.load(open(args.state, encoding="utf-8")))
            except Exception:  # noqa: BLE001
                seen = set()
        fresh = [o for o in ranked if key(o) not in seen]
        json.dump(sorted(seen | {key(o) for o in ranked}),
                  open(args.state, "w", encoding="utf-8"))
        print(f"Veille : {len(fresh)} nouvelle(s) offre(s) sur {len(ranked)} au total.",
              file=sys.stderr)
        ranked = fresh

    top = ranked[:args.top]

    if not top:
        print("Aucune nouvelle offre dans ta taille pour l'instant." if args.new_only
              else "Aucune offre trouvee dans ta taille pour l'instant.")
        return

    print(f"\n=== TOP {len(top)} — chaussures padel taille {prof['size_eu']} en France ===\n")
    for i, o in enumerate(top, 1):
        orig = f" (au lieu de {o['original']:.0f}€)" if o["original"] else ""
        disc = f"  -{o['discount_pct']}%" if o["discount_pct"] else ""
        ship = "port offert" if o["shipping"] == 0 else f"port {o['shipping']:.2f}€"
        print(f"{i:2}. {o['brand']:10} {o['title'][:52]:52} T.{o['size']:<5} "
              f"{o['price']:6.2f}€{disc:6}{orig:20} | {ship} | {o['shop']}")
        print(f"    {o['url']}")

    out_json = args.json or os.path.join(HERE, "report.json")
    out_md = args.md or os.path.join(HERE, "report.md")
    json.dump(ranked, open(out_json, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    open(out_md, "w", encoding="utf-8").write(to_md(ranked, prof))
    print(f"\nRapports ecrits : {out_json} , {out_md}")


if __name__ == "__main__":
    main()
