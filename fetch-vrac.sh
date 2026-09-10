#!/usr/bin/env bash
# fetch-vrac.sh - compteur du "vrac" (brain dump) affiche dans le bandeau.
#
# Vrac = taches Taskwarrior en attente SANS date d'echeance. Poser une date,
# c'est promouvoir une idee en engagement : la tache quitte alors le vrac et
# passe dans le panneau A VENIR.
#   total     = toutes les taches en attente sans date
#   nouvelles = celles creees il y a moins de 24 h
#   texte     = ligne affichee telle quelle par eww ("en vrac 23 · 4 nouvelles")
#
# Calcule en LOCAL : Taskwarrior est sur cette machine et il ne s'agit que
# d'un comptage, sans LLM. Si ce compteur doit un jour venir de n8n (quand
# les taches y seront envoyees), seul ce script changera : eww ne lit que
# le JSON ci-dessous.
#
# rc.gc=off / rc.recurrence=off / rc.hooks=off : une simple lecture ne doit
# JAMAIS modifier la base (renumerotation des id, creation d'occurrences de
# taches recurrentes, execution de hooks).
TW="task rc.verbose=nothing rc.gc=off rc.recurrence=off rc.hooks=off rc.confirmation=off"

total="$($TW status:pending due.none: count 2>/dev/null)"
nouv="$($TW status:pending due.none: entry.after:now-24h count 2>/dev/null)"

# Taskwarrior absent ou en erreur : texte vide, eww masque le compteur.
if ! [[ "$total" =~ ^[0-9]+$ ]]; then
  echo '{"total":0,"nouvelles":0,"texte":""}'
  exit 0
fi
[[ "$nouv" =~ ^[0-9]+$ ]] || nouv=0

texte="en vrac $total"
if   [ "$nouv" -eq 1 ]; then texte="$texte · 1 nouvelle"
elif [ "$nouv" -gt 1 ]; then texte="$texte · $nouv nouvelles"
fi

printf '{"total":%d,"nouvelles":%d,"texte":"%s"}\n' "$total" "$nouv" "$texte"
