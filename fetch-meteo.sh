#!/usr/bin/env bash
# fetch-meteo.sh - meteo du panneau d'angle (HUD, nid d'abeille de 6
# hexagones). Lu par le "defpoll hud_meteo" de eww.yuck, toutes les 15 min.
#
# Contrat (brief du panneau d'angle, section 4) - n8n renvoie :
#   { "synchro": "10:29",
#     "temp": 18, "ressenti": 17, "lieu": "Hantay",
#     "icone": "soleil" | "nuage" | "pluie" | "neige",
#     "condition": "Peu nuageux",
#     "vent": "12 km/h", "humidite": "58 %",
#     "lever": "07:15", "coucher": "20:20",
#     "jours": [ { "jour": "mar.", "icone": "nuage", "max": 23, "min": 15 },
#                ... 3 jours ] }
#
# Tout le travail (appel a Open-Meteo, table des codes WMO -> icone et
# libelle, arrondis) est fait COTE N8N : "collecteur bete, processeur
# intelligent". Ce script se contente, comme les autres fetch-*.sh, de :
#   - trouver ce JSON dans l'enveloppe n8n,
#   - completer les champs manquants, pour que eww n'ait jamais a tester un
#     champ absent (icone inconnue -> "nuage"),
#   - couper la condition en lignes courtes (11 caracteres max, aux espaces)
#     pour qu'un libelle long comme "Averses orageuses" tienne dans
#     l'hexagone central (80 px) : le retour a la ligne automatique de GTK
#     est peu fiable dans une boite de largeur fixe.
#
# Si n8n est injoignable : on garde la DERNIERE reponse valide (brief : "garder
# le dernier fichier et laisser le synchro vieillir plutot qu'afficher un
# panneau vide"). Elle est conservee dans ~/.cache/eww/bus/meteo.json.
#
# EN ATTENDANT LE WORKFLOW N8N : URL vide -> on affiche exemples/meteo.json
# (donnees fictives ; "synchro" vaut alors "exemple").

# >>> A COMPLETER : URL de PRODUCTION du webhook n8n "METEO" <<<
URL=""
# METEO_EXEMPLE permet de tester un autre fichier sans toucher a celui-ci :
#   METEO_EXEMPLE=/tmp/orage.json bash ~/.config/eww/fetch-meteo.sh
EXEMPLE="${METEO_EXEMPLE:-$HOME/.config/eww/exemples/meteo.json}"
DERNIER="$HOME/.cache/eww/bus/meteo.json"

if [ -n "$URL" ]; then
  OUT="$(curl -s --netrc --max-time 8 "$URL")"
  SOURCE="n8n"
else
  OUT="$(cat "$EXEMPLE" 2>/dev/null)"
  SOURCE="exemple"
fi
[ -z "$OUT" ] && OUT='{}'

printf '%s' "$OUT" | python3 -c '
import sys, json, os, tempfile

source, dernier = sys.argv[1], sys.argv[2]
ICONES = ("soleil", "nuage", "pluie", "neige")

def find_obj(x):
    """Localise l objet meteo (celui qui a "temp") quelle que soit l enveloppe n8n."""
    if isinstance(x, list):
        return find_obj(x[0]) if len(x) == 1 else None
    if isinstance(x, dict):
        if "temp" in x:
            return x
        for k in ("body", "data", "json"):
            if isinstance(x.get(k), (dict, list)):
                o = find_obj(x[k])
                if o is not None:
                    return o
    return None

def entier(v):
    try:
        return round(float(v))
    except (TypeError, ValueError):
        return None

def coupe(texte, n=11, lignes_max=2):
    """Coupe aux espaces en lignes de n caracteres au plus (2 lignes au plus)."""
    lignes = []
    for mot in texte.split():
        if lignes and len(lignes[-1]) + 1 + len(mot) <= n:
            lignes[-1] += " " + mot
        else:
            lignes.append(mot)
    if len(lignes) > lignes_max:
        lignes = lignes[:lignes_max]
        lignes[-1] = lignes[-1][:n - 1] + "…"
    return "\n".join(lignes)

def icone(v):
    return v if v in ICONES else "nuage"

try:
    raw = json.loads(sys.stdin.read() or "{}")
except Exception:
    raw = {}
obj = find_obj(raw)

vieux = False
if obj is None:
    # n8n injoignable ou reponse inattendue : derniere reponse valide.
    try:
        with open(dernier) as f:
            obj = json.load(f)
        vieux = True
    except Exception:
        obj = {"condition": "indisponible"}

jours = []
for j in (obj.get("jours") or [])[:3]:
    if isinstance(j, dict):
        jours.append({"jour": str(j.get("jour") or ""), "icone": icone(j.get("icone")),
                      "max": entier(j.get("max")), "min": entier(j.get("min"))})

sortie = {"synchro":   "exemple" if source == "exemple" else str(obj.get("synchro") or ""),
          "vieux":     vieux,
          "temp":      entier(obj.get("temp")),
          "ressenti":  entier(obj.get("ressenti")),
          "lieu":      str(obj.get("lieu") or "Hantay"),
          "icone":     icone(obj.get("icone")),
          "condition": coupe(str(obj.get("condition") or "")),
          "vent":      str(obj.get("vent") or ""),
          "humidite":  str(obj.get("humidite") or ""),
          "lever":     str(obj.get("lever") or ""),
          "coucher":   str(obj.get("coucher") or ""),
          "jours":     jours}

# Reponse fraiche de n8n : on la garde (ecriture dans un fichier temporaire
# puis renommage : jamais un fichier a moitie ecrit).
if source == "n8n" and not vieux and sortie["temp"] is not None:
    os.makedirs(os.path.dirname(dernier), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(dernier), prefix=".meteo.")
    with os.fdopen(fd, "w") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(tmp, dernier)

print(json.dumps(sortie, ensure_ascii=False))
' "$SOURCE" "$DERNIER"
