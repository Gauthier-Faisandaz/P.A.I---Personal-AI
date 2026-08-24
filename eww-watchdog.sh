#!/usr/bin/env bash
# eww-watchdog.sh - detecte un blocage du demon eww et le redemarre
# ENTIEREMENT (pas juste tuer le client bloque).
#
# Pourquoi un redemarrage complet et pas juste "kill -9" sur le client
# bloque : constate le 12/08 par l'utilisateur, meme "bash start.sh" (qui
# fait "eww kill" puis relance un demon frais) ne repare PAS une fenetre
# bloquee -- la fenetre reste affichee, plantee. Cause probable : "eww
# kill" est lui-meme une commande IPC envoyee au demon, et un demon deja
# bloque peut tout simplement l'ignorer, exactement comme il ignore "eww
# close"/"eww open". Seul un `killall eww` (qui tue le PROCESS directement,
# sans passer par le demon pour repondre) a fonctionne de facon fiable a
# chaque fois. Ce script fait donc la meme chose que "killall eww" +
# "bash start.sh" combines, automatiquement, des qu'un blocage est detecte.
CACHE="$HOME/.cache/eww"
LOCK="$CACHE/watchdog.lock"
LOG="$CACHE/watchdog.log"
EWW="$HOME/.cargo/bin/eww"
mkdir -p "$CACHE"
: > "$LOG"

log() { printf '%s %s\n' "$(date '+%H:%M:%S.%3N')" "$*" >> "$LOG"; }

# Une seule instance a la fois (meme principe que hoverd.sh en son temps).
exec 9>"$LOCK"
flock -n 9 || exit 0

log "watchdog demarre (pid $$)"

full_restart() {
  log "REDEMARRAGE COMPLET (blocage detecte)"
  # pkill -9 directement sur le nom du binaire -- PAS "eww kill" (lui-meme
  # potentiellement ignore par un demon bloque, voir plus haut). Ceci tue
  # le demon ET tout client "eww open/close" fantome en un seul coup,
  # exactement comme le "killall eww" manuel qui a toujours fonctionne.
  pkill -9 -f "/eww " 2>/dev/null
  sleep 0.5
  : > "$CACHE/eww-daemon.out.log"
  RUST_LOG=debug "$EWW" daemon > "$CACHE/eww-daemon.out.log" 2>&1 &
  sleep 1.5
  TARGET="$(cat "$CACHE/target_screen" 2>/dev/null)"
  "$EWW" close recos digest events detail ev_detail 2>/dev/null
  "$EWW" open recos  --screen "$TARGET" 2>/dev/null
  "$EWW" open digest --screen "$TARGET" 2>/dev/null
  "$EWW" open events --screen "$TARGET" 2>/dev/null
  log "redemarrage termine"
}

while true; do
  # etimes (secondes ecoulees) + ligne de commande de chaque process eww en
  # cours ; on ne cible que "open"/"close" (jamais "daemon", qui doit
  # rester vivant en continu).
  stuck="$(ps -eo pid,etimes,args 2>/dev/null | grep -E '/eww (open|close) ' | grep -v grep | awk '$2 >= 4')"
  if [ -n "$stuck" ]; then
    log "detecte : $stuck"
    full_restart
  fi
  sleep 2
done
