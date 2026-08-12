#!/usr/bin/env bash
# Recupere les "recommandations du jour" (JSON) depuis n8n via auth Basic (~/.netrc).
# Localise la liste des recommandations quelle que soit l'enveloppe n8n
# (objet, tableau [{...}], ou body/data/json), normalise chaque item vers
# { titre, detail, priorite } et ajoute une heure de synchro locale.
# Repli sur {"recommandations":[]} si injoignable.

# ⚠️  A PERSONNALISER : mettez ici l'URL de PRODUCTION de votre webhook n8n "recos"
#     (workflow active + chemin /webhook/ , pas /webhook-test/).
URL="https://n8n.power-of-automation.link/webhook/393ba0e4-916c-4e30-a364-4de9865a7a46"

OUT="$(curl -s --netrc --max-time 8 "$URL")"
[ -z "$OUT" ] && OUT='{}'

printf '%s' "$OUT" | python3 -c '
import sys, json, datetime

def find_list(x):
    """Localise la liste des recommandations dans nimporte quelle enveloppe."""
    if isinstance(x, list):
        # cas [{"recommandations":[...]}] : on descend dans lunique element
        if len(x) == 1 and isinstance(x[0], dict) and any(
            isinstance(x[0].get(k), list)
            for k in ("recommandations", "recos", "items", "data", "body")):
            return find_list(x[0])
        return [e for e in x if e is not None]
    if isinstance(x, dict):
        for k in ("recommandations", "recos", "items", "data", "body", "json"):
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
        return {"titre": str(e), "detail": "", "priorite": "basse"}
    titre  = e.get("titre")  or e.get("title") or e.get("nom")  or e.get("name") or ""
    detail = e.get("detail") or e.get("description") or e.get("text") or e.get("raison") or ""
    prio   = str(e.get("priorite") or e.get("priority") or e.get("prio") or "basse").lower()
    return {"titre": titre, "detail": detail, "priorite": PRIO.get(prio, "basse")}

try:
    raw = json.load(sys.stdin)
except Exception:
    raw = {}

items = [norm(e) for e in find_list(raw)]
out = {"recommandations": items,
       "sync": datetime.datetime.now().strftime("%H:%M")}
print(json.dumps(out, ensure_ascii=False))
'
