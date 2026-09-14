#!/usr/bin/env python3
"""
decoupe-hud.py - donne a chaque fenetre du panneau d'angle (hud-heure,
hud-meteo, hud-sparklines) sa forme exacte (extension X Shape), pour que
picom ne floute QUE ses hexagones, et pas le rectangle de la fenetre autour.

Pourquoi un script externe : eww 0.6.0 ne sait pas donner une forme a une
fenetre (spike du 11/09). On la pose donc de l'exterieur, sur les fenetres X
deja ouvertes.

La forme vit sur la fenetre X, pas dans eww : eww reload, un close/open, un
enregistrement de eww.yuck ou un redemarrage du demon recreent les fenetres,
SANS forme. D'ou deux appels :
  - ouvrir-hud.sh, juste apres l'ouverture (option --attendre) ;
  - eww-watchdog.sh, quand la liste des fenetres a change.

Ne touche pas une fenetre qui a DEJA une forme : la reposer enverrait un
evenement ShapeNotify, et picom recalculerait et repeindrait le flou pour
rien. (Apres un changement de masque, rouvrir le HUD : ouvrir-hud.sh.)

Forme : les masques hud/<piece>.masque, tires du rendu des cadres SVG par
generer-cadres.sh (voir cadre.py, DECOUPE AU PIXEL PRES). Ce script ne fait
que les lire : pas de GTK a charger, il reste rapide. Chaque masque doit etre
symetrique haut/bas, a cause d'un bogue de picom 10.2 (voir cadre.py) ;
"python3 cadre.py verifier" le controle.
Zero dependance Python : ctypes sur libX11 et libXext, deja installees.

Usage :
    python3 decoupe-hud.py              # decoupe les fenetres hud-* qui n'ont pas leur forme
    python3 decoupe-hud.py --attendre   # idem, en attendant jusqu'a 3 s qu'elles existent toutes
    python3 decoupe-hud.py --etat       # dit seulement, pour chacune, si elle existe et a sa forme
Sortie : une ligne par forme POSEE (le watchdog la journalise), rien sinon.
Code de sortie :
    0  toutes les fenetres hud-* presentes ont leur forme
    1  serveur X injoignable
    2  aucune fenetre hud-* (HUD ferme : rien a faire)
    3  une forme manque apres la pose (fenetre disparue entre-temps, ou
       masque illisible / pas a la taille de la fenetre)
"""
import ctypes
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cadre

# Titre X de chaque fenetre -> piece ("Eww - " + nom du defwindow, verifie
# avec xprop). Les noms viennent de cadre.py : rien a changer ici.
TITRES = {f'Eww - {cadre.fenetre_eww(p)}'.encode(): p for p in cadre.PIECES}

# Constantes de X11 / de l'extension Shape (X11/extensions/shape.h)
SHAPE_BOUNDING, SHAPE_INPUT, SHAPE_SET = 0, 2, 0

# Noms exacts des bibliotheques, et PAS ctypes.util.find_library : celle-ci
# lance un sous-processus (ldconfig) a chaque appel, et coutait a elle seule
# les trois quarts du temps d'execution du script (mesure le 12/09).
x11  = ctypes.CDLL('libX11.so.6')
xext = ctypes.CDLL('libXext.so.6')

class XRectangle(ctypes.Structure):
    _fields_ = [('x', ctypes.c_short), ('y', ctypes.c_short),
                ('width', ctypes.c_ushort), ('height', ctypes.c_ushort)]

Display, Window, Region = ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p
PWindow = ctypes.POINTER(Window)

x11.XOpenDisplay.restype = Display
x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
x11.XCloseDisplay.argtypes = [Display]
x11.XDefaultRootWindow.restype = Window
x11.XDefaultRootWindow.argtypes = [Display]
x11.XQueryTree.argtypes = [Display, Window, PWindow, PWindow,
                           ctypes.POINTER(PWindow), ctypes.POINTER(ctypes.c_uint)]
x11.XFetchName.argtypes = [Display, Window, ctypes.POINTER(ctypes.c_void_p)]
x11.XFree.argtypes = [ctypes.c_void_p]
x11.XSync.argtypes = [Display, ctypes.c_int]
x11.XCreateRegion.restype = Region
x11.XUnionRectWithRegion.argtypes = [ctypes.POINTER(XRectangle), Region, Region]
x11.XDestroyRegion.argtypes = [Region]
xext.XShapeCombineRegion.argtypes = [Display, Window, ctypes.c_int, ctypes.c_int,
                                     ctypes.c_int, Region, ctypes.c_int]
_i, _u = ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_uint)
xext.XShapeQueryExtents.argtypes = [Display, Window, _i, _i, _i, _u, _u, _i, _i, _i, _u, _u]

# Erreurs X : une fenetre peut disparaitre entre le moment ou on la trouve et
# celui ou on la decoupe (eww la recree). Par defaut, Xlib TUE le programme
# sur une telle erreur ; on l'ignore : le code de sortie 3 le signalera, et
# le watchdog reessaiera avec la nouvelle fenetre.
ERREUR_X = ctypes.CFUNCTYPE(ctypes.c_int, Display, ctypes.c_void_p)
_ignorer = ERREUR_X(lambda dpy, evt: 0)      # garder une reference (sinon ramasse-miettes)
x11.XSetErrorHandler.argtypes = [ERREUR_X]


def nom_de(dpy, w):
    p = ctypes.c_void_p()
    if not x11.XFetchName(dpy, w, ctypes.byref(p)) or not p.value:
        return None
    try:
        return ctypes.string_at(p.value)
    finally:
        x11.XFree(p)


def trouver(dpy, fenetre, trouvees, profondeur=2):
    """Remplit `trouvees` {piece: identifiant} avec les fenetres hud-* situees
    sous `fenetre`. Profondeur 2 : sous Openbox, une fenetre eww est l'enfant
    d'un cadre, lui-meme enfant de la racine."""
    racine, parent, enfants, n = Window(), Window(), PWindow(), ctypes.c_uint()
    if not x11.XQueryTree(dpy, fenetre, ctypes.byref(racine), ctypes.byref(parent),
                          ctypes.byref(enfants), ctypes.byref(n)):
        return
    liste = [enfants[i] for i in range(n.value)]
    if n.value:
        x11.XFree(ctypes.cast(enfants, ctypes.c_void_p))
    for w in liste:
        piece = TITRES.get(nom_de(dpy, w))
        if piece:
            trouvees[piece] = w
        elif profondeur > 1:
            trouver(dpy, w, trouvees, profondeur - 1)


def a_une_forme(dpy, w):
    v = [ctypes.c_int(), ctypes.c_int(), ctypes.c_int(), ctypes.c_uint(), ctypes.c_uint(),
         ctypes.c_int(), ctypes.c_int(), ctypes.c_int(), ctypes.c_uint(), ctypes.c_uint()]
    xext.XShapeQueryExtents(dpy, w, *[ctypes.byref(a) for a in v])
    return bool(v[0].value)          # bounding_shaped


def poser(dpy, w, piece):
    """Forme = union des rectangles du masque hud/<piece>.masque. Posee aussi
    en forme d'ENTREE : un clic hors du dessin traverse jusqu'au bureau.
    Renvoie False si le masque est illisible (fichier absent ou abime)."""
    try:
        _, _, rectangles = cadre.lire_masque(piece)
    except (OSError, ValueError, IndexError) as e:
        print(f'decoupe-hud : masque de {piece} illisible ({e})', file=sys.stderr)
        return False
    region = x11.XCreateRegion()
    r = XRectangle()
    for x, y, l, h in rectangles:
        r.x, r.y, r.width, r.height = x, y, l, h
        x11.XUnionRectWithRegion(ctypes.byref(r), region, region)
    for sorte in (SHAPE_BOUNDING, SHAPE_INPUT):
        xext.XShapeCombineRegion(dpy, w, sorte, 0, 0, region, SHAPE_SET)
    x11.XDestroyRegion(region)
    x11.XSync(dpy, 0)
    return True


def main():
    attendre, etat = '--attendre' in sys.argv, '--etat' in sys.argv
    dpy = x11.XOpenDisplay(None)
    if not dpy:
        print('decoupe-hud : serveur X injoignable', file=sys.stderr)
        return 1
    x11.XSetErrorHandler(_ignorer)
    try:
        racine = x11.XDefaultRootWindow(dpy)
        limite = time.monotonic() + (3 if attendre else 0)
        while True:
            trouvees = {}
            trouver(dpy, racine, trouvees)
            if len(trouvees) == len(cadre.PIECES) or time.monotonic() >= limite:
                break
            time.sleep(0.1)
        if etat:
            for piece in cadre.PIECES:
                w = trouvees.get(piece)
                forme = ('forme OUI' if a_une_forme(dpy, w) else 'forme NON') if w else 'absente'
                print(f'{cadre.fenetre_eww(piece):<15} {hex(w) if w else "-":<11} {forme}')
        if not trouvees:
            return 2
        manque = False
        for piece, w in trouvees.items():
            if a_une_forme(dpy, w):
                continue
            if etat:
                manque = True
                continue
            if poser(dpy, w, piece) and a_une_forme(dpy, w):
                print(f'decoupe posee sur {cadre.fenetre_eww(piece)} ({hex(w)})')
            else:
                manque = True
        return 3 if manque else 0
    finally:
        x11.XCloseDisplay(dpy)


if __name__ == '__main__':
    sys.exit(main())
