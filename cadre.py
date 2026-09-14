#!/usr/bin/env python3
"""
cadre.py - geometrie du panneau d'angle (HUD) : une colonne d'hexagones le
long du bord gauche de l'ecran, les cadres SVG qui la dessinent, et les
masques de decoupe tires de ces cadres.

Source UNIQUE de la geometrie : eww.yuck en recopie les nombres (section
PANNEAU D'ANGLE : fenetres et cases), decoupe-hud.py applique les masques
(hud/<piece>.masque), et "python3 cadre.py verifier" controle que tout
concorde.

Disposition (croquis de Gauthier du 14/09 ; ~73 % de la hauteur de l'ecran
depuis l'agrandissement de 20 % du meme jour, 60 % avant),
tout empile verticalement, hexagones reguliers "pointe en haut" :
  - heure      : un grand hexagone, rogne par le haut et la gauche de l'ecran,
                 qui CACHE le coin haut-gauche de l'ecran (voir COIN) ;
  - meteo      : un nid d'abeille de 6 hexagones egaux (centre, haut-gauche,
                 haut-droit, droit, bas-droit, bas-gauche), qui ne forment
                 qu'une seule piece, detachee du bord de l'ecran ;
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

COIN (demande du 14/09) : toute la partie haut-gauche de l'hexagone de
l'heure doit etre hors de l'ecran, sans laisser voir un bout de fond d'ecran
dans le coin. Il faut donc que le coin (0, 0) de l'ecran soit A L'INTERIEUR
de l'hexagone : son cote gauche a x < 0, et son arete haut-gauche au-dessus
du coin. "python3 cadre.py verifier" controle que le coin est dedans, a au
moins COIN_MARGE px de chaque arete.

DECOUPE AU PIXEL PRES (14/09) : la forme X Shape est binaire (un pixel est
dedans ou dehors). Deux essais avant d'en arriver la :
  - forme = hexagone exact : elle coupait le trait du contour, qui devenait
    un escalier ;
  - forme = hexagone agrandi de ~1,7 px : le trait restait lisse, mais le
    flou debordait dans cette bande, sans le voile du verre (un liseré de 0
    a 2 px selon l'endroit, remarque par Gauthier).
Desormais la forme est tiree du DESSIN : le cadre SVG est rendu par
GdkPixbuf (le meme moteur que GTK), et la forme est exactement l'ensemble
des pixels ou il dessine quelque chose (verre ou trait, pixels adoucis
compris, opacite > SEUIL_ALPHA). Le flou s'arrete au bord exterieur du
trait, et le trait reste lisse. La symetrie haut/bas est imposee (union du
masque et de son reflet).
Ces masques sont calcules par generer-cadres.sh (hud/<piece>.masque) :
decoupe-hud.py ne fait que les lire, sans charger GTK.
Chaque fenetre garde une MARGE de vide autour de ses hexagones -- sauf au
bord gauche de l'ecran, ou l'on coupe net (x < 0 est interdit, voir plus haut).

MEME TRAIT QUE LA COLONNE (demande du 14/09) : la bordure des panneaux de
la colonne fait 1 px, a .25 d'opacite, et tombe sur une colonne de pixels
entiere : elle est nette. Le contour des hexagones fait donc 1 px lui aussi,
trace RETRAIT = 0,5 px a l'interieur de chaque hexagone : les sommets sont
sur des pixels entiers, un trait centre dessus s'etalerait sur deux colonnes
de pixels (flou) ; decale d'un demi-pixel, il tombe au milieu d'une seule.
Les cotes verticaux sont ainsi aussi nets que la bordure de la colonne ; les
cotes obliques restent adoucis (ils ne peuvent pas suivre la grille), a la
meme finesse.

CASES (R3, 14/09) : pour les pieces a plusieurs hexagones (la meteo), chaque
hexagone porte son propre contenu. cases() donne, pour chacun, son rectangle
dans la fenetre ; eww.yuck les recopie (widget hud_case), et
"python3 cadre.py verifier" controle la copie.

Couleurs (tokens de eww.scss, identiques a la colonne de droite) :
    verre    rgba(255,255,255,.10)   = .panel background-color
    contour  rgba(255,255,255,.25)   = .panel border

ATTENTION : ce fichier genere du SVG consomme par librsvg. Rester en ASCII
dans les chaines produites (les commentaires Python n'y vont pas).

Usage :
    python3 cadre.py heure        > hud/heure.svg        (idem meteo, sparklines)
    python3 cadre.py masque heure > hud/heure.masque     (rendu du SVG : GTK requis)
    python3 cadre.py decoupe                   # resume des masques enregistres
    python3 cadre.py geometrie                 # les lignes a recopier dans eww.yuck
    python3 cadre.py verifier [eww.yuck]       # eww.yuck a jour ? symetrie ? coin ? masques ? cases ?
(generer-cadres.sh fait les SVG, les masques et la verification d'un coup.)
"""
import math
import os
import re
import sys

VERRE   = 'rgba(255,255,255,.10)'
CONTOUR = 'rgba(255,255,255,.25)'
TRAIT = 1            # epaisseur du contour (px), comme .panel border ($bordure)
RETRAIT = 0.5        # le contour est trace a 0,5 px a l'interieur (voir MEME TRAIT)
MARGE = 3            # vide autour des hexagones dans leur fenetre (px)
SEUIL_ALPHA = 3      # un pixel est dans la forme si son opacite depasse 3/255
                     # (ecarte la "poussiere" numerique du lissage)
COIN_MARGE = 6       # le coin de l'ecran doit etre a >= 6 px des aretes de l'heure

ICI = os.path.dirname(os.path.abspath(__file__))
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

def rentre(poly, d):
    """Le polygone convexe `poly`, chaque cote decale de d px vers l'interieur.
    Chaque cote devient une droite parallele ; les nouveaux sommets sont les
    intersections des droites voisines, pour que les cotes se rejoignent
    exactement aux coins."""
    n = len(poly)
    cx = sum(x for x, _ in poly) / n
    cy = sum(y for _, y in poly) / n
    droites = []
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        nx, ny = y2 - y1, x1 - x2                      # normale au cote
        l = math.hypot(nx, ny)
        nx, ny = nx / l, ny / l
        if (cx - x1) * nx + (cy - y1) * ny < 0:        # la tourner vers le centre
            nx, ny = -nx, -ny
        droites.append(((x1 + nx * d, y1 + ny * d), (x2 - x1, y2 - y1)))
    sommets = []
    for i in range(n):                                 # sommet i = cote i-1 x cote i
        (px, py), (ux, uy) = droites[i - 1]
        (qx, qy), (vx, vy) = droites[i]
        t = ((qx - px) * vy - (qy - py) * vx) / (ux * vy - uy * vx)
        sommets.append((px + t * ux, py + t * uy))
    return sommets

def distance_interieure(poly, x, y):
    """Distance du point (x, y) au bord du polygone convexe `poly` : positive
    si le point est dedans (distance a l'arete la plus proche), negative s'il
    est dehors."""
    n = len(poly)
    cx = sum(p[0] for p in poly) / n
    cy = sum(p[1] for p in poly) / n
    d = float('inf')
    for i in range(n):
        (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % n]
        nx, ny = y2 - y1, x1 - x2
        l = math.hypot(nx, ny)
        nx, ny = nx / l, ny / l
        if (cx - x1) * nx + (cy - y1) * ny < 0:        # normale vers l'interieur
            nx, ny = -nx, -ny
        d = min(d, (x - x1) * nx + (y - y1) * ny)
    return d

# ---------------------------------------------------------------- geometrie
# Chaque piece = une fenetre eww, nommee "hud-<piece>".
# cellules : (cx, cy, R) = centre et rayon de chaque hexagone, en px, dans le
# repere de l'ECRAN du dashboard (1920 x 1080 ; y < 0 = au-dessus de l'ecran).
# La fenetre de chaque piece en est deduite (fenetre_de) : rien a recopier.
# noms (facultatif) : un nom par cellule, pour les pieces dont chaque
# hexagone a son contenu (voir CASES).
# Les pieces sont placees EN CASCADE : la meteo sous l'heure, les sparklines
# sous la meteo. Agrandir une piece decale les suivantes, sans rien recalculer.
# Rayons pairs (sommets sur des pixels entiers).

# Axe commun : toutes les pieces sont centrees sur x = AXE. Pour decaler la
# colonne, changer AXE et relancer generer-cadres.sh. 92 (14/09) : la meteo
# ne touche plus le bord de l'ecran (ses cellules de gauche commencent a
# AXE - 80 = 12 px, soit ECART).
AXE = 92
ECART = 12           # entre deux pieces (px)
ECART_SPK = 11       # entre deux sparklines (px)

# Heure : rayon 120 (208 x 240 px ; 106 avant le 14/09, 88 avant +20 %).
# Plus grand que le reste pour rester rogne a gauche (cote gauche a
# AXE - 104 = -12) et cacher le coin (voir COIN) : centre a HY = 58, son
# arete haut-gauche croise le bord gauche de l'ecran a y ~ -9.
RH, HY = 120, 58

# Meteo : cellules de rayon 46 (80 x 92 px). Dans un nid d'abeille "pointe en
# haut", les voisins sont a (+-2a, 0) et (+-a, +-3b) du centre.
RM = 46
AM, BM = round(S3 * RM), RM // 2     # 40, 23
MX = AXE
MY = HY + RH + ECART + 3 * BM + RM   # centre du nid : sous l'heure

# Sparklines : rayon 56 (96 x 112 px), empilees sous la meteo.
RS = 56
SY = MY + 3 * BM + RM + ECART + RS   # centre de la premiere

PIECES = {
    'heure': {'cellules': [(AXE, HY, RH)]},
    'meteo': {'cellules': [(MX,          MY,          RM),     # centre
                           (MX + AM,     MY - 3 * BM, RM),     # haut-droit
                           (MX + 2 * AM, MY,          RM),     # droit
                           (MX + AM,     MY + 3 * BM, RM),     # bas-droit
                           (MX - AM,     MY + 3 * BM, RM),     # bas-gauche
                           (MX - AM,     MY - 3 * BM, RM)],    # haut-gauche
              'noms': ['centre', 'haut-droit', 'droit', 'bas-droit', 'bas-gauche', 'haut-gauche']},
    'sparklines': {'cellules': [(AXE, SY + i * (2 * RS + ECART_SPK), RS) for i in range(3)],
                   'noms': ['cpu', 'ram', 'net']},
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

def cases(piece):
    """Pour une piece dont les hexagones ont chacun leur contenu : le
    rectangle de chaque hexagone dans sa fenetre, sous son nom global
    "<piece>-<nom>" (ex. "meteo-centre"). Renvoie [(nom, x, y, l, h), ...]."""
    noms = PIECES[piece].get('noms', [])
    return [(f'{piece}-{nom}', cx - round(S3 * R), cy - R, 2 * round(S3 * R), 2 * R)
            for nom, (cx, cy, R) in zip(noms, cellules_locales(piece))]

def symetrique(piece):
    """La regle de picom (voir en tete) : chaque cellule a-t-elle sa jumelle
    symetrique haut/bas dans la fenetre ? (Un hexagone "pointe en haut" est
    lui-meme symetrique : il suffit de comparer les centres.)"""
    h = PIECES[piece]['fenetre'][3]
    cellules = set(cellules_locales(piece))
    return cellules == {(cx, h - cy, R) for cx, cy, R in cellules}

def marge_coin():
    """De combien de px le coin (0, 0) de l'ecran est a l'interieur de
    l'hexagone de l'heure (negatif : il depasse, un bout de fond se voit)."""
    return distance_interieure(hexa(*PIECES['heure']['cellules'][0]), 0, 0)

# ---------------------------------------------------------------- SVG

def chemin(polygones):
    return ' '.join('M' + ' L'.join(f'{x:g},{y:g}' for x, y in p) + ' Z' for p in polygones)

def segments_contour(piece):
    """Segments du contour : le bord exterieur de la piece (les cotes que
    partagent deux cellules voisines sont interieurs : pas de trait entre
    elles), chacun pris sur l'hexagone RENTRE de sa cellule (voir MEME TRAIT)."""
    hexagones = [hexa(cx, cy, R) for cx, cy, R in cellules_locales(piece)]
    compte = {}
    for p in hexagones:
        for i in range(6):
            cle = frozenset((p[i], p[(i + 1) % 6]))
            compte[cle] = compte.get(cle, 0) + 1
    segments = []
    for p in hexagones:
        q = rentre(p, RETRAIT)
        for i in range(6):
            if compte[frozenset((p[i], p[(i + 1) % 6]))] == 1:
                segments.append((q[i], q[(i + 1) % 6]))
    return segments

def svg_piece(piece):
    """Cadre d'une piece, a la taille de sa fenetre : verre sur les hexagones,
    puis le contour, trait entier et lisse."""
    _, _, W, H = PIECES[piece]['fenetre']
    cellules = [hexa(cx, cy, R) for cx, cy, R in cellules_locales(piece)]
    traits = ' '.join(f'M{a[0]:.2f},{a[1]:.2f} L{b[0]:.2f},{b[1]:.2f}' for a, b in segments_contour(piece))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
            f'<path d="{chemin(cellules)}" fill="{VERRE}"/>'
            f'<path d="{traits}" fill="none" stroke="{CONTOUR}" stroke-width="{TRAIT}" '
            f'stroke-linecap="square"/>'
            f'</svg>\n')

# ---------------------------------------------------------------- masques

def calculer_masque(piece):
    """Pixels de la fenetre ou le cadre dessine quelque chose (opacite >
    SEUIL_ALPHA), d'apres son rendu par GdkPixbuf -- le moteur de GTK, donc
    exactement ce que eww affichera. Symetrie haut/bas imposee (union avec le
    reflet), pour la regle de picom. Renvoie (largeur, hauteur, lignes de bool).
    GTK n'est charge qu'ici : decoupe-hud.py, qui ne fait que lire les
    masques, reste rapide."""
    import gi
    gi.require_version('GdkPixbuf', '2.0')
    from gi.repository import GdkPixbuf
    chargeur = GdkPixbuf.PixbufLoader.new_with_type('svg')
    chargeur.write(svg_piece(piece).encode('ascii'))
    chargeur.close()
    pb = chargeur.get_pixbuf()
    W, H = pb.get_width(), pb.get_height()
    n, pas, px = pb.get_n_channels(), pb.get_rowstride(), pb.get_pixels()
    m = [[px[y * pas + x * n + 3] > SEUIL_ALPHA for x in range(W)] for y in range(H)]
    return W, H, [[m[y][x] or m[H - 1 - y][x] for x in range(W)] for y in range(H)]

def texte_masque(piece):
    """Le fichier hud/<piece>.masque : une ligne "largeur hauteur", puis un
    rectangle "x y largeur 1" par suite de pixels de la forme sur une ligne."""
    W, H, m = calculer_masque(piece)
    lignes = [f'# masque X Shape de {fenetre_eww(piece)} (genere par cadre.py : ne pas modifier)',
              f'{W} {H}']
    for y, rang in enumerate(m):
        x = 0
        while x < W:
            if rang[x]:
                debut = x
                while x < W and rang[x]:
                    x += 1
                lignes.append(f'{debut} {y} {x - debut} 1')
            else:
                x += 1
    return '\n'.join(lignes) + '\n'

def lire_masque(piece):
    """Lit hud/<piece>.masque : renvoie (largeur, hauteur, [(x, y, l, h), ...])."""
    with open(os.path.join(ICI, 'hud', f'{piece}.masque')) as f:
        lignes = [l.split() for l in f if l.strip() and not l.startswith('#')]
    W, H = (int(v) for v in lignes[0])
    return W, H, [tuple(int(v) for v in l) for l in lignes[1:]]

def masque_symetrique(H, rectangles):
    """Le masque est-il son propre reflet haut/bas (ligne y <-> ligne H-1-y) ?"""
    lignes = {(x, y, l) for x, y, l, _ in rectangles}
    return lignes == {(x, H - 1 - y, l) for x, y, l in lignes}

# ---------------------------------------------------------------- eww.yuck

def afficher_geometrie():
    """Les lignes a recopier dans eww.yuck, dans la forme exacte attendue."""
    for piece, p in PIECES.items():
        x, y, w, h = p['fenetre']
        print(f';; (defwindow {fenetre_eww(piece)} ...)')
        print(f'  :geometry (geometry :x "{x}px" :y "{y}px" :width "{w}px" :height "{h}px" :anchor "top left")')
        print(f'  (hud_piece :nom "{piece}" :w {w} :h {h}))')
        for nom, cx, cy, l, h in cases(piece):
            print(f'    (hud_case :nom "{nom}" :x {cx} :y {cy} :w {l} :h {h}')
        print()

def verifier(chemin_yuck):
    """Compare les nombres recopies dans eww.yuck a ceux de ce fichier, et
    controle la symetrie de chaque fenetre, le coin cache par l'heure, les
    masques enregistres et les cases. Renvoie le code de sortie (0 ou 1)."""
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
    coin = marge_coin()
    if coin >= COIN_MARGE:
        print(f'ok            coin haut-gauche de l\'ecran cache par l\'heure ({coin:.1f} px a l\'interieur)')
    else:
        print(f'ECART         coin haut-gauche : {coin:.1f} px a l\'interieur de l\'heure '
              f'(il en faut {COIN_MARGE}) : un bout de fond d\'ecran se voit dans le coin')
        erreurs = 1
    for piece, p in PIECES.items():
        fen = fenetre_eww(piece)
        attendu = p['fenetre']
        if not symetrique(piece):
            print(f'ECART         {fen} : forme NON symetrique haut/bas (bogue picom : verre net)')
            erreurs = 1
        # Masque enregistre : present, a la taille de la fenetre, symetrique.
        try:
            W, H, rects = lire_masque(piece)
            if (W, H) == attendu[2:] and masque_symetrique(H, rects):
                print(f'ok            hud/{piece}.masque : {W}x{H}, {len(rects)} rectangles, symetrique')
            else:
                print(f'ECART         hud/{piece}.masque : {W}x{H} (attendu {attendu[2]}x{attendu[3]}), '
                      f'symetrique {masque_symetrique(H, rects)} -- relancer generer-cadres.sh')
                erreurs = 1
        except (OSError, ValueError, IndexError) as e:
            print(f'ECART         hud/{piece}.masque illisible ({e}) -- relancer generer-cadres.sh')
            erreurs = 1
        # Cases recopiees dans eww.yuck (widget hud_case), pour les pieces qui en ont.
        for nom, cx, cy, l, h in cases(piece):
            m = re.search(r'\(hud_case\s+:nom\s+"' + re.escape(nom) + r'"\s+:x\s+(\d+)\s+:y\s+(\d+)'
                          r'\s+:w\s+(\d+)\s+:h\s+(\d+)\b', texte)
            lu = tuple(int(v) for v in m.groups()) if m else None
            if lu == (cx, cy, l, h):
                print(f'ok              case {nom} : {cx},{cy} {l}x{h}')
            else:
                print(f'ECART           case {nom} : eww.yuck {lu}, cadre.py {(cx, cy, l, h)}')
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
        # (pas de ")" exige apres :h : la piece peut contenir un enfant, son contenu)
        m = re.search(r'\(hud_piece\s+:nom\s+"([\w-]+)"\s+:w\s+(\d+)\s+:h\s+(\d+)\b', corps)
        piece_lue = (m.group(1), int(m.group(2)), int(m.group(3))) if m else None
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
    elif quoi == 'masque' and len(sys.argv) > 2 and sys.argv[2] in PIECES:
        sys.stdout.write(texte_masque(sys.argv[2]))
    elif quoi == 'decoupe':
        for piece in PIECES:
            W, H, rects = lire_masque(piece)
            print(f'{piece:<11} {W}x{H} : {len(rects)} rectangles, '
                  f'{sum(l * h for _, _, l, h in rects)} px, symetrique {masque_symetrique(H, rects)}')
    elif quoi == 'geometrie':
        afficher_geometrie()
    elif quoi == 'verifier':
        sys.exit(verifier(sys.argv[2] if len(sys.argv) > 2 else os.path.join(ICI, 'eww.yuck')))
    else:
        sys.exit(f'usage : cadre.py {"|".join(PIECES)} | masque <piece> | decoupe | geometrie | verifier')
