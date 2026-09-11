#!/usr/bin/env bash
# ouvrir-colonne.sh - (re)ouvre la fenetre "colonne" sur l'ecran cible, avec
# sa geometrie calculee. Seul endroit ou ce calcul est fait ; appele par :
#   - start.sh         (demarrage, changement d'ecran)
#   - eww-watchdog.sh  (apres un redemarrage force du demon)
#   - marge.sh         (reglage a chaud de la marge droite)
#
# Pourquoi rouvrir plutot que deplacer : eww 0.6.0 fige la position d'une
# fenetre a son ouverture. Une variable dans :geometry est refusee
# ("Unknown variable", teste le 11/09) ; seuls les ARGUMENTS passes par
# "eww open --arg" sont acceptes. Rouvrir ne redemarre pas le demon : les
# donnees des panneaux et leurs hauteurs sont conservees.
EWW="$HOME/.cargo/bin/eww"
CFG="$HOME/.config/eww"
CACHE="$HOME/.cache/eww"
LOG="$HOME/.cache/eww-start.log"

# Reglages (valeurs de repli si le fichier manque)
MARGE=20
MARGE_DROITE=42
# shellcheck source=geometrie.conf
[ -r "$CFG/geometrie.conf" ] && . "$CFG/geometrie.conf"

# Ecran cible, choisi par start.sh
TARGET="$(cat "$CACHE/target_screen" 2>/dev/null)"
[ -z "$TARGET" ] && TARGET=0

# Hauteur de l'ecran cible, lue dans sa ligne xrandr ("... 1920x1080+1366+0
# ..." -> 1080), moins la marge en haut et en bas : voir le commentaire de
# "defwindow colonne" dans eww.yuck. Repli si l'ecran n'a pas pu etre lu
# (TARGET=0) : 93% de la hauteur, comme avant la refonte.
RES="$(xrandr --query | grep "^$TARGET connected" \
       | grep -oE '[0-9]+x[0-9]+\+[0-9]+\+[0-9]+' | head -n1 | cut -d+ -f1)"
W_ECRAN="${RES%x*}"      # "1920x1080" -> 1920
H_ECRAN="${RES#*x}"      # "1920x1080" -> 1080
if [[ "$H_ECRAN" =~ ^[0-9]+$ ]]; then
  HAUTEUR="$((H_ECRAN - 2 * MARGE))px"
else
  HAUTEUR="93%"
fi

# x NEGATIF : avec :anchor "top right", eww compte x depuis le bord droit
# vers la gauche quand il est negatif (convention deja en place : "-24px"
# donnait 24px d'ecart au bord droit, verifie avec xwininfo le 11/09).
ARGS=(--arg "marge=${MARGE}px" --arg "hauteur=$HAUTEUR" --arg "droite=-${MARGE_DROITE}px")

# Memorise la geometrie : mise-en-page.py y lit la marge et la hauteur.
printf '%s ' "${ARGS[@]}" > "$CACHE/colonne_args"
echo "$(date '+%F %T') - colonne sur $TARGET : marge ${MARGE}px, droite ${MARGE_DROITE}px, hauteur $HAUTEUR" >> "$LOG"

# Geometrie en px pour ui.sh, qui place la modale a gauche de la colonne.
# COLONNE_L = 33% de la largeur de l'ecran, arrondi vers le bas comme eww
# (1920 -> 633, 1366 -> 450, verifie avec xwininfo) ; 33 = :width de la
# colonne dans eww.yuck.
{
  echo "ECRAN_H=$H_ECRAN"
  echo "MARGE=$MARGE"
  echo "MARGE_DROITE=$MARGE_DROITE"
  [[ "$W_ECRAN" =~ ^[0-9]+$ ]] && echo "COLONNE_L=$((W_ECRAN * 33 / 100))"
} > "$CACHE/geometrie.env"

# La modale est placee par rapport a la colonne : si la colonne bouge
# (marge.sh, changement d'ecran), une modale ouverte serait mal placee.
"$EWW" close modale 2>/dev/null
"$EWW" update mail_modale="" 2>/dev/null

# Fermer d'abord (sans erreur si deja fermee) : le script est relancable.
"$EWW" close colonne 2>/dev/null
"$EWW" open colonne --screen "$TARGET" "${ARGS[@]}"

# Recalcul immediat des hauteurs avec la nouvelle geometrie (le bus est
# deja rempli : pas besoin d'attendre le prochain fetch). En arriere-plan,
# comme dans publier.sh.
nohup python3 "$CFG/mise-en-page.py" --pousser \
  < /dev/null > "$CACHE/mise-en-page.log" 2>&1 &
