#!/usr/bin/env bash
# fetch-meteo.sh - meteo du panneau d'angle (HUD, nid d'abeille de 6
# hexagones). Lu par le "defpoll hud_meteo" de eww.yuck, toutes les 15 min.
#
# Source : Open-Meteo, appele DIRECTEMENT (gratuit, sans cle ni compte).
# Pourquoi pas via n8n comme les autres fetch-*.sh : le brief supposait un
# workflow n8n meteo, qui n'existe pas (constate le 14/09). Ce script fait
# donc lui-meme le travail qu'il lui confiait : traduction des codes meteo
# (WMO) en icone et libelle, arrondis, jours abreges en francais. Comme le
# bandeau, qui calcule deja CPU, RAM et reseau en local.
#
# Sortie (une ligne JSON) :
#   { "synchro": "10:29", "vieux": false,
#     "temp": 18, "ressenti": 17, "lieu": "Hantay",
#     "icone": "soleil" | "lune" | "nuage" | "pluie" | "neige",
#     "condition": "Peu nuageux",          (coupee en lignes de 11 caracteres)
#     "vent": "12 km/h", "humidite": "58 %",
#     "lever": "07:15", "coucher": "20:20",
#     "jours": [ { "jour": "mar.", "icone": "nuage", "max": 23, "min": 15 },
#                ... 3 jours ] }
#
# Lune (demande du 14/09) : la nuit, le soleil du ciel degage ou peu
# nuageux devient une lune. Open-Meteo dit s'il fait jour (is_day, ajoute a
# l'URL du brief). Seule l'icone du TEMPS ACTUEL est concernee : les trois
# jours de prevision sont des journees, ils gardent le soleil.
#
# Condition coupee en lignes courtes (11 caracteres max, aux espaces) pour
# qu'un libelle long tienne dans l'hexagone central (80 px) : le retour a la
# ligne automatique de GTK est peu fiable dans une boite de largeur fixe.
#
# Si Open-Meteo ne repond pas : on ressert la DERNIERE reponse valide
# (~/.cache/eww/bus/meteo.json), avec "vieux": true et son heure de synchro
# d'origine (brief : "laisser le synchro vieillir plutot qu'afficher un
# panneau vide"). S'il n'y en a aucune : "indisponible".
#
# Pour les essais uniquement (variables d'environnement) :
#   METEO_URL=file:///tmp/reponse.json   autre source au format Open-Meteo
#   METEO_DERNIER=/tmp/dernier.json      autre fichier de derniere reponse
#   METEO_EXEMPLE=exemples/meteo.json    fichier DEJA au format de sortie
#                                         (ex. "Averses orageuses"), sans appel

LAT=50.5337          # Hantay
LON=2.8673
URL="${METEO_URL:-https://api.open-meteo.com/v1/forecast?latitude=$LAT&longitude=$LON&current=temperature_2m,relative_humidity_2m,apparent_temperature,wind_speed_10m,weather_code,is_day&daily=temperature_2m_max,temperature_2m_min,sunrise,sunset,weather_code&timezone=Europe/Paris&forecast_days=4}"
DERNIER="${METEO_DERNIER:-$HOME/.cache/eww/bus/meteo.json}"

if [ -n "$METEO_EXEMPLE" ]; then
  OUT="$(cat "$METEO_EXEMPLE" 2>/dev/null)"
  SOURCE="exemple"
else
  OUT="$(curl -s --max-time 10 "$URL")"
  SOURCE="open-meteo"
fi
[ -z "$OUT" ] && OUT='{}'

printf '%s' "$OUT" | python3 -c '
import sys, json, os, math, tempfile, datetime

source, dernier = sys.argv[1], sys.argv[2]
ICONES = ("soleil", "lune", "nuage", "pluie", "neige")
JOURS = ("lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim.")

# Table des codes meteo WMO (brief, section 4) : code -> (icone, libelle).
WMO = {0: ("soleil", "Ciel dégagé")}
WMO.update({c: ("soleil", "Peu nuageux") for c in (1, 2)})
WMO.update({3: ("nuage", "Couvert"), 45: ("nuage", "Brouillard"), 48: ("nuage", "Brouillard")})
WMO.update({c: ("pluie", "Bruine") for c in (51, 53, 55, 56, 57)})
WMO.update({c: ("pluie", "Pluie") for c in (61, 63, 65, 66, 67)})
WMO.update({c: ("pluie", "Averses") for c in (80, 81, 82)})
WMO.update({c: ("neige", "Neige") for c in (71, 73, 75, 77, 85, 86)})
WMO.update({c: ("pluie", "Orage") for c in (95, 96, 99)})

def entier(v):
    """Arrondi a l entier le plus proche (17,5 -> 18, et non 18 ou 17 selon
    la parite comme le round() de Python)."""
    try:
        return int(math.floor(float(v) + 0.5))
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

def depuis_open_meteo(r):
    """Reponse Open-Meteo -> sortie. None si elle est inutilisable."""
    cur, jour = r.get("current") or {}, r.get("daily") or {}
    if entier(cur.get("temperature_2m")) is None:
        return None
    ic, lib = WMO.get(entier(cur.get("weather_code")), ("nuage", ""))
    if ic == "soleil" and entier(cur.get("is_day")) == 0:
        ic = "lune"                           # la nuit : lune a la place du soleil
    jours = []
    for i in (1, 2, 3):                       # indice 0 = aujourd hui
        try:
            date = datetime.date.fromisoformat(jour["time"][i])
            jours.append({"jour": JOURS[date.weekday()],
                          "icone": WMO.get(entier(jour["weather_code"][i]), ("nuage", ""))[0],
                          "max": entier(jour["temperature_2m_max"][i]),
                          "min": entier(jour["temperature_2m_min"][i])})
        except (KeyError, IndexError, TypeError, ValueError):
            break
    heure = lambda cle: str((jour.get(cle) or [""])[0])[11:16]     # "2026-09-14T07:22" -> "07:22"
    vent, humidite = entier(cur.get("wind_speed_10m")), entier(cur.get("relative_humidity_2m"))
    return {"synchro": datetime.datetime.now().strftime("%H:%M"), "vieux": False,
            "temp": entier(cur.get("temperature_2m")),
            "ressenti": entier(cur.get("apparent_temperature")),
            "lieu": "Hantay", "icone": ic, "condition": coupe(lib),
            "vent": f"{vent} km/h" if vent is not None else "",
            "humidite": f"{humidite} %" if humidite is not None else "",
            "lever": heure("sunrise"), "coucher": heure("sunset"),
            "jours": jours}

def depuis_exemple(o):
    """Fichier deja au format de sortie (essais) : on le complete et on coupe."""
    return {"synchro": "exemple", "vieux": False,
            "temp": entier(o.get("temp")), "ressenti": entier(o.get("ressenti")),
            "lieu": str(o.get("lieu") or "Hantay"), "icone": icone(o.get("icone")),
            "condition": coupe(str(o.get("condition") or "")),
            "vent": str(o.get("vent") or ""), "humidite": str(o.get("humidite") or ""),
            "lever": str(o.get("lever") or ""), "coucher": str(o.get("coucher") or ""),
            "jours": [{"jour": str(j.get("jour") or ""), "icone": icone(j.get("icone")),
                       "max": entier(j.get("max")), "min": entier(j.get("min"))}
                      for j in (o.get("jours") or [])[:3] if isinstance(j, dict)]}

try:
    brut = json.loads(sys.stdin.read() or "{}")
except Exception:
    brut = {}

if source == "exemple":
    print(json.dumps(depuis_exemple(brut if isinstance(brut, dict) else {}), ensure_ascii=False))
    sys.exit(0)

sortie = depuis_open_meteo(brut) if isinstance(brut, dict) else None
if sortie is not None:
    # Reponse fraiche : on la garde (fichier temporaire puis renommage :
    # jamais un fichier a moitie ecrit).
    os.makedirs(os.path.dirname(dernier), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(dernier), prefix=".meteo.")
    with os.fdopen(fd, "w") as f:
        json.dump(sortie, f, ensure_ascii=False)
    os.replace(tmp, dernier)
else:
    # Open-Meteo injoignable ou reponse inattendue : derniere reponse valide.
    try:
        with open(dernier) as f:
            sortie = json.load(f)
        sortie["vieux"] = True
    except Exception:
        sortie = {"synchro": "", "vieux": True, "temp": None, "ressenti": None,
                  "lieu": "Hantay", "icone": "nuage", "condition": "indisponible",
                  "vent": "", "humidite": "", "lever": "", "coucher": "", "jours": []}

print(json.dumps(sortie, ensure_ascii=False))
' "$SOURCE" "$DERNIER"
