#!/usr/bin/env bash
# start.sh - lance le dashboard eww sur le bon ecran selon la config detectee.
#   - 2 ecrans (portable + externe) : affiche sur l'ecran choisi ci-dessous
#   - portable seul (itinerance)    : affiche sur l'ecran du portable
# Ce script est relançable : en cas de branchement/debranchement d'un ecran,
# relancez-le simplement pour repositionner les fenetres.

# ============================ REGLAGE ============================
# En configuration 2 ecrans, ou afficher le dashboard ?
#   "external" = l'ecran fixe (celui de droite)
#   "laptop"   = l'ecran du portable
DUAL_TARGET="external"
# ================================================================

EWW="$HOME/.cargo/bin/eww"
LOG="$HOME/.cache/eww-start.log"

mkdir -p "$HOME/.cache/eww"
echo "$(date '+%F %T') - start.sh lance" >> "$LOG"

# --- Compositeur (transparence + flou) ------------------------------------
# Au demarrage de session, le pilote GPU n'est pas toujours pret : picom peut
# echouer a initialiser glx et quitter aussitot -> fenetres eww noires.
# On attend un peu, on reessaye, et on garde un repli sans flou en dernier recours.

# Delai uniquement quand le script est lance par l'autostart (pas depuis un
# terminal, ou l'on veut une relance immediate).
[ -t 1 ] || sleep 5

if ! pgrep -x picom >/dev/null; then
  for i in 1 2 3; do
    # 'picom -b' sans --backend : lit ~/.config/picom.conf (glx + flou dual_kawase)
    picom -b --log-file="$HOME/.cache/picom.log"
    sleep 3
    pgrep -x picom >/dev/null && break
  done
fi

# Repli : si glx a echoue 3 fois, on repart en xrender.
# Transparence conservee, flou perdu -- mais jamais de fenetre noire.
if ! pgrep -x picom >/dev/null; then
  echo "$(date '+%F %T') - picom glx KO, repli xrender" >> "$LOG"
  picom --backend xrender -b
fi

# Demon eww
# On le tue et on le relance a chaque fois : sinon "eww daemon" ne fait rien
# s'il en detecte deja un qui tourne, et on garde indefiniment la meme
# instance -- constate le 12/08 (eww logs ne montrait que des evenements du
# 10/08, alors que start.sh avait ete relance des dizaines de fois entre
# temps). Un demon GTK qui tourne en continu depuis des jours, apres des
# milliers d'ouvertures/fermetures de fenetres, peut accumuler un etat
# incoherent -- ca vaut la peine de repartir propre.
# RUST_LOG=debug : logs detailles. On capture stdout/stderr directement dans
# un fichier qu'on controle plutot que de compter sur `eww logs` -- constate
# que le fichier interne d'eww (~/.cache/eww/eww_*.log) n'est plus ecrit
# depuis le 10/08 alors que le demon a ete relance des dizaines de fois
# depuis : soit eww logue sur stdout/stderr (qu'on jetait jusqu'ici avec
# >/dev/null), soit son propre mecanisme de log est peu fiable. Dans les
# deux cas, mieux vaut avoir notre propre capture.
"$EWW" kill 2>/dev/null
sleep 0.3
: > "$HOME/.cache/eww/eww-daemon.out.log"
RUST_LOG=debug "$EWW" daemon > "$HOME/.cache/eww/eww-daemon.out.log" 2>&1 &
sleep 1.5

# --- Detection des ecrans connectes (X11 / xrandr) ------------------------
CONNECTED="$(xrandr --query | grep -w connected)"
LAPTOP="$(printf  '%s\n' "$CONNECTED" | grep -Ei '^(eDP|LVDS)'        | head -n1 | cut -d' ' -f1)"
EXTERNAL="$(printf '%s\n' "$CONNECTED" | grep -Ei '^(HDMI|DP|DVI|VGA)' | head -n1 | cut -d' ' -f1)"

# --- Choix de l'ecran cible ----------------------------------------------
if [ -n "$EXTERNAL" ]; then
  # Deux ecrans : on suit le reglage DUAL_TARGET
  if [ "$DUAL_TARGET" = "laptop" ] && [ -n "$LAPTOP" ]; then
    TARGET="$LAPTOP"
  else
    TARGET="$EXTERNAL"
  fi
else
  # Un seul ecran : le portable
  TARGET="$LAPTOP"
fi

# Repli de securite si la detection echoue (ex: xrandr absent)
[ -z "$TARGET" ] && TARGET=0

echo "eww : affichage du dashboard sur l'ecran -> $TARGET"
echo "$(date '+%F %T') - ecran cible : $TARGET" >> "$LOG"

# Memorise l'ecran cible (lu par ui.sh ET par hoverd.sh -- doit donc etre
# ecrit AVANT de lancer hoverd.sh ci-dessous).
printf '%s' "$TARGET" > "$HOME/.cache/eww/target_screen"

# Demon de survol (voir hoverd.sh) : serialise les evenements hover/unhover
# pour eviter toute course lors d'un survol rapide, et decide lui-meme quand
# ouvrir/fermer reellement preview/ev_preview.
# On tue toute instance precedente avant de relancer : sinon, le verrou
# interne du demon (flock, pense pour eviter les doublons) empeche une
# nouvelle version du script de jamais prendre la main -- l'ancienne
# instance continuerait de tourner indefiniment en arriere-plan.
pkill -f "bash .*/hoverd\.sh" 2>/dev/null
sleep 0.3
: > "$HOME/.cache/eww/ui.log"   # journal cote emetteur (voir ui.sh), repart a zero
nohup bash "$HOME/.config/eww/hoverd.sh" >/dev/null 2>&1 &
disown 2>/dev/null

# --- Ouverture des fenetres sur le bon ecran ------------------------------
# On ferme d'abord (sans erreur si deja ferme) pour que le script soit relançable.
"$EWW" close recos digest events preview detail ev_preview ev_detail 2>/dev/null

"$EWW" open  recos  --screen "$TARGET"
"$EWW" open  digest --screen "$TARGET"
"$EWW" open  events --screen "$TARGET"

# preview/detail/ev_preview/ev_detail ne sont PAS ouvertes ici : elles ne le
# sont qu'a la demande (survol -> hoverd.sh, clic -> ui.sh) -- constate le
# 12/08 : les garder mappees en permanence laisse un fond fantome visible
# au repos sous ce compositeur, quelle que soit la technique de masquage du
# contenu essayee.
