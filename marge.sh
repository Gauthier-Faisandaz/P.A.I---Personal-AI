#!/usr/bin/env bash
# marge.sh - regle a chaud l'ecart entre la colonne et le bord droit de
# l'ecran (pour laisser passer le panneau LXQt).
#   bash ~/.config/eww/marge.sh        -> affiche la valeur actuelle
#   bash ~/.config/eww/marge.sh 60     -> passe a 60px et deplace la colonne
#
# La valeur est ecrite dans geometrie.conf : elle est gardee au prochain
# demarrage. Essayer, regarder, recommencer jusqu'a ce que ca tombe juste.
#
# Pourquoi pas "eww update marge_droite=60" (comme prevu dans le brief) :
# eww 0.6.0 refuse une variable dans la geometrie d'une fenetre, qui est
# figee a l'ouverture (teste le 11/09). On rouvre donc la fenetre -- une
# fraction de seconde, sans redemarrer le demon : voir ouvrir-colonne.sh.
CFG="$HOME/.config/eww"
CONF="$CFG/geometrie.conf"

if [ -z "$1" ]; then
  grep '^MARGE_DROITE=' "$CONF"
  exit 0
fi
if ! [[ "$1" =~ ^[0-9]+$ ]]; then
  echo "usage : marge.sh <px>   (nombre entier, ex. 48)" >&2
  exit 1
fi

sed -i "s/^MARGE_DROITE=.*/MARGE_DROITE=$1/" "$CONF"
bash "$CFG/ouvrir-colonne.sh"
echo "marge droite : $1 px"
