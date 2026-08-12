#!/usr/bin/env bash
# Pilote l'affichage des boites MAIL et AGENDA (survol/clic).
#
# ARCHITECTURE (voir eww.yuck, commentaire au-dessus de preview_box) :
# preview/detail/ev_preview/ev_detail sont ouvertes UNE SEULE FOIS par
# start.sh et ne sont plus jamais fermees/reouvertes. Leur affichage est
# entierement pilote par des `revealer` reactifs aux variables ci-dessous --
# ce script ne fait donc plus QUE des "eww update", plus aucun open/close.
#
# Survol (hover/unhover/ev_hover/ev_unhover) : on ecrit une ligne dans le
# pipe de hoverd.sh (voir ce fichier pour le pourquoi) plutot que d'appeler
# "eww update" directement ici -- ca garantit qu'un survol rapide sur
# plusieurs items applique les mises a jour dans le bon ordre, sans course
# entre process concurrents.
#
# Clic (open/close/ev_open/ev_close) : actions ponctuelles, appliquees ici
# directement (pas de risque de rafale sur un clic).
#
# Exclusion mutuelle : une seule modale de detail a la fois. Ouvrir le detail
# d'un evenement referme celui d'un mail (et inversement), highlight compris
# -- il suffit desormais de remettre l'autre variable a "", le revealer
# correspondant se referme tout seul.
CACHE="$HOME/.cache/eww"
FIFO="$CACHE/hover.fifo"
EWW="$HOME/.cargo/bin/eww"
mkdir -p "$CACHE"

LOG="$CACHE/ui.log"

case "$1" in
  # ----- MAIL / AGENDA : survol -> transmis a hoverd.sh ----------------------
  hover|unhover|ev_hover|ev_unhover)
    [ -p "$FIFO" ] || { rm -f "$FIFO"; mkfifo "$FIFO"; }
    # Lecture+ecriture : n'attend jamais un lecteur (contrairement a une
    # ouverture en ecriture seule sur un pipe), donc jamais de blocage meme
    # si hoverd.sh n'a pas encore demarre.
    if exec 4<>"$FIFO" 2>/tmp/uiexec.$$; then
      if printf '%s %s\n' "$1" "$2" >&4 2>/tmp/uiwrite.$$; then
        printf '%s envoye %s %s\n' "$(date '+%H:%M:%S.%3N')" "$1" "$2" >> "$LOG"
      else
        printf '%s ECHEC ECRITURE %s %s : %s\n' "$(date '+%H:%M:%S.%3N')" "$1" "$2" "$(cat /tmp/uiwrite.$$ 2>/dev/null)" >> "$LOG"
      fi
      exec 4>&- 2>/dev/null
    else
      printf '%s ECHEC OUVERTURE PIPE %s %s : %s\n' "$(date '+%H:%M:%S.%3N')" "$1" "$2" "$(cat /tmp/uiexec.$$ 2>/dev/null)" >> "$LOG"
    fi
    rm -f /tmp/uiexec.$$ /tmp/uiwrite.$$
    ;;

  # ----- MAIL : clic -------------------------------------------------------
  open)
    "$EWW" update ev_opened_id=""
    "$EWW" update hovered_id=""
    "$EWW" update opened_id="$2" ;;
  close)
    "$EWW" update opened_id="" ;;

  # ----- AGENDA : clic ------------------------------------------------------
  ev_open)
    "$EWW" update opened_id=""
    "$EWW" update ev_hovered_id=""
    "$EWW" update ev_opened_id="$2" ;;
  ev_close)
    "$EWW" update ev_opened_id="" ;;
esac
