#!/usr/bin/env bash
# ouvrir-hud.sh - (re)ouvre la fenetre "hud" (panneau d'angle, coin
# haut-gauche) sur l'ecran du dashboard.
#
# Meme ecran que la colonne : on le lit dans ~/.cache/eww/target_screen,
# ecrit par start.sh. Pourquoi un script separe de ouvrir-colonne.sh : le HUD
# est un chantier independant, et il n'a besoin de rien calculer. Sa
# geometrie est fixe (recopiee de cadre.py dans eww.yuck) ; la colonne, elle,
# depend de la hauteur de l'ecran et des marges de geometrie.conf.
#
# Etape 2 : a lancer a la main. A l'etape 3 (decoupe X Shape), start.sh et
# eww-watchdog.sh l'appelleront, et la decoupe sera appliquee juste apres.
EWW="$HOME/.cargo/bin/eww"

TARGET="$(cat "$HOME/.cache/eww/target_screen" 2>/dev/null)"
[ -z "$TARGET" ] && TARGET=0

# Fermer d'abord (sans erreur si deja fermee) : le script est relancable.
"$EWW" close hud 2>/dev/null
"$EWW" open hud --screen "$TARGET"
