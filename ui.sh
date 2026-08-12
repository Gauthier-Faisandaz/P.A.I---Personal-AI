#!/usr/bin/env bash
# Pilote l'affichage des fenetres MAIL et AGENDA (survol + clic).
#
# ARCHITECTURE :
# - survol (hover/unhover/ev_hover/ev_unhover) : on ecrit une ligne dans le
#   pipe de hoverd.sh, qui applique les evenements strictement dans l'ordre
#   d'arrivee et decide LUI-MEME quand ouvrir/fermer reellement preview/
#   ev_preview (rarement : une fois par "session" de survol, pas a chaque
#   item -- voir hoverd.sh et le commentaire en haut de eww.yuck).
# - clic (open/close/ev_open/ev_close) : detail/ev_detail sont de vrais
#   "eww open"/"eww close" a la demande, ici directement (pas besoin de
#   passer par le demon : un clic est une action ponctuelle, jamais de
#   rafale possible comme sur un survol).
CACHE="$HOME/.cache/eww"
FIFO="$CACHE/hover.fifo"
EWW="$HOME/.cargo/bin/eww"
TARGET="$(cat "$CACHE/target_screen" 2>/dev/null)"
mkdir -p "$CACHE"

LOG="$CACHE/ui.log"

case "$1" in
  hover|unhover|ev_hover|ev_unhover)
    [ -p "$FIFO" ] || { rm -f "$FIFO"; mkfifo "$FIFO"; }
    if exec 4<>"$FIFO" 2>/tmp/uiexec.$; then
      if printf '%s %s\n' "$1" "$2" >&4 2>/tmp/uiwrite.$; then
        printf '%s envoye %s %s\n' "$(date '+%H:%M:%S.%3N')" "$1" "$2" >> "$LOG"
      else
        printf '%s ECHEC ECRITURE %s %s : %s\n' "$(date '+%H:%M:%S.%3N')" "$1" "$2" "$(cat /tmp/uiwrite.$ 2>/dev/null)" >> "$LOG"
      fi
      exec 4>&- 2>/dev/null
    else
      printf '%s ECHEC OUVERTURE PIPE %s %s : %s\n' "$(date '+%H:%M:%S.%3N')" "$1" "$2" "$(cat /tmp/uiexec.$ 2>/dev/null)" >> "$LOG"
    fi
    rm -f /tmp/uiexec.$ /tmp/uiwrite.$
    ;;
  open)
    "$EWW" update ev_opened_id=""
    "$EWW" close ev_detail 2>/dev/null
    "$EWW" update opened_id="$2"
    "$EWW" open detail --screen "$TARGET" ;;
  close)
    "$EWW" close detail 2>/dev/null
    "$EWW" update opened_id="" ;;
  ev_open)
    "$EWW" update opened_id=""
    "$EWW" close detail 2>/dev/null
    "$EWW" update ev_opened_id="$2"
    "$EWW" open ev_detail --screen "$TARGET" ;;
  ev_close)
    "$EWW" close ev_detail 2>/dev/null
    "$EWW" update ev_opened_id="" ;;
esac
