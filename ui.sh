#!/usr/bin/env bash
# ui.sh - ouvre / ferme la modale (detail d'un mail ou d'un item de veille).
#   ui.sh open mail <mail_id>   clic sur une ligne de la boite de reception
#   ui.sh open veille <id>      clic sur une ligne de la veille
#   ui.sh close                 croix ✕ de la modale ; aussi lance par
#                               mise-en-page.py a chaque repli ou depli d'un
#                               panneau (la modale ne serait plus alignee)
#
# Une seule fenetre "modale", deux contenus : la variable mail_modale OU
# veille_modale porte l'id de l'item affiche, l'autre est vide. eww.yuck
# choisit le contenu d'apres elles (modale_box).
#
# Repris de la version d'avant l'accordeon (commit 8c5b890, fenetre
# "detail"). Seule la GEOMETRIE change : la modale n'a plus une position
# fixe, elle s'aligne sur le haut du panneau d'ou vient l'item.
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
    source="$2"
    id="$3"
    # La source donne les noms des variables : <source>_modale (l'item
    # affiche) et y_<source> (le haut de son panneau). Rien d'autre n'est
    # accepte : ces noms finissent dans des commandes eww.
    case "$source" in
      mail)   autre=veille ;;
      veille) autre=mail ;;
      *) echo "ui.sh : source inconnue '$source' (mail | veille)" >&2; exit 1 ;;
    esac

    if "$EWW" active-windows | grep -q '^modale:'; then
      # Deja ouverte sur la MEME source (clic sur un autre mail) : on change
      # seulement l'item affiche ; la modale garde la position prise a son
      # ouverture.
      if [ -z "$("$EWW" get "${autre}_modale" 2>/dev/null)" ]; then
        "$EWW" update "${source}_modale=$id"
        exit 0
      fi
      # Ouverte sur l'AUTRE source : elle est alignee sur l'autre panneau.
      # On la ferme pour la rouvrir en face du bon.
      "$EWW" close modale
    fi
    # Un seul item affiche a la fois : l'autre variable est videe, dans le
    # meme update (pas d'etat intermediaire avec deux contenus).
    "$EWW" update "${source}_modale=$id" "${autre}_modale="

    # Geometrie de l'ecran et de la colonne, ecrite par ouvrir-colonne.sh
    TARGET="$(cat "$CACHE/target_screen" 2>/dev/null)"
    # shellcheck source=/dev/null
    . "$CACHE/geometrie.env" 2>/dev/null
    MARGE="${MARGE:-20}"

    # y = haut du panneau d'ou vient l'item, lu UNE fois, ici, au moment
    # du clic, puis passe en argument de fenetre : eww ne le recalcule
    # jamais tant que la modale reste ouverte. Si un mail arrive et que les
    # panneaux changent de hauteur, la modale ne saute pas.
    Y="$("$EWW" get "y_${source}" 2>/dev/null)"
    { [[ "$Y" =~ ^[0-9]+$ ]] && [ "$Y" -gt 0 ]; } || Y="$MARGE"
    # Recalage vers le haut si la modale depasserait le bas de la zone
    # utile (meme marge qu'en bas de la colonne), sans remonter au-dessus
    # de la marge du haut. Toujours le cas pour la veille, en bas de la
    # colonne : la modale remonte alors juste ce qu'il faut.
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
    "$EWW" update mail_modale="" veille_modale="" ;;
esac
