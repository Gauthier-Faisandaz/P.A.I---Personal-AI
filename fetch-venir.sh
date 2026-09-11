#!/usr/bin/env bash
# fetch-venir.sh - panneau A VENIR : evenements Google Agenda + taches
# Taskwarrior datees, DEJA fusionnes, tries et groupes par n8n.
#
# Contrat (brief de la refonte, section 7) - n8n renvoie :
#   { "synchro": "09:55",
#     "resume":  "1 en retard · 2 aujourd'hui",
#     "groupes": [ { "cle": "retard", "libelle": "EN RETARD",
#                    "compte": 1,          (facultatif)
#                    "date": "jeu. 10",    (facultatif)
#                    "items": [ { "type": "tache" | "event",
#                                 "titre": "...",
#                                 "quand": "−1 j" } ] } ] }   (quand : facultatif)
#
# Tout le travail (fusion des deux sources, regroupement en retard /
# aujourd'hui / demain / cette semaine, calcul du resume) est fait COTE N8N.
# Ce script se contente de :
#   - trouver ce JSON dans l'enveloppe n8n (comme les autres fetch-*.sh),
#   - completer les champs facultatifs, pour que eww n'ait jamais a tester
#     un champ absent,
#   - retirer les groupes sans item (pas de titre orphelin dans le panneau),
#   - ajouter a chaque groupe une "entete" prete a afficher ("EN RETARD · 1").
#
# EN ATTENDANT LE WORKFLOW N8N : URL vide -> on affiche exemples/a-venir.json
# (donnees fictives, signalees par "exemple" dans le resume de l'en-tete).

# >>> A COMPLETER : URL de PRODUCTION du webhook n8n "A VENIR" <<<
URL=""
EXEMPLE="$HOME/.config/eww/exemples/a-venir.json"

if [ -n "$URL" ]; then
  OUT="$(curl -s --netrc --max-time 8 "$URL")"
  SOURCE="n8n"
else
  OUT="$(cat "$EXEMPLE" 2>/dev/null)"
  SOURCE="exemple"
fi
[ -z "$OUT" ] && OUT='{}'

printf '%s' "$OUT" | python3 -c '
import sys, json, datetime

source = sys.argv[1]
maintenant = datetime.datetime.now().strftime("%H:%M")

def find_obj(x):
    """Localise l objet {"groupes": [...]} quelle que soit l enveloppe n8n."""
    if isinstance(x, list):
        return find_obj(x[0]) if len(x) == 1 else None
    if isinstance(x, dict):
        if isinstance(x.get("groupes"), list):
            return x
        for k in ("body", "data", "json"):
            if isinstance(x.get(k), (dict, list)):
                o = find_obj(x[k])
                if o is not None:
                    return o
    return None

try:
    raw = json.loads(sys.stdin.read() or "{}")
except Exception:
    raw = {}
obj = find_obj(raw)

if obj is None:
    # Webhook injoignable ou reponse inattendue : panneau vide, mais le
    # resume de l en-tete dit pourquoi.
    print(json.dumps({"synchro": maintenant, "resume": "n8n injoignable",
                      "groupes": []}, ensure_ascii=False))
    sys.exit(0)

groupes = []
for g in obj.get("groupes") or []:
    if not isinstance(g, dict):
        continue
    items = []
    for it in g.get("items") or []:
        if not isinstance(it, dict):
            continue
        items.append({"type":  "event" if it.get("type") == "event" else "tache",
                      "titre": str(it.get("titre") or "(sans titre)"),
                      "quand": str(it.get("quand") or "")})
    if not items:
        continue                       # groupe vide : pas de titre orphelin
    entete = str(g.get("libelle") or "")
    if g.get("date"):
        entete += " · " + str(g["date"])
    if g.get("compte") not in (None, ""):
        entete += " · " + str(g["compte"])
    groupes.append({"cle": str(g.get("cle") or ""), "entete": entete,
                    "items": items})

resume  = str(obj.get("resume") or "")
synchro = str(obj.get("synchro") or maintenant)
if source == "exemple":
    resume  = ("exemple · " + resume) if resume else "exemple"
    synchro = "exemple"
if not resume and not groupes:
    resume = "rien à venir"

print(json.dumps({"synchro": synchro, "resume": resume, "groupes": groupes},
                 ensure_ascii=False))
' "$SOURCE"
