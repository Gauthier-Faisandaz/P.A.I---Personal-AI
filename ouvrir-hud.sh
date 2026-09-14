#!/usr/bin/env bash
# ouvrir-hud.sh - (re)ouvre les fenetres du panneau d'angle (colonne
# d'hexagones au bord gauche : hud-heure, hud-meteo, hud-sparklines) sur
# l'ecran du dashboard, puis leur pose leur decoupe.
# Appele par start.sh (demarrage) et eww-watchdog.sh (apres un redemarrage
# force du demon). Relancable a la main a tout moment.
#
# Meme ecran que la colonne : on le lit dans ~/.cache/eww/target_screen,
# ecrit par start.sh. Pourquoi un script separe de ouvrir-colonne.sh : le HUD
# est un chantier independant, et il n'a besoin de rien calculer. Sa
# geometrie est fixe (recopiee de cadre.py dans eww.yuck) ; la colonne, elle,
# depend de la hauteur de l'ecran et des marges de geometrie.conf.
EWW="$HOME/.cargo/bin/eww"
CFG="$HOME/.config/eww"

TARGET="$(cat "$HOME/.cache/eww/target_screen" 2>/dev/null)"
[ -z "$TARGET" ] && TARGET=0

# Noms des fenetres : lus dans cadre.py (source unique), pas recopies ici.
FENETRES="$(python3 -B -c "import sys; sys.path.insert(0, '$CFG'); import cadre; print(*map(cadre.fenetre_eww, cadre.PIECES))")"

# Fermer d'abord (sans erreur si deja fermees) : le script est relancable.
for f in $FENETRES; do "$EWW" close "$f" 2>/dev/null; done
for f in $FENETRES; do "$EWW" open "$f" --screen "$TARGET"; done

# Decoupe (forme des hexagones, pour que picom ne floute qu'eux) tout de
# suite, plutot qu'au prochain tick du watchdog : evite de voir 2 s de
# rectangles flous a l'ouverture. --attendre : "eww open" peut rendre la main
# avant que les fenetres existent ; le script les guette jusqu'a 3 s.
python3 -B "$CFG/decoupe-hud.py" --attendre
