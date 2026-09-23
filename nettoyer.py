"""nettoyer.py - nettoyage des textes AFFICHES dans les panneaux, commun a
tous les fetch-*.sh (fonction propre).

Pourquoi ici et pas dans n8n : c'est une contrainte de l'ECRAN, pas de la
donnee. n8n envoie le texte tel quel (il peut servir ailleurs, ou les
emojis sont bienvenus) ; le script local l'adapte a la colonne. Et pas dans
eww.yuck : le yuck affiche, il ne transforme pas.

Deux regles :
  1. Pas d'emoji. La couleur est reservee au sens (urgent, retard) : un
     emoji apporte la sienne (Noto Color Emoji) ou un dessin d'un autre
     style (Symbola) et attire l'oeil sans rien dire d'urgent. Les signes
     du dashboard (! ► ☐ ▪ ●) ne sont pas concernes : c'est eww.yuck qui les
     ajoute, ils ne passent jamais par ici.
  2. Espaces : un seul espace entre deux mots, aucun au debut ni a la fin,
     pas de retour a la ligne dans un titre. Les espaces INSECABLES de la
     typographie francaise (avant « : » ou « ? ») sont gardes.

Ne touche pas aux accents, ni a la ponctuation (« » — · …), ni aux fleches
(→).

Usage dans le python d'un fetch-*.sh :
    import os, sys
    sys.path.insert(0, os.path.expanduser("~/.config/eww"))
    from nettoyer import propre
    titre = propre(it.get("titre")) or "(sans titre)"
"""
import re

# Plages Unicode des pictogrammes (emojis), et les caracteres invisibles qui
# les composent : 200D (colle deux emojis en un), FE0E/FE0F (choix texte /
# couleur), 20E3 (touche "1️⃣"), E0020-E007F (drapeaux de regions).
_EMOJI = re.compile(
    "["
    "\U0001F000-\U0001FAFF"   # emoticones, pictogrammes, transports, drapeaux,
                              # teintes de peau, symboles supplementaires
    "☀-➿"           # symboles divers (☀ ☎ ⚠ ★) et dingbats (✅ ✈ ❤)
    "⬀-⯿"           # ⭐ ⬛ ⬆ ...
    "⌚⌛⌨⏏⏩-⏳⏸-⏺"   # ⌚ ⏰ ⏳ ...
    "‍︎️⃣"
    "\U000E0020-\U000E007F"
    "]+"
)

# Tout blanc SAUF les espaces insecables (00A0, 202F) : [^\S...] = "un blanc
# qui n'est pas l'un de ceux-la".
_BLANCS = re.compile("[^\\S  ]+")


def propre(texte):
    """Texte pret a afficher : sans emoji, espaces normalises. None -> ""."""
    if texte is None:
        return ""
    t = _EMOJI.sub(" ", str(texte))       # " " et non "" : "a🚀b" -> "a b"
    return _BLANCS.sub(" ", t).strip()
