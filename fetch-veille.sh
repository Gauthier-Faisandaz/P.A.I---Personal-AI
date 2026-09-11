#!/usr/bin/env bash
# fetch-veille.sh - panneau VEILLE : "qu'est-ce qui bouge dans mon domaine ?"
# (articles, newsletters...), DEJA selectionnes et commentes par n8n.
#
# Contrat (brief v9, section 5) - n8n renvoie, meme forme que les autres
# fichiers du bus :
#   { "synchro": "10:29",
#     "items": [ { "titre":    "Comparatif des orchestrateurs...",
#                  "source":   "newsletter",
#                  "age":      "3 h",
#                  "neuf":     true,
#                  "url":      "https://...",
#                  "pourquoi": "Recoupe directement ta pile n8n." } ] }
#
# La curation (quoi garder, combien, dans quel ordre, la phrase "pourquoi")
# est faite COTE N8N ; le panneau ne fait qu'afficher. Ce script se
# contente de :
#   - trouver ce JSON dans l'enveloppe n8n (comme les autres fetch-*.sh),
#   - completer les champs absents, pour que eww n'ait jamais a tester un
#     champ manquant,
#   - filtrer les url (voir url_sure plus bas : elles finiront dans une
#     commande shell a l'etape 6),
#   - donner a chaque item un "id" stable et construire l'index "by_id" que
#     lit la modale (comme fetch-digest.sh pour les mails),
#   - calculer le compteur de l'en-tete : "N à lire", ou "rien de neuf".
#
# EN ATTENDANT LE WORKFLOW N8N : URL vide -> on affiche exemples/veille.json
# (donnees fictives, signalees par "exemple" dans le resume de l'en-tete).

# >>> A COMPLETER : URL de PRODUCTION du webhook n8n "VEILLE" <<<
URL=""
# VEILLE_EXEMPLE permet de tester un autre fichier sans toucher a celui-ci :
#   VEILLE_EXEMPLE=/tmp/gros.json bash ~/.config/eww/sync.sh veille
EXEMPLE="${VEILLE_EXEMPLE:-$HOME/.config/eww/exemples/veille.json}"

if [ -n "$URL" ]; then
  OUT="$(curl -s --netrc --max-time 8 "$URL")"
  SOURCE="n8n"
else
  OUT="$(cat "$EXEMPLE" 2>/dev/null)"
  SOURCE="exemple"
fi
[ -z "$OUT" ] && OUT='{}'

printf '%s' "$OUT" | python3 -c '
import sys, json, datetime, hashlib

origine = sys.argv[1]                 # "n8n" ou "exemple"
maintenant = datetime.datetime.now().strftime("%H:%M")

def find_obj(x):
    """Localise l objet {"items": [...]} quelle que soit l enveloppe n8n."""
    if isinstance(x, list):
        return find_obj(x[0]) if len(x) == 1 else None
    if isinstance(x, dict):
        if isinstance(x.get("items"), list):
            return x
        for k in ("body", "data", "json"):
            if isinstance(x.get(k), (dict, list)):
                o = find_obj(x[k])
                if o is not None:
                    return o
    return None

def url_sure(u):
    """Seules les adresses web passent. Pourquoi : a l etape 6, le bouton
    "ouvrir la source" donne l url a xdg-open ENTRE APOSTROPHES, dans une
    commande shell. Or ces url viennent de contenus externes (newsletters,
    flux...) : une apostrophe dedans fermerait les guillemets et le shell
    executerait la suite. Elle est donc remplacee par son codage url (%27),
    que le navigateur comprend pareil. Espaces et caracteres de controle :
    url refusee. Tout ce qui n est pas http(s) (file://, javascript:...)
    aussi."""
    u = str(u or "").strip()
    if not u.lower().startswith(("https://", "http://")):
        return ""
    if any(c.isspace() or ord(c) < 32 for c in u):
        return ""
    return u.replace("\x27", "%27")

def truthy(v):
    return v in (True, "true", "True", 1, "1")

try:
    raw = json.loads(sys.stdin.read() or "{}")
except Exception:
    raw = {}
obj = find_obj(raw)

if obj is None:
    # Webhook injoignable, reponse inattendue ou fichier d exemple absent :
    # panneau vide, mais le resume de l en-tete dit pourquoi.
    raison = "exemple introuvable" if origine == "exemple" else "n8n injoignable"
    print(json.dumps({"synchro": maintenant, "resume": raison,
                      "items": [], "by_id": {}}, ensure_ascii=False))
    sys.exit(0)

items, by_id = [], {}
for k, it in enumerate(obj.get("items") or []):
    if not isinstance(it, dict):
        continue
    titre = str(it.get("titre") or "(sans titre)")
    url = url_sure(it.get("url"))
    # id STABLE, tire de l url (a defaut, du titre) et non de la position
    # dans la liste : si un article arrive en tete pendant que la modale est
    # ouverte, elle continue d afficher le MEME article. Hexadecimal : sans
    # danger dans la commande onclick de eww.yuck.
    ident = hashlib.sha1((url or titre).encode()).hexdigest()[:12]
    if ident in by_id:                    # meme article en double
        ident += "-" + str(k)
    src = str(it.get("source") or "")
    age = str(it.get("age") or "")
    x = {"id": ident, "titre": titre, "source": src, "age": age,
         "meta": " · ".join(p for p in (src, age) if p),   # "newsletter · 3 h"
         "neuf": truthy(it.get("neuf")), "url": url,
         "pourquoi": str(it.get("pourquoi") or "")}        # lu par la modale seule
    items.append(x)
    by_id[ident] = x

n = len(items)
resume = f"{n} à lire" if n else "rien de neuf"
synchro = str(obj.get("synchro") or maintenant)
if origine == "exemple":
    resume = "exemple · " + resume
    synchro = "exemple"

print(json.dumps({"synchro": synchro, "resume": resume, "items": items,
                  "by_id": by_id}, ensure_ascii=False))
' "$SOURCE" | bash "$HOME/.config/eww/publier.sh" veille   # copie dans le bus + recalcul des hauteurs
