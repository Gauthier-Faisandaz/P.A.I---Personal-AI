#!/usr/bin/env bash
# hoverd.sh - demon persistant qui applique les evenements de survol
# (mail + agenda) dans l'ordre EXACT ou ils arrivent.
#
# Pourquoi ce demon :
# Chaque entree/sortie de survol declenche un appel independant depuis
# ui.sh. Si chacun de ces appels faisait directement "eww update" dans son
# propre process, rien ne garantirait qu'ils s'executent dans l'ordre ou GTK
# a reellement declenche les evenements (demarrage d'un interprete a cout
# variable) -- lors d'un survol rapide, un evenement plus ANCIEN pourrait
# s'appliquer APRES un evenement plus RECENT et laisser l'etat affiche en
# retard sur la souris.
#
# Ici, ui.sh ne fait plus qu'ecrire une ligne dans un pipe (ecriture quasi
# instantanee). Ce demon, lance UNE SEULE fois par start.sh, lit et applique
# ces lignes strictement dans leur ordre d'arrivee : par construction, le
# dernier evenement ecrit est toujours le dernier applique, sans exception
# possible (un seul lecteur, un seul thread, aucune course).
#
# ARCHITECTURE (voir eww.yuck, commentaire au-dessus de preview_box) :
# preview/detail/ev_preview/ev_detail sont ouvertes UNE SEULE FOIS par
# start.sh et ne sont plus jamais fermees/reouvertes -- leur affichage est
# pilote par un `revealer` reactif aux variables hovered_id/ev_hovered_id.
# Ce demon ne fait donc plus que des "eww update" (plus de "open"/"close"
# ici), ce qui elimine le remapping X11 repete qui s'averait peu fiable
# cote GTK (fenetre listee comme active par eww mais jamais peinte).
EWW="$HOME/.cargo/bin/eww"
CACHE="$HOME/.cache/eww"
FIFO="$CACHE/hover.fifo"
LOCK="$CACHE/hoverd.lock"
LOG="$CACHE/hoverd.log"
mkdir -p "$CACHE"
: > "$LOG"   # on repart d'un journal vide a chaque (re)demarrage du demon

log() { printf '%s %s\n' "$(date '+%H:%M:%S.%3N')" "$*" >> "$LOG"; }

# Une seule instance a la fois : si un demon tourne deja, celui-ci se ferme
# aussitot. Permet de relancer start.sh sans jamais dupliquer le demon.
exec 9>"$LOCK"
flock -n 9 || exit 0

[ -p "$FIFO" ] || { rm -f "$FIFO"; mkfifo "$FIFO"; }

detail_ouvert() {
  [ -n "$("$EWW" get opened_id 2>/dev/null)" ] && return 0
  [ -n "$("$EWW" get ev_opened_id 2>/dev/null)" ] && return 0
  return 1
}

# Ouverture en lecture+ecriture : le demon garde ainsi en permanence une
# reference en ecriture sur son propre pipe, donc `read` ne recoit jamais
# de EOF entre deux ecrivains externes (sinon la boucle se terminerait des
# qu'aucun ui.sh n'est "en ligne" au meme instant).
exec 3<>"$FIFO"

# Emballe chaque appel eww pour journaliser sa duree, son code de sortie et
# sa sortie d'erreur -- seul moyen de voir concretement ou ca coince cote
# demon plutot que de continuer a deviner.
ew() {
  local t0 t1 out rc
  t0=$(date +%s%3N)
  out="$("$EWW" "$@" 2>&1)"; rc=$?
  t1=$(date +%s%3N)
  log "  eww $* -> rc=$rc (${t1}-${t0}=$((t1 - t0))ms)${out:+ | $out}"
}

apply() {
  local action="$1" id="$2"
  log "APPLY $action $id"
  case "$action" in
    hover)
      if detail_ouvert; then log "  skip (modale ouverte)"; return; fi
      ew update hovered_id="$id" ;;
    unhover)
      ew update hovered_id="" ;;
    ev_hover)
      if detail_ouvert; then log "  skip (modale ouverte)"; return; fi
      ew update ev_hovered_id="$id" ;;
    ev_unhover)
      ew update ev_hovered_id="" ;;
  esac
}

log "demon demarre (pid $$)"

while IFS=' ' read -r -u 3 action id; do
  log "recu $action $id"
  # Stabilisation anti-rafale : quand la souris balaie plusieurs items, on
  # ne veut appliquer que l'etat FINAL (le dernier item reellement survole),
  # pas chaque etape intermediaire. On n'applique un evenement qu'apres
  # ~30ms sans qu'aucun nouveau n'arrive : chaque nouvel evenement relance
  # l'attente. La variable ne bouge donc plus tant que la souris est encore
  # en mouvement, et ne change qu'une fois que la souris s'est reellement
  # arretee -- moins de mises a jour inutiles, et l'etat affiche correspond
  # toujours a l'endroit ou la souris est vraiment.
  mail_action=""; mail_id=""
  ev_action="";   ev_id=""
  case "$action" in
    hover|unhover)       mail_action="$action"; mail_id="$id" ;;
    ev_hover|ev_unhover) ev_action="$action";   ev_id="$id" ;;
  esac
  while IFS=' ' read -t 0.03 -r -u 3 action id; do
    log "recu $action $id (stabilisation)"
    case "$action" in
      hover|unhover)       mail_action="$action"; mail_id="$id" ;;
      ev_hover|ev_unhover) ev_action="$action";   ev_id="$id" ;;
    esac
  done

  [ -n "$mail_action" ] && apply "$mail_action" "$mail_id"
  [ -n "$ev_action" ]   && apply "$ev_action" "$ev_id"
done
