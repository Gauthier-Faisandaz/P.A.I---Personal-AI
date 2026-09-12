#!/usr/bin/env bash
# ouvrir-hud.sh - (re)ouvre la fenetre "hud" (panneau d'angle, coin
# haut-gauche) sur l'ecran du dashboard, puis lui pose sa decoupe.
# Appele par start.sh (demarrage) et eww-watchdog.sh (apres un redemarrage
# force du demon). Relancable a la main a tout moment.
#
# Meme ecran que la colonne : on le lit dans ~/.cache/eww/target_screen,
# ecrit par start.sh. Pourquoi un script separe de ouvrir-colonne.sh : le HUD
# est un chantier independant, et il n'a besoin de rien calculer. Sa
# geometrie est fixe (recopiee de cadre.py dans eww.yuck) ; la colonne, elle,
# depend de la hauteur de l'ecran et des marges de geometrie.conf.
EWW="$HOME/.cargo/bin/eww"

TARGET="$(cat "$HOME/.cache/eww/target_screen" 2>/dev/null)"
[ -z "$TARGET" ] && TARGET=0

# Fermer d'abord (sans erreur si deja fermee) : le script est relancable.
"$EWW" close hud 2>/dev/null
"$EWW" open hud --screen "$TARGET"

# Decoupe (forme des trois pieces, pour que picom ne floute qu'elles) tout
# de suite, plutot qu'au prochain tick du watchdog : evite de voir 2 s de
# rectangle flou a l'ouverture. --attendre : "eww open" peut rendre la main
# avant que la fenetre existe ; le script la guette jusqu'a 3 s.
python3 -B "$HOME/.config/eww/decoupe-hud.py" --attendre
