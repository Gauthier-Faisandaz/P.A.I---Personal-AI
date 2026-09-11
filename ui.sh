#!/usr/bin/env bash
# Pilote l'accordeon de la colonne : quel panneau est deplie (clic sur un
# en-tete). Usage : ui.sh panneau reco|venir|mail
#
# Historique :
#  - 12/08 : le survol a ete retire (voir eww.yuck), ainsi que le demon
#    hoverd.sh et le pipe FIFO qui l'alimentait.
#  - 10/09, refonte en colonne : les popups de detail (fenetres detail et
#    ev_detail, actions open / close / ev_open / ev_close) ont disparu. Le
#    detail d'un mail s'affiche desormais DANS son panneau, pilote par la
#    variable mail_ouvert (voir eww.yuck) : un simple "eww update" depuis
#    le clic suffit, sans passer par ce script.
EWW="$HOME/.cargo/bin/eww"

case "$1" in
  panneau)
    # $2 = reco | venir | mail (voir "defvar ouvert" dans eww.yuck).
    # Panneau deja ouvert : sans effet (pas d'etat "tout replie").
    [ "$("$EWW" get ouvert)" = "$2" ] && exit 0
    # mail_ouvert remis a "" dans le MEME appel : en revenant plus tard sur
    # le panneau mails, on retrouve la liste, pas le dernier detail ouvert.
    "$EWW" update ouvert="$2" mail_ouvert="" ;;
esac
