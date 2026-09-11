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

# (Marges de la colonne -- haut/bas et bord droit : voir geometrie.conf)
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
#
# Garantie "un seul demon" (10/09) : "eww kill" est une commande IPC, qu'un
# demon bloque ignore (meme constat que dans eww-watchdog.sh). Constate au
# rebranchement de l'ecran HDMI : l'ancien demon a survecu, un second a ete
# lance a cote, et l'ancienne colonne est restee affichee sur le portable.
# Donc : "eww kill" poli (borne a 2s), on attend jusqu'a 2s que le process
# disparaisse, et s'il est encore la on le tue directement (kill -9).
# -x eww = processus dont le NOM est exactement "eww" (le binaire : demon et
# clients open/close eventuellement bloques). Surtout pas "pkill -f '/eww '"
# : ca tuerait aussi tout process dont la ligne de commande contient
# "~/.config/eww " (un terminal, un editeur...) -- constate le 10/09.
timeout 2 "$EWW" kill 2>/dev/null
for i in 1 2 3 4 5 6 7 8 9 10; do
  pgrep -x eww >/dev/null || break
  sleep 0.2
done
if pgrep -x eww >/dev/null; then
  echo "$(date '+%F %T') - demon eww sourd a 'eww kill', kill -9" >> "$LOG"
  pkill -9 -x eww 2>/dev/null
  sleep 0.3
fi
: > "$HOME/.cache/eww/eww-daemon.out.log"
RUST_LOG=debug "$EWW" daemon > "$HOME/.cache/eww/eww-daemon.out.log" 2>&1 &
sleep 1.5

# Le survol (et le demon hoverd.sh / pipe FIFO qui le pilotait) a ete retire
# le 12/08 -- voir eww.yuck. Seul le clic subsiste desormais ; il n'a besoin
# d'aucun demon dedie (pas de risque de course sur un clic comme il y en
# avait sur un survol).
#
# Motifs ANCRES (^...$) pour ce pkill et celui du surveillant, plus bas :
# la ligne de commande doit etre EXACTEMENT "bash <chemin>/hoverd.sh".
# Sans ancres, "bash .*/hoverd\.sh" visait aussi toute commande qui
# contenait ces mots quelque part (un "bash -c '... hoverd.sh'" lance
# depuis un terminal ou un outil) -- meme famille de bug que le pkill -f
# du surveillant, corrige le 11/09. [^ ]* = un mot sans espace (le chemin
# de bash, puis celui du script).
pkill -f "^[^ ]*bash ([^ ]*/)?hoverd\.sh$" 2>/dev/null   # au cas ou une vieille instance trainerait

# --- Surveillant anti-blocage (24/08) --------------------------------------
# Bug upstream confirme (elkowar/eww #451, #255), present meme en 0.6.0 (le
# plus recent) : le demon peut se bloquer sur "eww open"/"eww close" au clic,
# meme sans clics rapides. Constate : ni "eww kill" ni "bash start.sh" ne
# reparent une fenetre bloquee -- seul un "killall eww" (signal direct au
# process, sans passer par le demon) marche a coup sur. Ce surveillant fait
# exactement ca automatiquement : voir eww-watchdog.sh pour le detail.
pkill -f "^[^ ]*bash ([^ ]*/)?eww-watchdog\.sh$" 2>/dev/null   # motif ancre : voir hoverd.sh plus haut
nohup bash "$HOME/.config/eww/eww-watchdog.sh" >/dev/null 2>&1 &
disown

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

# Memorise l'ecran cible (utilise plus bas dans ce script)
printf '%s' "$TARGET" > "$HOME/.cache/eww/target_screen"

# --- Ouverture de la colonne sur le bon ecran -----------------------------
# Depuis la refonte (09/2026), tout le dashboard tient dans UNE seule
# fenetre, "colonne" (voir eww.yuck). Sa geometrie (hauteur selon l'ecran,
# marges de geometrie.conf) est calculee par ouvrir-colonne.sh, partage
# avec eww-watchdog.sh et marge.sh. Il lit l'ecran dans target_screen,
# ecrit juste au-dessus.
bash "$HOME/.config/eww/ouvrir-colonne.sh"

# (La 2e fenetre, "modale" -- le detail d'un mail --, n'est PAS ouverte
# ici : ui.sh l'ouvre au clic sur un mail et la ferme a la croix, avec de
# vrais open/close. Voir ui.sh pour la raison : fond fantome sous picom.)
