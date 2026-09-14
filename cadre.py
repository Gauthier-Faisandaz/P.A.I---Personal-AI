#!/usr/bin/env python3
"""
cadre.py - geometrie du panneau d'angle (HUD) : une colonne d'hexagones le
long du bord gauche de l'ecran, et les cadres SVG qui la dessinent.

Source UNIQUE de la geometrie : eww.yuck en recopie les nombres (section
PANNEAU D'ANGLE), decoupe-hud.py en tire la forme X Shape de chaque fenetre,
et "python3 cadre.py verifier" controle que tout concorde.

Disposition (croquis de Gauthier du 14/09, 60 % de la hauteur de l'ecran),
tout empile verticalement, hexagones reguliers "pointe en haut" :
  - heure      : un grand hexagone, rogne par le haut et la gauche de l'ecran ;
  - meteo      : un nid d'abeille de 6 hexagones egaux (centre, haut-gauche,
                 haut-droit, droit, bas-droit, bas-gauche), qui ne forment
                 qu'une seule piece ; ceux de gauche sont rognes par l'ecran ;
  - sparklines : 3 hexagones empiles.
Aucune decoration pour l'instant (demande du 14/09) : verre + contour.

REGLE IMPOSEE PAR PICOM (bogue de picom 10.2, moteur glx, constate le
14/09) : sur une fenetre decoupee, picom ne floute un pixel (x, y) que si
son symetrique haut/bas (x, H - y) est AUSSI dans la forme (H = hauteur de
la fenetre). Chaque fenetre doit donc etre symetrique par rapport a son axe
horizontal, sinon des morceaux du verre restent nets. D'ou :
  - une fenetre par piece (l'ensemble n'est pas symetrique, chaque piece l'est) ;
  - l'heure n'est pas "coupee" par le haut de l'ecran : l'hexagone est
    ENTIER dans sa fenetre, et c'est la fenetre qui commence au-dessus de
    l'ecran (y negatif, accepte par eww et Openbox : teste le 14/09) ;
  - les coupes a GAUCHE, elles, sont sans danger (une coupe verticale ne
    casse pas la symetrie haut/bas) : les fenetres commencent en x >= 0.
    Surtout pas x < 0 : a gauche de l'ecran HDMI se trouve l'ecran du
    portable (il commence en y = 321), la fenetre y deborderait.
"python3 cadre.py verifier" controle cette symetrie.

BORDS LISSES : la forme X Shape est binaire (un pixel est dedans ou dehors),
un bord oblique y devient donc un escalier. Si elle coupe le trait du
contour, le trait devient un escalier lui aussi (constate le 14/09). D'ou :
  - la forme X Shape est un peu PLUS GRANDE que l'hexagone dessine (rayon
    R + DILATATION, soit ~1,7 px de plus de chaque cote) ;
  - le contour est dessine en entier, lisse (librsvg l'adoucit), a
    l'interieur de cette forme : l'escalier tombe a l'exterieur du trait,
    dans le vide, ou il ne se voit presque plus ;
  - chaque fenetre a une MARGE de vide autour de ses hexagones pour contenir
    tout ca -- sauf au bord gauche de l'ecran, ou l'on coupe net (une coupe
    verticale ne fait pas d'escalier, et x < 0 est interdit, voir plus haut).

Couleurs (tokens de eww.scss, identiques a la colonne de droite) :
    verre    rgba(255,255,255,.10)   = .panel background-color
    contour  rgba(255,255,255,.25)   = .panel border (demande du 14/09 : meme
                                     trait que la colonne ; 1,4 px et non 1 px,
                                     car un trait oblique lisse sur 1 px parait
                                     plus pale qu'une bordure droite)

ATTENTION : ce fichier genere du SVG consomme par librsvg. Rester en ASCII
dans les chaines produites (les commentaires Python n'y vont pas).

Usage :
    python3 cadre.py heure        > hud/heure.svg
    python3 cadre.py meteo        > hud/meteo.svg
    python3 cadre.py sparklines   > hud/sparklines.svg
    python3 cadre.py decoupe                   # polygones X Shape (repere de chaque fenetre)
    python3 cadre.py geometrie                 # les lignes a recopier dans eww.yuck
    python3 cadre.py verifier [eww.yuck]       # eww.yuck a jour ? fenetres symetriques ?
(generer-cadres.sh fait les SVG et la verification d'un coup.)
"""
import math
import os
import re
import sys

VERRE   = 'rgba(255,255,255,.10)'
CONTOUR = 'rgba(255,255,255,.25)'
TRAIT = 1.4          # epaisseur du contour (px), trait entier et lisse
MARGE = 3            # vide autour des hexagones dans leur fenetre (px)
DILATATION = 2       # forme X Shape = hexagones de rayon R + 2 (~1,7 px de plus)

S3 = math.sqrt(3) / 2

def hexa(cx, cy, R):
    """Hexagone regulier "pointe en haut", de rayon R (centre -> sommet).
    R pair et decalages arrondis AVANT d'ajouter le centre : les sommets
    tombent sur des pixels entiers, deux cellules voisines partagent
    exactement leurs sommets, et la symetrie haut/bas est exacte."""
    assert R % 2 == 0, 'R doit etre pair'
    a, b = round(S3 * R), R // 2
    return [(cx, cy - R), (cx + a, cy - b), (cx + a, cy + b),
            (cx, cy + R), (cx - a, cy + b), (cx - a, cy - b)]

# ---------------------------------------------------------------- geometrie
# Chaque piece = une fenetre eww, nommee "hud-<piece>".
# cellules : (cx, cy, R) = centre et rayon de chaque hexagone, en px, dans le
# repere de l'ECRAN du dashboard (1920 x 1080 ; y < 0 = au-dessus de l'ecran).
# La fenetre de chaque piece en est deduite (fenetre_de) : rien a recopier.
# Axe commun : toutes les pieces sont centrees sur x = 52.

# Meteo : cellules de rayon 38 (66 x 76 px). Dans un nid d'abeille "pointe en
# haut", les voisins sont a (+-2a, 0) et (+-a, +-3b) du centre.
RM = 38
AM, BM = round(S3 * RM), RM // 2     # 33, 19
MX, MY = 52, 249                     # centre du nid

PIECES = {
    # Heure : rayon 88 (152 x 176 px), centre (52, 56) : l'hexagone depasse
    # de 32 px au-dessus de l'ecran et de 24 px a gauche.
    'heure': {'cellules': [(52, 56, 88)]},
    'meteo': {'cellules': [(MX,          MY,          RM),     # centre
                           (MX + AM,     MY - 3 * BM, RM),     # haut-droit
                           (MX + 2 * AM, MY,          RM),     # droit
                           (MX + AM,     MY + 3 * BM, RM),     # bas-droit
                           (MX - AM,     MY + 3 * BM, RM),     # bas-gauche (a moitie rogne)
                           (MX - AM,     MY - 3 * BM, RM)]},   # haut-gauche (a moitie rogne)
    # Sparklines : rayon 46 (80 x 92 px), empilees, 9 px entre deux.
    'sparklines': {'cellules': [(52, 401, 46), (52, 502, 46), (52, 603, 46)]},
}

def fenetre_de(cellules):
    """Rectangle (x, y, largeur, hauteur) de la fenetre : les hexagones plus
    MARGE de chaque cote, sauf a gauche de l'ecran (x jamais < 0)."""
    gauche = min(cx - round(S3 * R) for cx, cy, R in cellules)
    droite = max(cx + round(S3 * R) for cx, cy, R in cellules)
    haut   = min(cy - R for cx, cy, R in cellules)
    bas    = max(cy + R for cx, cy, R in cellules)
    x0, y0 = max(0, gauche - MARGE), haut - MARGE
    return (x0, y0, droite + MARGE - x0, bas + MARGE - y0)

for _p in PIECES.values():
    _p['fenetre'] = fenetre_de(_p['cellules'])

def fenetre_eww(piece):
    """Nom de la fenetre eww (defwindow) de la piece ; son titre X est
    "Eww - " + ce nom (verifie avec xprop)."""
    return 'hud-' + piece

def cellules_locales(piece):
    """Les cellules dans le repere de leur FENETRE."""
    x0, y0 = PIECES[piece]['fenetre'][:2]
    return [(cx - x0, cy - y0, R) for cx, cy, R in PIECES[piece]['cellules']]

def decoupe(piece):
    """Polygones de la forme X Shape de la fenetre (repere de la fenetre) :
    les hexagones agrandis de DILATATION (voir BORDS LISSES en tete). Leur
    union est la seule zone affichee, et floutee, par picom."""
    return [hexa(cx, cy, R + DILATATION) for cx, cy, R in cellules_locales(piece)]

def symetrique(piece):
    """La regle de picom (voir en tete) : chaque cellule a-t-elle sa jumelle
    symetrique haut/bas dans la fenetre ? (Un hexagone "pointe en haut" est
    lui-meme symetrique : il suffit de comparer les centres.)"""
    h = PIECES[piece]['fenetre'][3]
    cellules = set(cellules_locales(piece))
    return cellules == {(cx, h - cy, R) for cx, cy, R in cellules}

# ---------------------------------------------------------------- SVG

def chemin(polygones):
    return ' '.join('M' + ' L'.join(f'{x},{y}' for x, y in p) + ' Z' for p in polygones)

def aretes_contour(piece):
    """Bord exterieur de la piece : les aretes des hexagones, sauf celles que
    partagent deux cellules voisines (interieures : pas de trait entre elles)."""
    compte = {}
    for cx, cy, R in cellules_locales(piece):
        p = hexa(cx, cy, R)
        for i in range(6):
            cle = frozenset((p[i], p[(i + 1) % 6]))
            compte[cle] = compte.get(cle, 0) + 1
    return [tuple(sorted(cle)) for cle, n in compte.items() if n == 1]

def svg_piece(piece):
    """Cadre d'une piece, a la taille de sa fenetre : verre sur les hexagones
    (taille reelle, pas agrandie), puis le contour, trait entier et lisse."""
    _, _, W, H = PIECES[piece]['fenetre']
    cellules = [hexa(cx, cy, R) for cx, cy, R in cellules_locales(piece)]
    traits = ' '.join(f'M{a[0]},{a[1]} L{b[0]},{b[1]}' for a, b in aretes_contour(piece))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            f'<path d="{chemin(cellules)}" fill="{VERRE}"/>'
            f'<path d="{traits}" fill="none" stroke="{CONTOUR}" stroke-width="{TRAIT}" '
            f'stroke-linecap="round" stroke-linejoin="round"/>'
            f'</svg>\n')

# ---------------------------------------------------------------- eww.yuck

def afficher_geometrie():
    """Les lignes a recopier dans eww.yuck, dans la forme exacte attendue."""
    for piece, p in PIECES.items():
        x, y, w, h = p['fenetre']
        print(f';; (defwindow {fenetre_eww(piece)} ...)')
        print(f'  :geometry (geometry :x "{x}px" :y "{y}px" :width "{w}px" :height "{h}px" :anchor "top left")')
        print(f'  (hud_piece :nom "{piece}" :w {w} :h {h}))')
        print()

def verifier(chemin_yuck):
    """Compare les nombres recopies dans eww.yuck a ceux de ce fichier, et
    controle la symetrie de chaque fenetre. Renvoie le code de sortie (0 ou 1)."""
    with open(chemin_yuck, encoding='utf-8') as f:
        # On ignore les lignes de commentaire (;;) : elles peuvent citer des
        # exemples qui ne sont pas le vrai code.
        texte = '\n'.join(l for l in f.read().splitlines()
                          if not l.lstrip().startswith(';'))
    erreurs = 0
    # L'ancienne fenetre unique (12/09) ne doit plus exister.
    if re.search(r'\(defwindow\s+hud(?=[\s\[])', texte):
        print('ECART         fenetre "hud" (ancienne fenetre unique) encore presente')
        erreurs = 1
    for piece, p in PIECES.items():
        fen = fenetre_eww(piece)
        if not symetrique(piece):
            print(f'ECART         {fen} : forme NON symetrique haut/bas (bogue picom : verre net)')
            erreurs = 1
        debut = re.search(r'\(defwindow\s+' + re.escape(fen) + r'(?=[\s\[])', texte)
        if not debut:
            print(f'ECART         {fen} : absente de eww.yuck')
            erreurs = 1
            continue
        # Corps de la fenetre : de "(defwindow <nom>" jusqu'au defwindow suivant.
        suite = re.search(r'\(defwindow\s', texte[debut.end():])
        corps = texte[debut.start(): debut.end() + suite.start() if suite else len(texte)]
        g = re.search(r':geometry\s+\(geometry\s+:x\s+"(-?\d+)px"\s+:y\s+"(-?\d+)px"\s+'
                      r':width\s+"(\d+)px"\s+:height\s+"(\d+)px"', corps)
        lu = tuple(int(v) for v in g.groups()) if g else None
        m = re.search(r'\(hud_piece\s+:nom\s+"([\w-]+)"\s+:w\s+(\d+)\s+:h\s+(\d+)\s*\)', corps)
        piece_lue = (m.group(1), int(m.group(2)), int(m.group(3))) if m else None
        attendu = p['fenetre']
        if lu == attendu and piece_lue == (piece, attendu[2], attendu[3]):
            print(f'ok            {fen} : {attendu[0]},{attendu[1]} {attendu[2]}x{attendu[3]}, symetrique')
        else:
            print(f'ECART         {fen} : eww.yuck {lu} {piece_lue}, cadre.py {attendu}')
            erreurs = 1
    return erreurs

# ---------------------------------------------------------------- sortie
if __name__ == '__main__':
    quoi = sys.argv[1] if len(sys.argv) > 1 else 'geometrie'
    if quoi in PIECES:
        sys.stdout.write(svg_piece(quoi))
    elif quoi == 'decoupe':
        for piece in PIECES:
            for p in decoupe(piece):
                print(f'{piece:<11} ' + ' '.join(f'{x},{y}' for x, y in p))
    elif quoi == 'geometrie':
        afficher_geometrie()
    elif quoi == 'verifier':
        defaut = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'eww.yuck')
        sys.exit(verifier(sys.argv[2] if len(sys.argv) > 2 else defaut))
    else:
        sys.exit(f'usage : cadre.py {"|".join(PIECES)}|decoupe|geometrie|verifier')
