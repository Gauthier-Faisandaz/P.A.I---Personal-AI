#!/usr/bin/env bash
# hoverd.sh - demon persistant qui applique les evenements de survol
# (mail + agenda) dans l'ordre EXACT ou ils arrivent.
#
# Pourquoi ce demon :
# Chaque entree/sortie de survol declenche un appel independant depuis
# ui.sh. Si chacun de ces appels faisait directement "eww update"/"eww
# open"/"eww close" dans son propre process, rien ne garantirait qu'ils
# s'executent dans l'ordre ou GTK a reellement declenche les evenements
# (demarrage d'un interprete a cout variable) -- lors d'un survol rapide,
# un evenement plus ANCIEN pourrait s'appliquer APRES un evenement plus
# RECENT et laisser l'etat affiche en retard sur la souris.
#
# Ici, ui.sh ne fait plus qu'ecrire une ligne dans un pipe (ecriture quasi
# instantanee). Ce demon, lance UNE SEULE fois par start.sh, lit et applique
# ces lignes strictement dans leur ordre d'arrivee : par construction, le
# dernier evenement ecrit est toujours le dernier applique, sans exception
# possible (un seul lecteur, un seul thread, aucune course).
#
# ARCHITECTURE (12/08, voir le commentaire en haut de eww.yuck) :
# preview/ev_preview ne sont PAS mappees en permanence (fond fantome
# constate avec cette approche, deux fois, avec des techniques differentes)
# et ne sont PAS ouvertes/fermees a chaque item survole non plus (peu
# fiable, meme lentement -- constate a l'iteration 11). Compromis : ce
# demon n'ouvre REELLEMENT la fenetre qu'au tout premier survol d'une
# "session" (mail_open/ev_open passe de 0 a 1), et ne la ferme REELLEMENT
# que quand la souris quitte VRAIMENT toute la liste (plus jamais un
# nouveau hover juste apres). Entre les deux, passer d'un item a l'autre ne
# fait qu'un "eww update hovered_id" (pas de remap X11). Grace a la
# stabilisation anti-rafale ci-dessous, "sortie d'un item + entree sur le
# suivant" se rassemble deja naturellement en un seul evenement avant meme
# d'atteindre apply() -- l'ouverture/fermeture reelle redevient donc aussi
# rare qu'un clic (deja prouve fiable), tout en gardant les transitions
# rapides instantanees.
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

mail_open=0
ev_open=0

apply() {
  local action="$1" id="$2"
  log "APPLY $action $id (mail_open=$mail_open ev_open=$ev_open)"
  case "$action" in
    hover)
      if detail_ouvert; then log "  skip (modale ouverte)"; return; fi
      if [ "$mail_open" != "1" ]; then
        ew open preview --screen "$(cat "$CACHE/target_screen" 2>/dev/null)"
        mail_open=1
      fi
      ew update hovered_id="$id" ;;
    unhover)
      ew update hovered_id=""
      if [ "$mail_open" = "1" ]; then
        ew close preview
        mail_open=0
      fi ;;
    ev_hover)
      if detail_ouvert; then log "  skip (modale ouverte)"; return; fi
      if [ "$ev_open" != "1" ]; then
        ew open ev_preview --screen "$(cat "$CACHE/target_screen" 2>/dev/null)"
        ev_open=1
      fi
      ew update ev_hovered_id="$id" ;;
    ev_unhover)
      ew update ev_hovered_id=""
      if [ "$ev_open" = "1" ]; then
        ew close ev_preview
        ev_open=0
      fi ;;
  esac
}

log "demon demarre (pid $$)"

while IFS=' ' read -r -u 3 action id; do
  log "recu $action $id"
  # Stabilisation anti-rafale : quand la souris balaie plusieurs items, on
  # ne veut appliquer que l'etat FINAL (le dernier item reellement survole),
  # pas chaque etape intermediaire. On n'applique un evenement qu'apres
  # ~30ms sans qu'aucun nouveau n'arrive : chaque nouvel evenement relance
  # l'attente. C'est ce qui fait qu'une transition "sortie d'un item + entree
  # sur le suivant" (deux evenements bruts) ne produit qu'un SEUL appel a
  # apply() -- generalement juste "hover(suivant)", jamais "unhover" puis
  # "hover" separement -- donc jamais de fermeture/reouverture reelle entre
  # deux items adjacents.
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
