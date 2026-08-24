#!/usr/bin/env bash
# Pilote l'affichage des fenetres de detail MAIL et AGENDA (clic uniquement).
#
# NOTE (12/08) : le survol a ete retire (voir eww.yuck), ainsi que le demon
# hoverd.sh et le pipe FIFO qui l'alimentait.
#
# IMPORTANT : detail/ev_detail sont ouvertes/fermees ici avec de vrais
# "eww open"/"eww close" (pas juste un :visible sur une fenetre qui reste
# mappee en permanence) -- constate le 12/08 : une fenetre transparente
# mappee en continu, meme contenu masque, laisse un fond fantome visible
# sous ce compositeur. Un clic n'a pas le probleme qu'avait le survol avec
# cette approche (rafales rapides -> fenetre "active" cote eww mais jamais
# peinte cote GTK, voir CHANGELOG.md iteration 11) : c'est une action
# ponctuelle, l'ouverture/fermeture reelle est fiable ici.
EWW="$HOME/.cargo/bin/eww"
TARGET="$(cat "$HOME/.cache/eww/target_screen" 2>/dev/null)"

case "$1" in
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
