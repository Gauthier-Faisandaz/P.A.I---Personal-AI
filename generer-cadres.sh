#!/usr/bin/env bash
# generer-cadres.sh - produit les SVG des cadres du panneau d'angle (HUD)
# depuis cadre.py, verifie qu'ils sont utilisables par GTK, puis verifie que
# la geometrie recopiee dans eww.yuck est a jour et que chaque fenetre est
# symetrique haut/bas.
#
# Pourquoi un script plutot que lancer cadre.py a la main : cadre.py est la
# SOURCE UNIQUE de la geometrie du HUD. Chaque fois qu'on l'ajuste, il faut
# regenerer TOUS les cadres et refaire les memes controles. A la main, on en
# oublie un au premier ajustement, et les cadres divergent.
#
# Pourquoi les SVG sont versionnes (et pas generes au demarrage) : ils sont
# statiques. Les generer a chaque boot ajouterait dans start.sh une etape qui
# peut echouer, pour un resultat toujours identique.
#
# Trois controles :
#  1. ASCII pur, pour chaque SVG. cadre.py le demande ("rester en ASCII dans
#     les chaines produites") : meme famille de piege que le @charset du
#     SCSS, un seul caractere accentue peut faire refuser le fichier en silence.
#  2. Lecture par GdkPixbuf (python3-gi), pour chaque SVG, c'est-a-dire le
#     MEME chargeur SVG que GTK utilise pour le fond des pieces eww. Un SVG
#     mal forme ne fait pas d'erreur dans eww : le cadre est juste absent.
#     Ici, on le voit. On compare aussi la taille lue a celle de la fenetre.
#  3. "python3 cadre.py verifier" : les tailles et positions recopiees dans
#     eww.yuck (section PANNEAU D'ANGLE) sont-elles celles de cadre.py, et
#     chaque fenetre est-elle symetrique haut/bas (bogue de picom 10.2, voir
#     cadre.py) ?
#
# Usage : bash generer-cadres.sh   (depuis n'importe quel dossier)
# Code de sortie : 0 si tout passe, 1 sinon.

set -euo pipefail
cd "$(dirname "$0")"
mkdir -p hud

# Liste des pieces : lue dans cadre.py (source unique).
PIECES="$(python3 -B -c 'import cadre; print(*cadre.PIECES)')"

for piece in $PIECES; do
  python3 -B cadre.py "$piece" > "hud/$piece.svg"
done

erreurs=0
for piece in $PIECES; do
  f="hud/$piece.svg"

  # 1. ASCII : on cherche tout octet hors de la plage 0-127.
  if LC_ALL=C grep -qP '[^\x00-\x7F]' "$f"; then
    echo "ECHEC ASCII   $f :"
    LC_ALL=C grep -nP '[^\x00-\x7F]' "$f" | head -3
    erreurs=1
    continue
  fi

  # 2. Lecture GTK + taille attendue (celle de la fenetre, dans cadre.py).
  # -B : ne pas ecrire de __pycache__/ dans le depot a cause de "import cadre".
  if resultat=$(python3 -B - "$f" "$piece" <<'EOF'
import sys
import gi
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import GdkPixbuf
import cadre

fichier, piece = sys.argv[1], sys.argv[2]
attendu = cadre.PIECES[piece]['fenetre'][2:]
p = GdkPixbuf.Pixbuf.new_from_file(fichier)
lu = (p.get_width(), p.get_height())
print(f'{lu[0]}x{lu[1]}')
sys.exit(0 if lu == attendu else f'taille lue {lu}, attendue {attendu}')
EOF
  ); then
    echo "ok            $f  ($resultat, ASCII, lu par GdkPixbuf)"
  else
    echo "ECHEC GTK     $f"
    erreurs=1
  fi
done

# 3. Geometrie recopiee dans eww.yuck + symetrie des fenetres.
echo "--- eww.yuck (python3 cadre.py verifier)"
python3 -B cadre.py verifier || erreurs=1

exit $erreurs
