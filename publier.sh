#!/usr/bin/env bash
# publier.sh - dernier maillon de chaque fetch-*.sh :
#     ... | bash ~/.config/eww/publier.sh digest|recos|venir
#
# 1. garde une copie du JSON dans ~/.cache/eww/bus/<nom>.json : c'est la
#    que mise-en-page.py lit les donnees des trois panneaux ;
# 2. renvoie le JSON tel quel sur la sortie standard : c'est elle que lit le
#    defpoll (ou sync.sh), rien ne change pour eww ;
# 3. relance le calcul des hauteurs des panneaux, en arriere-plan.
#
# Pourquoi ici : c'est le seul endroit par lequel passent TOUTES les
# nouvelles donnees (defpoll automatique comme bouton ↻, qui appellent les
# memes fetch-*.sh). Pas de boucle possible : mise-en-page.py ecrit des
# variables eww (h_*, y_*), jamais dans le bus ni dans digest/recos/venir.
BUS="$HOME/.cache/eww/bus"
nom="$1"
case "$nom" in
  digest|recos|venir) ;;
  *) echo "publier.sh : nom inconnu '$nom'" >&2; cat; exit 1 ;;
esac
mkdir -p "$BUS"

# Ecriture dans un fichier temporaire puis "mv" (instantane) : le calcul ne
# peut jamais lire un fichier a moitie ecrit.
tmp="$(mktemp "$BUS/.$nom.XXXXXX")"
cat > "$tmp"
cat "$tmp"
mv -f "$tmp" "$BUS/$nom.json"

# En arriere-plan, et sorties redirigees : sinon eww attendrait la fin du
# calcul (il lit la sortie du defpoll jusqu'a ce qu'elle se ferme). Le
# journal ne garde que le dernier calcul : voir ~/.cache/eww/mise-en-page.log
nohup python3 "$HOME/.config/eww/mise-en-page.py" --pousser \
  < /dev/null > "$HOME/.cache/eww/mise-en-page.log" 2>&1 &
