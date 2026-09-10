#!/usr/bin/env bash
# fetch-sys.sh - CPU / RAM / reseau pour le bandeau, en % (0-100) pour les
# barres. Sortie : {"cpu":12,"ram":48,"net":3}
#
# Appele par un defpoll toutes les 5 s (voir eww.yuck). Pourquoi pas les
# variables magiques d'eww (EWW_CPU, EWW_RAM, EWW_NET) : d'apres la doc eww,
# elles se rafraichissent toutes les 2 s, sans reglage possible. Le brief
# demande 3 a 5 s : le dashboard ne doit pas couter du CPU pour afficher le
# CPU (i5-4210U), et chaque rafraichissement du bandeau fait aussi
# recalculer par picom le flou derriere la fenetre.
#
# CPU et reseau sont des DIFFERENCES entre deux appels (les compteurs du
# noyau ne font qu'augmenter) : l'etat precedent est garde dans PREV. Au
# tout premier appel, il n'y a pas d'etat precedent : on affiche 0.

# ============================ REGLAGE ============================
# Debit (descendant + montant) qui remplit la barre NET, en octets/s.
# 1250000 octets/s = 10 Mbit/s.
NET_MAX=1250000
# ================================================================

PREV="$HOME/.cache/eww/sys.prev"

# CPU : 1re ligne de /proc/stat = temps cumules de tous les coeurs.
# Colonnes : user nice system idle iowait irq softirq steal
read -r _ user nice system idle iowait irq softirq steal _ < /proc/stat
busy=$((user + nice + system + irq + softirq + steal))
total=$((busy + idle + iowait))

# RAM : part utilisee = (total - disponible) / total.
ram=$(awk '/^MemTotal:/ {t=$2} /^MemAvailable:/ {a=$2}
           END {if (t > 0) printf "%d", (t - a) * 100 / t; else print 0}' /proc/meminfo)

# Reseau : octets recus + emis, toutes interfaces sauf lo (la boucle locale,
# qui ne passe pas par le reseau). Colonnes : iface rx ... (8 champs) tx ...
net=$(awk -F'[: ]+' 'NR > 2 && $2 != "lo" {s += $3 + $11} END {printf "%d", s}' /proc/net/dev)

# Instant present en MICROsecondes entieres. $EPOCHREALTIME (bash >= 5)
# donne des secondes avec decimales, mais le separateur suit la locale
# ("1789058993,280525" en francais) et awk ne lirait que la partie entiere :
# on retire donc le separateur, quel qu'il soit.
now=${EPOCHREALTIME/[,.]/}

# Etat precedent (absent au 1er appel -> on reprend les valeurs actuelles,
# ce qui donne des differences nulles).
# (test -r d'abord : un "read < fichier_absent" affiche une erreur que
# "2>/dev/null" ne masque pas, la redirection d'entree echouant la 1re.)
[ -r "$PREV" ] && read -r pbusy ptotal pnet pnow < "$PREV"
[ -n "$pnow" ] || { pbusy=$busy; ptotal=$total; pnet=$net; pnow=$now; }
printf '%s %s %s %s\n' "$busy" "$total" "$net" "$now" > "$PREV"

awk -v b="$busy" -v t="$total" -v pb="$pbusy" -v pt="$ptotal" \
    -v n="$net" -v pn="$pnet" -v now="$now" -v pnow="$pnow" \
    -v max="$NET_MAX" -v ram="$ram" 'BEGIN {
  cpu = (t > pt) ? (b - pb) * 100 / (t - pt) : 0
  # now et pnow sont en microsecondes : /1e6 pour des octets par SECONDE
  net = (now > pnow) ? (n - pn) / ((now - pnow) / 1e6) * 100 / max : 0
  if (net > 100) net = 100
  if (net < 0)   net = 0
  printf "{\"cpu\":%d,\"ram\":%d,\"net\":%d}\n", cpu, ram, net
}'
