#!/usr/bin/env bash
# generer-cadres.sh - produit les SVG des cadres du panneau d'angle (HUD)
# depuis cadre.py, puis verifie qu'ils sont utilisables par GTK.
#
# Pourquoi un script plutot que lancer cadre.py a la main : cadre.py est la
# SOURCE UNIQUE de la geometrie du HUD. Chaque fois qu'on l'ajuste, il faut
# regenerer les QUATRE fichiers et refaire les memes controles. A la main,
# on en oublie un au premier ajustement, et les cadres divergent.
#
# Pourquoi les SVG sont versionnes (et pas generes au demarrage) : ils sont
# statiques. Les generer a chaque boot ajouterait dans start.sh une etape qui
# peut echouer, pour un resultat toujours identique.
#
# Deux controles par fichier :
#  1. ASCII pur. cadre.py le demande ("rester en ASCII dans les chaines
#     produites") : meme famille de piege que le @charset du SCSS, un seul
#     caractere accentue peut faire refuser le fichier en silence.
#  2. Lecture par GdkPixbuf (python3-gi), c'est-a-dire le MEME chargeur SVG
#     que GTK utilisera pour le fond de la fenetre eww. Un SVG mal forme ne
#     fait pas d'erreur dans eww : le cadre est juste absent. Ici, on le voit.
#     On compare aussi la taille lue a celle declaree dans cadre.py.
#
# Usage : bash generer-cadres.sh   (depuis n'importe quel dossier)
# Code de sortie : 0 si les quatre fichiers passent, 1 sinon.

set -euo pipefail
cd "$(dirname "$0")"
mkdir -p hud

PIECES="heure sparklines meteo filigrane"

for piece in $PIECES; do
  python3 cadre.py "$piece" > "hud/$piece.svg"
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

  # 2. Lecture GTK + taille attendue (constantes *_W / *_H de cadre.py).
  # -B : ne pas ecrire de __pycache__/ dans le depot a cause de "import cadre".
  if resultat=$(python3 -B - "$f" "$piece" <<'EOF'
import sys
import gi
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import GdkPixbuf
import cadre

fichier, piece = sys.argv[1], sys.argv[2]
attendu = {'heure':      (cadre.HEURE_W, cadre.HEURE_H),
           'sparklines': (cadre.SPK_W,   cadre.SPK_H),
           'meteo':      (cadre.MET_W,   cadre.MET_H),
           'filigrane':  (cadre.FIL_W,   cadre.FIL_H)}[piece]
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

exit $erreurs
