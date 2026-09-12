#!/usr/bin/env python3
"""
Vocabulaire de cadres HUD pour le panneau d'angle du dashboard PAI.

Plutot que de dessiner trois cadres a la main, on definit un petit vocabulaire
de pieces -- equerre, encoche, blocs segmentes, noeud, barre hachuree, connecteur --
et on compose. Modifier une piece la corrige partout ; ajouter un panneau ne
demande pas de redessiner.

Chaque cadre produit DEUX choses depuis la meme geometrie :
  - le SVG peint en fond de la fenetre GTK ;
  - le polygone de decoupe (clip-path CSS pour la maquette, masque X Shape en
    production : voir decoupe() et decoupe-hud.py).

Ce fichier est aussi la SOURCE UNIQUE des tailles et des positions du HUD :
eww.yuck en recopie les nombres (section PANNEAU D'ANGLE), et
"python3 cadre.py verifier" controle que la copie est a jour.

Couleurs : blanc uniquement, aux opacites du dashboard (eww.scss).
    verre    rgba(255,255,255,.10)   = .panel background-color
    contour  rgba(255,255,255,.28)   ~ .panel border (.25), un cran plus lisible
    accent   rgba(255,255,255,.55)   = equerres et amorces, ce qui fait le style
    filet    rgba(255,255,255,.30)   = filigrane hors cadre
    hachure  rgba(255,255,255,.22)

ATTENTION : ce fichier genere du SVG consomme par librsvg. Rester en ASCII
dans les chaines produites (les commentaires Python n'y vont pas).

Usage :
    python3 cadre.py heure       > hud/heure.svg
    python3 cadre.py sparklines  > hud/sparklines.svg
    python3 cadre.py meteo       > hud/meteo.svg
    python3 cadre.py filigrane   > hud/filigrane.svg
    python3 cadre.py clips                     # les polygones (clip-path CSS, en %)
    python3 cadre.py decoupe                   # les polygones X Shape (px, fenetre hud)
    python3 cadre.py geometrie                 # les nombres a recopier dans eww.yuck
    python3 cadre.py verifier [eww.yuck]       # eww.yuck est-il a jour ?
(generer-cadres.sh fait les quatre SVG et la verification d'un coup.)
"""
import os
import re
import sys

VERRE   = 'rgba(255,255,255,.10)'
CONTOUR = 'rgba(255,255,255,.28)'
ACCENT  = 'rgba(255,255,255,.55)'
FILET   = 'rgba(255,255,255,.30)'
HACHURE = 'rgba(255,255,255,.22)'

# ---------------------------------------------------------------- vocabulaire

def poly(pts, close=True):
    d = 'M' + ' L'.join(f'{x:g},{y:g}' for x, y in pts)
    return d + ' Z' if close else d

def trace(d, col=CONTOUR, w=1.4, extra=''):
    return f'<path d="{d}" fill="none" stroke="{col}" stroke-width="{w}" {extra}/>'

def equerre(x, y, sx, sy, bras=20, w=2.2, col=ACCENT):
    """Equerre d'angle : deux segments partant du meme point."""
    return trace(f'M{x + sx * bras:g},{y:g} L{x:g},{y:g} L{x:g},{y + sy * bras:g}',
                 col, w, 'stroke-linecap="square"')

def blocs(x, y, n=5, bw=12, bh=6, gap=4, col=ACCENT):
    """Rangee de petits blocs pleins -- la bande d'identification des HUD."""
    return ''.join(f'<rect x="{x + i * (bw + gap):g}" y="{y:g}" width="{bw}" '
                   f'height="{bh}" fill="{col}"/>' for i in range(n))

def noeud(x, y, r=3.5, col=FILET):
    return f'<circle cx="{x:g}" cy="{y:g}" r="{r}" fill="none" stroke="{col}" stroke-width="1.2"/>'

def hachure(x, y, w, h, biais=0):
    """Bande hachuree a 45 degres. Le biais decale le bord droit (parallelogramme)."""
    p = poly([(x, y), (x + w, y), (x + w + biais, y + h), (x + biais, y + h)])
    return f'<path d="{p}" fill="url(#hach)"/>'

def connecteur(pts, col=FILET, w=1.1):
    """Ligne brisee du filigrane."""
    return trace(poly(pts, False), col, w, 'stroke-linejoin="round"')

DEFS = ('<defs><pattern id="hach" width="7" height="7" patternUnits="userSpaceOnUse" '
        'patternTransform="rotate(45)">'
        f'<line x1="0" y1="0" x2="0" y2="7" stroke="{HACHURE}" stroke-width="2"/>'
        '</pattern></defs>')

def svg(w, h, corps):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" overflow="visible">{DEFS}{corps}</svg>\n')

def clip(pts, w, h):
    return 'polygon(' + ', '.join(f'{x / w * 100:.3f}% {y / h * 100:.3f}%' for x, y in pts) + ')'

# ---------------------------------------------------------------- les cadres

# Amorce du connecteur heure -> filigrane (trait de 14 px).
# Historique : elle etait dessinee par heure(), de x = 300 a 314, donc HORS
# de l'image de 300 px. Un navigateur la montre (overflow visible), GTK la
# rogne : elle etait invisible sur le bureau. Elle vit desormais au debut du
# filigrane (fenetre sans decoupe ni flou, faite pour le trait nu), qui
# commence donc AMORCE px plus a gauche : pile au bord droit de heure.
AMORCE = 14

HEURE_W, HEURE_H = 300, 160
def heure_contour():
    c, g = 12, 30     # coupe haut-gauche, coupe bas-droite
    return [(c, 0), (HEURE_W, 0), (HEURE_W, HEURE_H - g), (HEURE_W - g, HEURE_H),
            (0, HEURE_H), (0, c)]

def heure():
    W, H, p = HEURE_W, HEURE_H, heure_contour()
    s  = f'<path d="{poly(p)}" fill="{VERRE}"/>'
    s += trace(poly(p))
    # encoches sur l'arete haute : deux tabulations posees sur la ligne
    s += trace(f'M96,0 L104,8 L150,8 L158,0', ACCENT, 1.6)
    s += blocs(172, 3, n=3, bw=14, bh=4)
    # equerres
    s += equerre(8, 12, 1, 1) + equerre(W - 8, 8, -1, 1)
    s += equerre(8, H - 8, 1, -1) + equerre(W - 8, H - 8 - 30, -1, -1, bras=14)
    # double ligne interieure a gauche
    s += trace('M6,44 L6,104', ACCENT, 1.4)
    s += trace('M10,52 L10,96', FILET, 1)
    # bande hachuree en bas a gauche
    s += hachure(20, H - 12, 46, 7, biais=6)
    # (l'amorce du connecteur vers le filigrane est dans filigrane() : voir AMORCE)
    return svg(W, H, s)

SPK_W, SPK_H = 570, 106
def spk_contour():
    return [(14, 0), (SPK_W, 0), (SPK_W, SPK_H - 34), (SPK_W - 46, SPK_H),
            (0, SPK_H), (0, 14)]

def sparklines():
    W, H, p = SPK_W, SPK_H, spk_contour()
    s  = f'<path d="{poly(p)}" fill="{VERRE}"/>'
    s += trace(poly(p))
    s += equerre(10, 14, 1, 1) + equerre(W - 8, 8, -1, 1)
    s += equerre(8, H - 8, 1, -1)
    # deux separateurs verticaux, un par cellule
    s += trace(f'M{W/3:g},16 L{W/3:g},{H-20:g}', FILET, 1)
    s += trace(f'M{2*W/3:g},16 L{2*W/3:g},{H-20:g}', FILET, 1)
    return svg(W, H, s)

FIL_W, FIL_H = 592 + AMORCE, 46
def filigrane():
    """Bande de circuiterie au-dessus des sparklines. Purement decorative :
    aucun verre, que du trait -- elle n'aura donc pas de flou (voir la note
    du brief : un flou derriere une ligne de 1 px ne produit rien de visible).

    Les AMORCE premiers pixels portent l'amorce qui la relie a heure ; le
    dessin d'origine suit, decale d'autant (groupe translate) pour garder ses
    coordonnees lisibles."""
    W, H = FIL_W, FIL_H
    # amorce : bord droit de heure -> noeud du bas (y = 30 ici = y 28 dans heure)
    s  = connecteur([(0, 30), (AMORCE, 30)])
    s += f'<g transform="translate({AMORCE},0)">'
    s += noeud(6, 12) + noeud(6, 30)
    s += connecteur([(12, 12), (34, 12), (44, 22), (170, 22)])
    s += connecteur([(12, 30), (28, 30), (38, 20), (60, 20)])
    s += blocs(64, 6, n=5, bw=11, bh=7)
    # chevron central
    s += trace('M196,26 L208,10 L220,26', ACCENT, 1.6, 'stroke-linejoin="miter"')
    s += hachure(228, 8, 96, 8, biais=8)
    s += trace('M232,30 L350,30 L364,18 L470,18', CONTOUR, 1.4, 'stroke-linejoin="round"')
    s += connecteur([(474, 18), (512, 18), (522, 8), (566, 8)])
    s += connecteur([(474, 26), (516, 26), (526, 36), (566, 36)])
    s += noeud(574, 8) + noeud(574, 36)
    s += '</g>'
    return svg(W, H, s)

MET_W, MET_H = 190, 330
def met_contour():
    c, g = 14, 34
    return [(c, 0), (MET_W - 26, 0), (MET_W, 26), (MET_W, MET_H - g),
            (MET_W - g, MET_H), (0, MET_H), (0, c)]

def meteo():
    W, H, p = MET_W, MET_H, met_contour()
    s  = f'<path d="{poly(p)}" fill="{VERRE}"/>'
    s += trace(poly(p))
    s += equerre(8, 14, 1, 1) + equerre(8, H - 8, 1, -1)
    # noeud en haut a droite, relie a la coupe
    s += noeud(W - 16, 14, r=5, col=ACCENT)
    s += trace(f'M{W-16:g},19 L{W-16:g},30', ACCENT, 1.4)
    # colonne de blocs sur le bord droit
    s += ''.join(f'<rect x="{W-14:g}" y="{44 + i*12:g}" width="7" height="7" fill="{ACCENT}"/>'
                 for i in range(4))
    s += trace(f'M{W-10:g},96 L{W-10:g},150', FILET, 1)
    # hachures haut-gauche et bas
    s += hachure(20, 6, 40, 7, biais=6)
    s += hachure(24, H - 14, 58, 8, biais=7)
    s += trace(f'M6,60 L6,120', ACCENT, 1.4)
    return svg(W, H, s)

# ---------------------------------------------------------------- positions

# Coin haut-gauche de chaque piece, en px, dans le repere de l'ecran du
# dashboard (1920 x 1080, hauteur utile 1046).
POSITIONS = {
    'heure':      (28, 26),
    'filigrane':  (342 - AMORCE, 24),   # 328 : colle au bord droit de heure
    'sparklines': (340, 80),
    'meteo':      (28, 202),
}
TAILLES = {
    'heure':      (HEURE_W, HEURE_H),
    'filigrane':  (FIL_W, FIL_H),
    'sparklines': (SPK_W, SPK_H),
    'meteo':      (MET_W, MET_H),
}

# Contour de chaque piece a verre, dans son propre repere. Le filigrane n'en a
# pas : c'est du trait nu, dans une fenetre ni decoupee ni floutee.
CONTOURS = {
    'heure':      heure_contour,
    'sparklines': spk_contour,
    'meteo':      met_contour,
}

# Deux fenetres eww (voir le brief, section 2) :
#  - hud           : les trois pieces a verre, floutees, decoupees (X Shape) ;
#  - hud-filigrane : le trait nu, rectangulaire, exclu du flou par picom.
FENETRES = {
    'hud':           ['heure', 'sparklines', 'meteo'],
    'hud-filigrane': ['filigrane'],
}

def geometrie(fenetre):
    """Rectangle englobant des pieces de la fenetre, et decalage (dx, dy) de
    chaque piece par rapport au coin de la fenetre.
    Renvoie ((x, y, w, h), {piece: (dx, dy, w, h)})."""
    pieces = FENETRES[fenetre]
    x0 = min(POSITIONS[p][0] for p in pieces)
    y0 = min(POSITIONS[p][1] for p in pieces)
    x1 = max(POSITIONS[p][0] + TAILLES[p][0] for p in pieces)
    y1 = max(POSITIONS[p][1] + TAILLES[p][1] for p in pieces)
    decalages = {p: (POSITIONS[p][0] - x0, POSITIONS[p][1] - y0) + TAILLES[p]
                 for p in pieces}
    return (x0, y0, x1 - x0, y1 - y0), decalages

def decoupe(fenetre):
    """Polygones de la forme X Shape de la fenetre : le contour de chaque
    piece a verre, decale a sa place dans la fenetre (px entiers).
    L'union de ces polygones est la seule zone que picom floutera.
    Renvoie {piece: [(x, y), ...]}."""
    _, dec = geometrie(fenetre)
    return {p: [(round(x + dx), round(y + dy)) for x, y in CONTOURS[p]()]
            for p, (dx, dy, _, _) in dec.items() if p in CONTOURS}

def afficher_geometrie():
    """Les lignes a recopier dans eww.yuck, dans la forme exacte attendue."""
    for fen in FENETRES:
        (x, y, w, h), dec = geometrie(fen)
        print(f';; fenetre {fen}')
        print(f'  :geometry (geometry :x "{x}px" :y "{y}px" :width "{w}px" '
              f':height "{h}px" :anchor "top left")')
        for p, (dx, dy, pw, ph) in dec.items():
            print(f'    (hud_piece :nom "{p}" :dx {dx} :dy {dy} :w {pw} :h {ph})')
        print()

def verifier(chemin):
    """Compare les nombres recopies dans eww.yuck a ceux de ce fichier.
    Une fenetre absente de eww.yuck n'est pas une erreur (etape pas encore
    faite) ; un nombre different, si. Renvoie le code de sortie (0 ou 1)."""
    with open(chemin, encoding='utf-8') as f:
        # On ignore les lignes de commentaire (;;) : elles peuvent citer des
        # exemples qui ne sont pas le vrai code.
        texte = '\n'.join(l for l in f.read().splitlines()
                          if not l.lstrip().startswith(';'))
    erreurs = 0
    for fen in FENETRES:
        (x, y, w, h), dec = geometrie(fen)
        # Corps de la fenetre : de "(defwindow <nom>" jusqu'au defwindow suivant.
        debut = re.search(r'\(defwindow\s+' + re.escape(fen) + r'(?=[\s\[])', texte)
        if not debut:
            print(f'--            fenetre {fen} : absente de eww.yuck (pas encore creee)')
            continue
        suite = re.search(r'\(defwindow\s', texte[debut.end():])
        corps = texte[debut.start(): debut.end() + suite.start() if suite else len(texte)]

        g = re.search(r':geometry\s+\(geometry\s+:x\s+"(\d+)px"\s+:y\s+"(\d+)px"\s+'
                      r':width\s+"(\d+)px"\s+:height\s+"(\d+)px"', corps)
        lu = tuple(int(v) for v in g.groups()) if g else None
        if lu == (x, y, w, h):
            print(f'ok            fenetre {fen} : {x},{y} {w}x{h}')
        else:
            print(f'ECART         fenetre {fen} : eww.yuck {lu}, cadre.py {(x, y, w, h)}')
            erreurs = 1

        trouvees = {}
        for m in re.finditer(r'\(hud_piece\s+:nom\s+"([\w-]+)"\s+:dx\s+(\d+)\s+:dy\s+(\d+)'
                             r'\s+:w\s+(\d+)\s+:h\s+(\d+)\s*\)', corps):
            if m.group(1) in trouvees:
                print(f'ECART         piece {m.group(1)} : presente deux fois dans {fen}')
                erreurs = 1
            trouvees[m.group(1)] = tuple(int(v) for v in m.groups()[1:])
        for p in sorted(set(dec) | set(trouvees)):
            if trouvees.get(p) == dec.get(p):
                print(f'ok              piece {p} : dx {dec[p][0]} dy {dec[p][1]} '
                      f'{dec[p][2]}x{dec[p][3]}')
            else:
                print(f'ECART           piece {p} : eww.yuck {trouvees.get(p)}, '
                      f'cadre.py {dec.get(p)}')
                erreurs = 1
    return erreurs

# ---------------------------------------------------------------- sortie
if __name__ == '__main__':
    quoi = sys.argv[1] if len(sys.argv) > 1 else 'clips'
    if quoi == 'heure':       sys.stdout.write(heure())
    elif quoi == 'sparklines':sys.stdout.write(sparklines())
    elif quoi == 'meteo':     sys.stdout.write(meteo())
    elif quoi == 'filigrane': sys.stdout.write(filigrane())
    elif quoi == 'geometrie': afficher_geometrie()
    elif quoi == 'decoupe':
        for p, pts in decoupe('hud').items():
            print(f'{p:<10} ' + ' '.join(f'{x},{y}' for x, y in pts))
    elif quoi == 'verifier':
        defaut = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'eww.yuck')
        sys.exit(verifier(sys.argv[2] if len(sys.argv) > 2 else defaut))
    else:
        print('heure     ', clip(heure_contour(), HEURE_W, HEURE_H))
        print('sparklines', clip(spk_contour(), SPK_W, SPK_H))
        print('meteo     ', clip(met_contour(), MET_W, MET_H))
