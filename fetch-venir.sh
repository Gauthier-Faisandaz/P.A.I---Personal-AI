#!/usr/bin/env bash
# fetch-venir.sh - panneau A VENIR : evenements Google Agenda + taches
# Taskwarrior datees, sur 7 jours glissants (aujourd'hui + 6 jours).
#
# Repartition des roles (decision de Gauthier, 23/09) :
#   - n8n RASSEMBLE les evenements : son webhook renvoie les lignes BRUTES
#     de sa table agenda, sans rien calculer :
#       { "data": [ { "title": "Réunion SFP",
#                     "startDate": "2026-09-28T10:00:00+02:00",  (ou "2026-09-30" :
#                     "endDate":   "2026-09-28T11:00:00+02:00",   toute la journee)
#                     "status": "confirmed", ... } ] }
#     (les autres champs sont ignores).
#   - CE SCRIPT fait le reste, parce que tout depend de l'heure qu'il est ICI
#     et que Taskwarrior est sur cette machine : il lit les taches datees,
#     fusionne les deux sources, les range en groupes, calcule les libelles,
#     les echeances et le resume de l'en-tete.
#   - eww.yuck ne fait qu'afficher (sa forme de donnees n'a pas change).
#
# Groupes, dans cet ordre, les vides omis :
#   EN RETARD        taches dont le JOUR d'echeance est passe ("−2 j").
#                    Un evenement passe n'est jamais "en retard".
#   AUJOURD'HUI      evenements et taches du jour (heure, ou rien).
#   DEMAIN           idem, lendemain.
#   PROCHAINS JOURS  J+2 a J+6 ("lun. 10:00", ou "lun." sans heure).
# Tache SANS echeance : jamais ici, c'est le "vrac" (fetch-vrac.sh).
#
# Sortie (lue par eww.yuck et mise-en-page.py, inchangee) :
#   { "synchro": "09:55", "resume": "1 en retard · 2 aujourd'hui",
#     "groupes": [ { "cle": "retard", "entete": "EN RETARD · 1",
#                    "items": [ { "type": "tache" | "event",
#                                 "titre": "...", "quand": "−1 j" } ] } ] }
#
# Agenda injoignable : les taches s'affichent quand meme, et le resume le
# signale ("agenda injoignable · ...").
#
# Variables d'essai (sans toucher a ce fichier) :
#   VENIR_EXEMPLE=fichier     reponse du webhook lue dans ce fichier
#   VENIR_TACHES=fichier      "task export" lu dans ce fichier
#   VENIR_MAINTENANT=2026-09-10T09:00   fait comme s'il etait cette heure-la
# Exemple complet, avec les fichiers fournis :
#   VENIR_EXEMPLE=~/.config/eww/exemples/a-venir.json \
#   VENIR_TACHES=~/.config/eww/exemples/a-venir-taches.json \
#   VENIR_MAINTENANT=2026-09-10T09:00 bash ~/.config/eww/sync.sh venir
# (le prochain rafraichissement automatique, <= 30 min, remet les vraies
# donnees).

URL="https://n8n.power-of-automation.link/webhook/68231c0f-62ba-4474-914b-a6803084dd72"

if [ -n "$VENIR_EXEMPLE" ]; then
  OUT="$(cat "$VENIR_EXEMPLE" 2>/dev/null)"
else
  OUT="$(curl -s --netrc --max-time 8 "$URL")"
fi

printf '%s' "$OUT" | python3 -c '
import os, sys, json, subprocess, datetime as dt
sys.path.insert(0, os.path.expanduser("~/.config/eww"))
from nettoyer import propre    # sans emoji, espaces normalises

JOURS = ("lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim.")   # sans locale
FENETRE = 7                    # aujourd hui + 6 jours

m = os.environ.get("VENIR_MAINTENANT")
maintenant = dt.datetime.fromisoformat(m).astimezone() if m else dt.datetime.now().astimezone()
aujourdhui = maintenant.date()

def jour_court(d):
    return f"{JOURS[d.weekday()]} {d.day}"          # "mer. 23"

# ---------------------------------------------------------------- agenda
def trouver_liste(x):
    """La liste des evenements, quelle que soit l enveloppe n8n. None =
    reponse inattendue (webhook injoignable, erreur...)."""
    if isinstance(x, list):
        return x
    if isinstance(x, dict):
        for k in ("data", "body", "json", "items"):
            if k in x:
                return trouver_liste(x[k])
    return None

def lire_date(s):
    """(moment local, a_une_heure). "2026-09-30" = toute la journee."""
    s = str(s or "").strip()
    if not s:
        return None, False
    if "T" not in s:
        d = dt.date.fromisoformat(s[:10])
        return dt.datetime(d.year, d.month, d.day).astimezone(), False
    t = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
    return t.astimezone(), True

lignes = []    # (jour, a_une_heure, moment, type, titre)
try:
    brut = json.loads(sys.stdin.read() or "null")
except Exception:
    brut = None
evenements = trouver_liste(brut)
agenda_ok = evenements is not None

for e in evenements or []:
    if not isinstance(e, dict):
        continue
    try:
        debut, heure = lire_date(e.get("startDate"))
        fin, _ = lire_date(e.get("endDate"))
    except ValueError:
        continue                                    # date illisible : ignore
    if debut is None:
        continue
    jour = debut.date()
    if jour < aujourdhui:
        # Commence avant aujourd hui : on ne le garde que s il dure encore
        # (vacances sur plusieurs jours...), range dans AUJOURD HUI.
        if fin is None or fin < maintenant:
            continue
        jour, heure = aujourdhui, False
    lignes.append((jour, heure, debut, "event",
                   propre(e.get("title")) or "(sans titre)"))

# ---------------------------------------------------------- Taskwarrior
# Memes precautions que fetch-vrac.sh : une lecture ne doit JAMAIS modifier
# la base (gc, recurrence, hooks coupes).
def taches_brutes():
    f = os.environ.get("VENIR_TACHES")
    try:
        if f:
            with open(os.path.expanduser(f)) as h:
                return json.load(h)
        r = subprocess.run(
            ["task", "rc.verbose=nothing", "rc.gc=off", "rc.recurrence=off",
             "rc.hooks=off", "rc.confirmation=off",
             "status:pending", "-WAITING", "due.any:", "export"],
            capture_output=True, text=True, timeout=5)
        return json.loads(r.stdout or "[]")
    except Exception:
        return []                                   # Taskwarrior absent : agenda seul

for t in taches_brutes():
    if not isinstance(t, dict) or not t.get("due"):
        continue
    try:
        due = dt.datetime.strptime(t["due"], "%Y%m%dT%H%M%SZ") \
                .replace(tzinfo=dt.timezone.utc).astimezone()
    except ValueError:
        continue
    # "due:today" = minuit, "due:eod" = 23:59 : ce ne sont pas de vraies
    # heures, on n en affiche pas.
    heure = due.strftime("%H:%M") not in ("00:00", "23:59")
    lignes.append((due.date(), heure, due, "tache",
                   propre(t.get("description")) or "(sans titre)"))

# ------------------------------------------------------------ groupes
# En retard = le JOUR d echeance est passe, pas l heure : une tache "pour
# aujourd hui" reste dans AUJOURD HUI toute la journee (Taskwarrior, lui,
# la dirait deja en retard des minuit).
def groupe_de(jour, typ):
    ecart = (jour - aujourdhui).days
    if ecart < 0:
        return "retard" if typ == "tache" else None
    if ecart == 0: return "aujourdhui"
    if ecart == 1: return "demain"
    if ecart < FENETRE: return "semaine"
    return None                                     # au-dela de 7 jours

def quand(cle, jour, heure, moment):
    h = moment.strftime("%H:%M") if heure else ""
    if cle == "retard":
        return f"−{(aujourdhui - jour).days} j"      # "−2 j" (vrai signe moins)
    if cle == "semaine":
        return f"{JOURS[jour.weekday()]} {h}".strip()      # "lun. 10:00" / "lun."
    return h                                               # "14:00" / ""

rangees = {"retard": [], "aujourdhui": [], "demain": [], "semaine": []}
for jour, heure, moment, typ, titre in lignes:
    cle = groupe_de(jour, typ)
    if cle:
        rangees[cle].append((jour, heure, moment, typ, titre))

# Tri : par jour ; dans un jour, d abord ce qui n a pas d heure (journee
# entiere, taches), puis par heure.
for l in rangees.values():
    l.sort(key=lambda x: (x[0], x[1], x[2]))

demain = aujourdhui + dt.timedelta(days=1)
nb_retard, nb_jour = len(rangees["retard"]), len(rangees["aujourdhui"])
entetes = {
    "retard":     f"EN RETARD · {nb_retard}",
    "aujourdhui": f"AUJOURD\x27HUI · {jour_court(aujourdhui)}",
    "demain":     f"DEMAIN · {jour_court(demain)}",
    "semaine":    "PROCHAINS JOURS",
}
groupes = [{"cle": cle, "entete": entetes[cle],
            "items": [{"type": typ, "titre": titre,
                       "quand": quand(cle, jour, heure, moment)}
                      for jour, heure, moment, typ, titre in rangees[cle]]}
           for cle in ("retard", "aujourdhui", "demain", "semaine") if rangees[cle]]

# ------------------------------------------------------------- resume
morceaux = []
if nb_retard: morceaux.append(f"{nb_retard} en retard")
if nb_jour:   morceaux.append(f"{nb_jour} aujourd\x27hui")
if not morceaux:
    n = sum(len(g["items"]) for g in groupes)
    morceaux.append(f"{n} à venir" if n else "rien à venir")
if not agenda_ok:
    morceaux.insert(0, "agenda injoignable")

print(json.dumps({"synchro": maintenant.strftime("%H:%M"),
                  "resume": " · ".join(morceaux), "groupes": groupes},
                 ensure_ascii=False))
' | bash "$HOME/.config/eww/publier.sh" venir   # copie dans le bus + recalcul des hauteurs
