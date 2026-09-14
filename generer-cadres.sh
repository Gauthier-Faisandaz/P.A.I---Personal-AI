#!/usr/bin/env bash
# generer-cadres.sh - produit les cadres SVG du panneau d'angle (HUD) et
# leurs masques de decoupe depuis cadre.py, verifie que les SVG sont
# utilisables par GTK, puis verifie que la geometrie recopiee dans eww.yuck
# est a jour, que chaque fenetre est symetrique haut/bas, que le coin de
# l'ecran est cache et que les masques sont bons.
#
# Pourquoi un script plutot que lancer cadre.py a la main : cadre.py est la
# SOURCE UNIQUE de la geometrie du HUD. Chaque fois qu'on l'ajuste, il faut
# regenerer TOUS les cadres ET leurs masques, et refaire les memes controles.
# A la main, on en oublie un au premier ajustement, et tout diverge.
#
# Pourquoi les SVG et les masques sont versionnes (et pas generes au
# demarrage) : ils sont statiques. Les generer a chaque boot ajouterait dans
# start.sh une etape qui peut echouer (et charger GTK), pour un resultat
# toujours identique.
#
# Masques (hud/<piece>.masque) : la forme X Shape de chaque fenetre, tiree du
# RENDU du cadre SVG (voir cadre.py, DECOUPE AU PIXEL PRES) : exactement les
# pixels ou le cadre dessine quelque chose. decoupe-hud.py les lit.
# Apres un changement, rouvrir le HUD (bash ouvrir-hud.sh) : une fenetre qui
# a deja une forme n'est pas redecoupee.
#
# Controles :
#  1. ASCII pur, pour chaque SVG. cadre.py le demande ("rester en ASCII dans
#     les chaines produites") : meme famille de piege que le @charset du
#     SCSS, un seul caractere accentue peut faire refuser le fichier en silence.
#  2. Lecture par GdkPixbuf (python3-gi), pour chaque SVG, c'est-a-dire le
#     MEME chargeur SVG que GTK utilise pour le fond des pieces eww. Un SVG
#     mal forme ne fait pas d'erreur dans eww : le cadre est juste absent.
#     Ici, on le voit. On compare aussi la taille lue a celle de la fenetre.
#  3. "python3 cadre.py verifier" : geometrie recopiee dans eww.yuck,
#     symetrie haut/bas (bogue de picom 10.2, voir cadre.py), coin de
#     l'ecran cache par l'heure, masques presents, a la bonne taille et
#     symetriques.
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
  python3 -B cadre.py masque "$piece" > "hud/$piece.masque"
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

# 3. Geometrie recopiee dans eww.yuck, symetrie, coin, masques.
echo "--- eww.yuck et masques (python3 cadre.py verifier)"
python3 -B cadre.py verifier || erreurs=1

exit $erreurs
