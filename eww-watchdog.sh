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
#
# Seconde tache (panneau d'angle, 12/09) : a chaque tick, redonner sa
# decoupe a la fenetre "hud" si elle l'a perdue (voir decoupe-hud.py).
CACHE="$HOME/.cache/eww"
LOCK="$CACHE/watchdog.lock"
LOG="$CACHE/watchdog.log"
EWW="$HOME/.cargo/bin/eww"
CFG="$HOME/.config/eww"
mkdir -p "$CACHE"
: > "$LOG"

log() { printf '%s %s\n' "$(date '+%H:%M:%S.%3N')" "$*" >> "$LOG"; }

# Une seule instance a la fois (meme principe que hoverd.sh en son temps).
# -w 5 (attendre jusqu'a 5 s) et non -n (abandonner tout de suite) : le
# verrou est herite par le "sleep 2" de la boucle ci-dessous. Quand
# start.sh tue l'ancien surveillant, ce sleep orphelin garde le verrou
# jusqu'a 2 s de plus ; avec -n, le nouveau surveillant abandonnait aussitot
# et le dashboard restait SANS surveillant (constate le 11/09 : watchdog.log
# vide depuis le matin). Un vrai second surveillant attend 5 s puis s'arrete.
exec 9>"$LOCK"
flock -w 5 9 || exit 0

log "watchdog demarre (pid $$)"

full_restart() {
  log "REDEMARRAGE COMPLET (blocage detecte)"
  # pkill -9 directement sur le nom du binaire -- PAS "eww kill" (lui-meme
  # potentiellement ignore par un demon bloque, voir plus haut). Ceci tue
  # le demon ET tout client "eww open/close" fantome en un seul coup,
  # exactement comme le "killall eww" manuel qui a toujours fonctionne.
  # -x eww = process dont le NOM est exactement "eww" (le binaire), comme
  # dans start.sh. Surtout pas "pkill -f '/eww '" (version precedente) :
  # -f cherche dans la ligne de commande COMPLETE, et tuait donc aussi tout
  # process qui contenait "~/.config/eww " -- un terminal, un editeur, un
  # script (constate le 11/09 : une commande lancee par "cd ~/.config/eww
  # && ..." a ete tuee en plein milieu lors d'un redemarrage).
  pkill -9 -x eww 2>/dev/null
  sleep 0.5
  : > "$CACHE/eww-daemon.out.log"
  RUST_LOG=debug "$EWW" daemon > "$CACHE/eww-daemon.out.log" 2>&1 &
  sleep 1.5
  # Meme ecran et meme geometrie que start.sh : ouvrir-colonne.sh relit
  # target_screen et geometrie.conf.
  bash "$CFG/ouvrir-colonne.sh" 2>/dev/null
  # Le panneau d'angle aussi (meme ecran, lu dans target_screen) : le demon
  # tue ci-dessus l'a emporte avec lui.
  bash "$CFG/ouvrir-hud.sh" >/dev/null 2>&1
  log "redemarrage termine"
}

while true; do
  # etimes (secondes ecoulees) + ligne de commande de chaque process eww en
  # cours ; on ne cible que "open"/"close" (jamais "daemon", qui doit
  # rester vivant en continu).
  # -C eww : seulement les process dont le NOM est "eww" (le binaire).
  # Avant, on fouillait la ligne de commande de TOUS les process : un
  # script ou un terminal dont la commande contenait "/eww open" depuis
  # 4 s aurait declenche un redemarrage pour rien. (Le "=" apres chaque
  # colonne supprime la ligne d'en-tete de ps.)
  stuck="$(ps -C eww -o pid=,etimes=,args= 2>/dev/null | grep -E '/eww (open|close) ' | awk '$2 >= 4')"
  if [ -n "$stuck" ]; then
    log "detecte : $stuck"
    full_restart
  fi

  # Decoupe du panneau d'angle : la forme de la fenetre "hud" est perdue a
  # chaque recreation (eww reload, enregistrement de eww.yuck, close/open),
  # et une fenetre recreee a un NOUVEL identifiant X. On relit donc
  # l'identifiant a chaque tick (xwininfo : ~5 ms, programme en C) et on ne
  # lance decoupe-hud.py (Python : ~25 ms) que s'il a change. Lancer Python a
  # chaque tick coutait ~4 % d'un coeur en permanence (mesure le 12/09).
  # hud_decoupe = identifiant dont la forme est CONFIRMEE (code 0) : en cas
  # d'echec, il ne change pas, et le tick suivant reessaie.
  # xwininfo et decoupe-hud.py parlent au serveur X, jamais au demon eww :
  # un demon bloque ne les bloque pas.
  hud="$(xwininfo -name 'Eww - hud' 2>/dev/null | awk '/Window id/ {print $4}')"
  if [ -n "$hud" ] && [ "$hud" != "$hud_decoupe" ]; then
    out="$(python3 -B "$CFG/decoupe-hud.py" --xid "$hud" 2>&1)" && hud_decoupe="$hud"
    [ -n "$out" ] && log "hud : $out"
  fi

  sleep 2
done
