#!/usr/bin/env bash
# Recupere les "recommandations du jour" (JSON) depuis n8n via auth Basic (~/.netrc).
# Localise la liste des recommandations quelle que soit l'enveloppe n8n
# (objet, tableau [{...}], ou body/data/json), normalise chaque item vers
# { titre, detail, priorite } et ajoute une heure de synchro locale.
# Repli sur {"recommandations":[]} si injoignable.
# Accepte aussi le format cible du brief (09/2026) :
#   { "actions": [ {rang, titre, contexte, urgent} ] }
# (Le champ "synthese" qu'attendait l'etat semi-ouvert de l'accordeon n'est
# plus lu depuis l'etape 0 de la colonne elastique : inutile de le produire
# cote n8n.)

# ⚠️  A PERSONNALISER : mettez ici l'URL de PRODUCTION de votre webhook n8n "recos"
#     (workflow active + chemin /webhook/ , pas /webhook-test/).
URL="https://n8n.power-of-automation.link/webhook/393ba0e4-916c-4e30-a364-4de9865a7a46"

OUT="$(curl -s --netrc --max-time 8 "$URL")"
[ -z "$OUT" ] && OUT='{}'

printf '%s' "$OUT" | python3 -c '
import sys, json, datetime
import os
sys.path.insert(0, os.path.expanduser("~/.config/eww"))
from nettoyer import propre    # sans emoji, espaces normalises

def find_list(x):
    """Localise la liste des recommandations dans nimporte quelle enveloppe."""
    if isinstance(x, list):
        # cas [{"recommandations":[...]}] : on descend dans lunique element
        if len(x) == 1 and isinstance(x[0], dict) and any(
            isinstance(x[0].get(k), list)
            for k in ("recommandations", "recos", "actions", "items", "data", "body")):
            return find_list(x[0])
        return [e for e in x if e is not None]
    if isinstance(x, dict):
        for k in ("recommandations", "recos", "actions", "items", "data", "body", "json"):
            if isinstance(x.get(k), list):
                return find_list(x[k])
        for k in ("body", "data", "json"):
            if isinstance(x.get(k), dict):
                return find_list(x[k])
    return []

PRIO = {"high": "haute", "medium": "moyenne", "low": "basse",
        "1": "haute", "2": "moyenne", "3": "basse",
        "haute": "haute", "moyenne": "moyenne", "basse": "basse"}

def norm(e):
    if not isinstance(e, dict):
        return {"titre": propre(e), "detail": "", "priorite": "basse"}
    titre  = e.get("titre")  or e.get("title") or e.get("nom")  or e.get("name") or ""
    detail = (e.get("detail") or e.get("description") or e.get("text") or e.get("raison")
              or e.get("contexte") or "")
    prio   = str(e.get("priorite") or e.get("priority") or e.get("prio") or "basse").lower()
    if e.get("urgent") in (True, "true", 1):   # format cible du brief
        prio = "haute"
    return {"titre": propre(titre), "detail": propre(detail), "priorite": PRIO.get(prio, "basse")}

try:
    raw = json.load(sys.stdin)
except Exception:
    raw = {}

items = [norm(e) for e in find_list(raw)]
# resume = texte affiche tel quel dans l en-tete du panneau (replie ou non).
# Calcule ici plutot que dans eww.yuck : eww reste un rendu bete.
n = len(items)
if n == 0:   resume = "aucune action"
elif n == 1: resume = "1 action"
else:        resume = f"{n} actions"
out = {"recommandations": items,
       "resume": resume,
       "sync": datetime.datetime.now().strftime("%H:%M")}
print(json.dumps(out, ensure_ascii=False))
' | bash "$HOME/.config/eww/publier.sh" recos   # copie dans le bus + recalcul des hauteurs
