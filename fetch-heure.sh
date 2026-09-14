#!/usr/bin/env bash
# fetch-heure.sh - heure et date du panneau d'angle (hexagone du haut).
# Sortie : une ligne JSON a chaque changement, lue par le "deflisten
# hud_temps" de eww.yuck :
#     {"heure":"14:32","date":"lun. 14 sept."}
#
# Pourquoi un deflisten (script qui tourne en continu) plutot qu'un defpoll
# toutes les 10 s comme l'horloge du bandeau : l'heure est ici l'element
# principal, elle doit changer PILE a la minute. Le script dort jusqu'a la
# minute suivante au lieu d'interroger l'heure en boucle.
#
# Jamais plus de 10 s de sommeil d'affilee : "sleep" compte le temps sur une
# horloge qui s'arrete pendant une mise en veille. Sans ce plafond, apres une
# veille d'une heure, l'heure affichee resterait fausse jusqu'a une minute ;
# avec, elle se recale en 10 s au plus.
# On n'ecrit que si le texte a change : eww ne redessine rien pour rien.
#
# Pourquoi pas la variable eww EWW_TIME + formattime : formattime ne connait
# pas les langues, la date serait en anglais ("Mon 14 Sep").
# Date en francais par la locale, comme le bandeau : "lun. 14 sept.".

prec=""
while true; do
  maintenant="$(LC_TIME=fr_FR.UTF-8 date '+{"heure":"%H:%M","date":"%a %-d %b"}')"
  if [ "$maintenant" != "$prec" ]; then
    printf '%s\n' "$maintenant"
    prec="$maintenant"
  fi
  # Secondes avant la minute suivante (10# : "08" n'est pas un nombre octal).
  reste=$(( 60 - 10#$(date +%S) ))
  sleep $(( reste < 10 ? reste : 10 ))
done
