#!/usr/bin/env bash
# Veille padel : met a jour le code, cherche les nouvelles offres en 44,5.
# Usage : ./veille.sh [min_discount] [top]
#   ./veille.sh            # remises >= 45%, top 8
#   ./veille.sh 40 12      # remises >= 40%, top 12
# A planifier via cron, ex. tous les jeudis a 08:00 :
#   0 8 * * 4 ~/startbootstrap/padel-deal-finder/veille.sh >> ~/padel-veille.log 2>&1
set -euo pipefail

MIN_DISCOUNT="${1:-45}"
TOP="${2:-8}"
BRANCH="claude/padel-shoe-finder"

# se placer a la racine du repo (dossier parent de ce script)
cd "$(dirname "$0")/.."

# recuperer la derniere version de l'outil (sans casser si hors-ligne)
git pull --quiet origin "$BRANCH" 2>/dev/null || echo "(git pull ignore : hors-ligne ou branche locale)"

echo "===== Veille padel $(date '+%Y-%m-%d %H:%M') ====="
python3 padel-deal-finder/finder.py --new-only --min-discount "$MIN_DISCOUNT" --top "$TOP"
