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
  - meteo      : un nid d'abeille de 7 hexagones egaux (centre + 6 voisins),
                 rogne a gauche ; la cellule de gauche est une piece a part
                 (son propre contour), les 6 autres ne font qu'une forme ;
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

Couleurs (tokens de eww.scss) :
    verre    rgba(255,255,255,.10)   = .panel background-color
    contour  rgba(255,255,255,.55)   plus marque que .panel (.25) : sans
                                     decoration, c'est lui qui dessine la forme

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
CONTOUR = 'rgba(255,255,255,.55)'
# Epaisseur du trait de contour. Seule sa moitie INTERIEURE est visible : la
# decoupe X Shape de la fenetre coupe tout ce qui depasse de la forme.
TRAIT = 2.4

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
#   fenetre  : (x, y, largeur, hauteur) en px, repere de l'ecran du dashboard
#              (1920 x 1080). y < 0 = la fenetre commence au-dessus de l'ecran.
#   cellules : (cx, cy, R, groupe), dans le repere de la FENETRE.
#              groupe "forme"  : fusionnee avec les autres cellules "forme"
#                                (pas de trait entre elles) ;
#              groupe "a_part" : cellule a son propre contour complet.
# Axe commun : toutes les pieces sont centrees sur x = 52 (ecran).
# Ecarts : ~10 px entre les pieces, 9 px entre deux sparklines.

# Meteo : cellules de rayon 38 (66 x 76 px). Dans un nid d'abeille "pointe en
# haut", les voisins sont a (+-2a, 0) et (+-a, +-3b) du centre.
RM = 38
AM, BM = round(S3 * RM), RM // 2     # 33, 19
MX, MY = 52, 95                      # centre du nid, repere de la fenetre

PIECES = {
    # Heure : rayon 88 (152 x 176 px), centre ecran (52, 56) : 32 px au-dessus
    # de l'ecran (y negatif), 24 px a gauche (coupe verticale par la fenetre).
    'heure': {
        'fenetre':  (0, -32, 128, 176),
        'cellules': [(52, 88, 88, 'forme')],
    },
    'meteo': {
        'fenetre':  (0, 154, 151, 190),
        'cellules': [(MX,          MY,          RM, 'forme'),    # centre
                     (MX + AM,     MY - 3 * BM, RM, 'forme'),    # haut-droit
                     (MX + 2 * AM, MY,          RM, 'forme'),    # droit
                     (MX + AM,     MY + 3 * BM, RM, 'forme'),    # bas-droit
                     (MX - AM,     MY + 3 * BM, RM, 'forme'),    # bas-gauche (a moitie rogne)
                     (MX - AM,     MY - 3 * BM, RM, 'forme'),    # haut-gauche (a moitie rogne)
                     (MX - 2 * AM, MY,          RM, 'a_part')],  # gauche (presque hors ecran)
    },
    # Sparklines : rayon 46 (80 x 92 px), empilees, 9 px entre deux.
    'sparklines': {
        'fenetre':  (12, 355, 80, 294),
        'cellules': [(40, 46, 46, 'forme'), (40, 147, 46, 'forme'), (40, 248, 46, 'forme')],
    },
}

def fenetre_eww(piece):
    """Nom de la fenetre eww (defwindow) de la piece ; son titre X est
    "Eww - " + ce nom (verifie avec xprop)."""
    return 'hud-' + piece

def decoupe(piece):
    """Polygones de la forme X Shape de la fenetre (un par cellule, repere de
    la fenetre). Leur union est la seule zone affichee, et floutee, par picom."""
    return [hexa(cx, cy, R) for cx, cy, R, _ in PIECES[piece]['cellules']]

def symetrique(piece):
    """La regle de picom (voir en tete) : chaque cellule a-t-elle sa jumelle
    symetrique haut/bas dans la fenetre ? (Un hexagone "pointe en haut" est
    lui-meme symetrique : il suffit de comparer les centres.)"""
    h = PIECES[piece]['fenetre'][3]
    cellules = {(cx, cy, R) for cx, cy, R, _ in PIECES[piece]['cellules']}
    return cellules == {(cx, h - cy, R) for cx, cy, R in cellules}

# ---------------------------------------------------------------- SVG

def chemin(polygones):
    return ' '.join('M' + ' L'.join(f'{x},{y}' for x, y in p) + ' Z' for p in polygones)

def aretes_contour(piece):
    """Aretes a tracer : le bord exterieur des cellules "forme" (une arete
    partagee par deux cellules voisines est interieure : on l'ecarte), plus
    toutes les aretes des cellules "a_part"."""
    compte, a_part = {}, []
    for cx, cy, R, groupe in PIECES[piece]['cellules']:
        p = hexa(cx, cy, R)
        aretes = [(p[i], p[(i + 1) % 6]) for i in range(6)]
        if groupe == 'a_part':
            a_part += aretes
        else:
            for a, b in aretes:
                cle = frozenset((a, b))
                compte[cle] = compte.get(cle, 0) + 1
    bord = [tuple(sorted(cle)) for cle, n in compte.items() if n == 1]
    return bord + a_part

def svg_piece(piece):
    """Cadre d'une piece, a la taille de sa fenetre : verre sur l'union des
    cellules, puis le contour, limite a l'interieur de la forme (clip-path)
    pour correspondre a ce que la decoupe X Shape laissera voir."""
    _, _, W, H = PIECES[piece]['fenetre']
    forme = chemin(decoupe(piece))
    traits = ' '.join(f'M{a[0]},{a[1]} L{b[0]},{b[1]}' for a, b in aretes_contour(piece))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            f'<defs><clipPath id="forme"><path d="{forme}"/></clipPath></defs>'
            f'<path d="{forme}" fill="{VERRE}"/>'
            f'<path d="{traits}" fill="none" stroke="{CONTOUR}" stroke-width="{TRAIT}" '
            f'stroke-linecap="round" clip-path="url(#forme)"/>'
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
