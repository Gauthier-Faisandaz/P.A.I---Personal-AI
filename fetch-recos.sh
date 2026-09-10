#!/usr/bin/env bash
# Recupere les "recommandations du jour" (JSON) depuis n8n via auth Basic (~/.netrc).
# Localise la liste des recommandations quelle que soit l'enveloppe n8n
# (objet, tableau [{...}], ou body/data/json), normalise chaque item vers
# { titre, detail, priorite } et ajoute une heure de synchro locale.
# Repli sur {"recommandations":[]} si injoignable.
# Accepte aussi le format cible du brief (09/2026) :
#   { "synthese": "...", "actions": [ {rang, titre, contexte, urgent} ] }
# "synthese" = la priorite du jour en UNE phrase, ecrite par le LLM cote n8n
# (pas tronquee ici : une troncature couperait au milieu d'un mot). Tant que
# n8n ne la fournit pas, repli sur le titre de la recommandation n°1.

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

def find_text(x, key):
    """Cherche un champ texte (ex: synthese) dans la meme enveloppe n8n."""
    if isinstance(x, list):
        return find_text(x[0], key) if len(x) == 1 else ""
    if isinstance(x, dict):
        if isinstance(x.get(key), str):
            return x[key].strip()
        for k in ("body", "data", "json"):
            if isinstance(x.get(k), (dict, list)):
                v = find_text(x[k], key)
                if v:
                    return v
    return ""

PRIO = {"high": "haute", "medium": "moyenne", "low": "basse",
        "1": "haute", "2": "moyenne", "3": "basse",
        "haute": "haute", "moyenne": "moyenne", "basse": "basse"}

def norm(e):
    if not isinstance(e, dict):
        return {"titre": str(e), "detail": "", "priorite": "basse"}
    titre  = e.get("titre")  or e.get("title") or e.get("nom")  or e.get("name") or ""
    detail = (e.get("detail") or e.get("description") or e.get("text") or e.get("raison")
              or e.get("contexte") or "")
    prio   = str(e.get("priorite") or e.get("priority") or e.get("prio") or "basse").lower()
    if e.get("urgent") in (True, "true", 1):   # format cible du brief
        prio = "haute"
    return {"titre": titre, "detail": detail, "priorite": PRIO.get(prio, "basse")}

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
# synthese = ligne affichee sous l en-tete quand le panneau est replie
# ("semi-ouvert"). Jamais vide : le panneau ne doit jamais tenir sur une
# seule ligne.
synthese = (find_text(raw, "synthese")
            or (items[0]["titre"] if items else "")
            or "Aucune recommandation pour le moment.")
out = {"recommandations": items,
       "resume": resume,
       "synthese": synthese,
       "sync": datetime.datetime.now().strftime("%H:%M")}
print(json.dumps(out, ensure_ascii=False))
'
