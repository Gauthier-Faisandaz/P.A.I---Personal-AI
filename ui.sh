#!/usr/bin/env bash
# ui.sh - ouvre / ferme la modale d'un mail.
#   ui.sh open <mail_id>   clic sur une ligne de la boite de reception
#   ui.sh close            croix ✕ de la modale ; aussi lance par
#                          mise-en-page.py a chaque repli ou depli d'un
#                          panneau (la modale ne serait plus alignee)
#
# Repris de la version d'avant l'accordeon (commit 8c5b890, fenetre
# "detail"). Seule la GEOMETRIE change : la modale n'a plus une position
# fixe, elle s'aligne sur le haut du panneau mails.
#
# IMPORTANT (12/08, toujours valable) : la modale est ouverte/fermee avec de
# vrais "eww open"/"eww close", jamais laissee mappee avec un contenu
# masque -- une fenetre transparente mappee en continu laisse un fond
# fantome visible sous ce compositeur. Un clic est une action ponctuelle :
# l'ouverture/fermeture reelle y est fiable. (Si eww se bloquait quand
# meme sur un open/close -- bug amont #451 --, eww-watchdog.sh le relance.)
EWW="$HOME/.cargo/bin/eww"
CACHE="$HOME/.cache/eww"

H_MODALE=420      # hauteur propre de la modale, independante du panneau
ECART_MODALE=14   # entre la modale et le bord gauche de la colonne

case "$1" in
  open)
    "$EWW" update mail_modale="$2"
    # Deja ouverte (clic sur un autre mail) : on change seulement le mail
    # affiche ; la modale garde la position prise a son ouverture.
    "$EWW" active-windows | grep -q '^modale:' && exit 0

    # Geometrie de l'ecran et de la colonne, ecrite par ouvrir-colonne.sh
    TARGET="$(cat "$CACHE/target_screen" 2>/dev/null)"
    # shellcheck source=/dev/null
    . "$CACHE/geometrie.env" 2>/dev/null
    MARGE="${MARGE:-20}"

    # y = haut du panneau mails, lu UNE fois, ici, au moment du clic, puis
    # passe en argument de fenetre : eww ne le recalcule jamais tant que la
    # modale reste ouverte. Si un mail arrive et que les panneaux changent
    # de hauteur, la modale ne saute pas.
    Y="$("$EWW" get y_mail 2>/dev/null)"
    { [[ "$Y" =~ ^[0-9]+$ ]] && [ "$Y" -gt 0 ]; } || Y="$MARGE"
    # Recalage vers le haut si la modale depasserait le bas de la zone
    # utile (meme marge qu'en bas de la colonne), sans remonter au-dessus
    # de la marge du haut.
    if [[ "$ECRAN_H" =~ ^[0-9]+$ ]]; then
      BAS=$((ECRAN_H - MARGE))
      [ $((Y + H_MODALE)) -gt "$BAS" ] && Y=$((BAS - H_MODALE))
      [ "$Y" -lt "$MARGE" ] && Y="$MARGE"
    fi
    # x : juste a gauche de la colonne. NEGATIF : compte depuis le bord
    # droit (anchor right), comme pour la colonne.
    X=$(( ${MARGE_DROITE:-42} + ${COLONNE_L:-633} + ECART_MODALE ))

    "$EWW" open modale --screen "$TARGET" \
      --arg "x=-${X}px" --arg "y=${Y}px" --arg "hauteur=${H_MODALE}px" ;;
  close)
    "$EWW" close modale 2>/dev/null
    "$EWW" update mail_modale="" ;;
esac
