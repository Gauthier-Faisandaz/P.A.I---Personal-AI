#!/usr/bin/env python3
"""
decoupe-hud.py - donne a la fenetre eww "hud" la forme exacte de ses trois
pieces (extension X Shape), pour que picom ne floute QUE les pieces, et pas
les vides entre elles.

Pourquoi un script externe : eww 0.6.0 ne sait pas donner une forme a une
fenetre (spike du 11/09). On la pose donc de l'exterieur, sur la fenetre X
deja ouverte. Le spike a verifie que picom (glx, dual_kawase) arrete bien son
flou sur cette forme, y compris sous Openbox (qui la recopie sur son cadre).

La forme vit sur la fenetre X, pas dans eww : eww reload, un close/open, un
enregistrement de eww.yuck ou un redemarrage du demon recreent la fenetre,
SANS forme. D'ou deux appels :
  - ouvrir-hud.sh, juste apres l'ouverture (option --attendre) ;
  - eww-watchdog.sh, quand la fenetre a change (nouvel identifiant X).

Econome, a deux niveaux :
  - si la fenetre a DEJA une forme, on ne touche a rien. La reposer enverrait
    un evenement ShapeNotify, et picom recalculerait la zone et repeindrait
    le flou, pour rien ;
  - le watchdog ne lance ce script que si l'identifiant de la fenetre a
    change (il le lit avec xwininfo, ~5 ms). Lancer Python a chaque tick
    coutait ~4 % d'un coeur en permanence (mesure le 12/09, i5-4210U).

Geometrie : cadre.py (source unique), fonction decoupe("hud").
Zero dependance Python : ctypes sur libX11 et libXext, deja installees.

Usage :
    python3 decoupe-hud.py              # cherche la fenetre, pose la forme si besoin
    python3 decoupe-hud.py --attendre   # idem, en guettant la fenetre jusqu'a 3 s
    python3 decoupe-hud.py --xid 0x...  # fenetre deja connue (watchdog) : pas de recherche
    python3 decoupe-hud.py --etat       # dit seulement si la fenetre existe et a sa forme
Sortie : une ligne SEULEMENT quand la forme est posee (le watchdog la journalise).
Code de sortie :
    0  la fenetre a sa forme (deja, ou posee a l'instant)
    1  serveur X injoignable
    2  pas de fenetre hud (HUD ferme : rien a faire)
    3  forme absente apres la pose (fenetre disparue entre-temps ?)
"""
import ctypes
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cadre

# Titre que eww donne a la fenetre "hud" ("Eww - " + nom du defwindow,
# verifie avec xprop). A changer si la fenetre est renommee dans eww.yuck.
NOM = b'Eww - hud'

# Constantes de X11 / de l'extension Shape (X11/extensions/shape.h)
SHAPE_BOUNDING, SHAPE_INPUT, SHAPE_SET, EVEN_ODD = 0, 2, 0, 0

# Noms exacts des bibliotheques, et PAS ctypes.util.find_library : celle-ci
# lance un sous-processus (ldconfig) a chaque appel, et coutait a elle seule
# les trois quarts du temps d'execution du script (mesure le 12/09).
x11  = ctypes.CDLL('libX11.so.6')
xext = ctypes.CDLL('libXext.so.6')

class XPoint(ctypes.Structure):
    _fields_ = [('x', ctypes.c_short), ('y', ctypes.c_short)]

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
x11.XPolygonRegion.restype = Region
x11.XPolygonRegion.argtypes = [ctypes.POINTER(XPoint), ctypes.c_int, ctypes.c_int]
x11.XUnionRegion.argtypes = [Region, Region, Region]
x11.XDestroyRegion.argtypes = [Region]
xext.XShapeCombineRegion.argtypes = [Display, Window, ctypes.c_int, ctypes.c_int,
                                     ctypes.c_int, Region, ctypes.c_int]
_i, _u = ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_uint)
xext.XShapeQueryExtents.argtypes = [Display, Window, _i, _i, _i, _u, _u, _i, _i, _i, _u, _u]

# Erreurs X : la fenetre peut disparaitre entre le moment ou on la trouve et
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


def trouver(dpy, fenetre, profondeur=2):
    """Cherche la fenetre NOM sous `fenetre`. Profondeur 2 : sous Openbox, la
    fenetre eww est l'enfant d'un cadre, lui-meme enfant de la racine."""
    racine, parent, enfants, n = Window(), Window(), PWindow(), ctypes.c_uint()
    if not x11.XQueryTree(dpy, fenetre, ctypes.byref(racine), ctypes.byref(parent),
                          ctypes.byref(enfants), ctypes.byref(n)):
        return None
    liste = [enfants[i] for i in range(n.value)]
    if n.value:
        x11.XFree(ctypes.cast(enfants, ctypes.c_void_p))
    for w in liste:
        if nom_de(dpy, w) == NOM:
            return w
    if profondeur > 1:
        for w in liste:
            trouvee = trouver(dpy, w, profondeur - 1)
            if trouvee:
                return trouvee
    return None


def a_une_forme(dpy, w):
    v = [ctypes.c_int(), ctypes.c_int(), ctypes.c_int(), ctypes.c_uint(), ctypes.c_uint(),
         ctypes.c_int(), ctypes.c_int(), ctypes.c_int(), ctypes.c_uint(), ctypes.c_uint()]
    xext.XShapeQueryExtents(dpy, w, *[ctypes.byref(a) for a in v])
    return bool(v[0].value)          # bounding_shaped


def poser(dpy, w):
    """Forme = union des polygones de cadre.decoupe("hud"). Posee aussi en
    forme d'ENTREE : un clic dans un vide traverse jusqu'au bureau."""
    region = x11.XCreateRegion()
    for pts in cadre.decoupe('hud').values():
        tableau = (XPoint * len(pts))(*[XPoint(x, y) for x, y in pts])
        morceau = x11.XPolygonRegion(tableau, len(pts), EVEN_ODD)
        x11.XUnionRegion(region, morceau, region)
        x11.XDestroyRegion(morceau)
    for sorte in (SHAPE_BOUNDING, SHAPE_INPUT):
        xext.XShapeCombineRegion(dpy, w, sorte, 0, 0, region, SHAPE_SET)
    x11.XDestroyRegion(region)
    x11.XSync(dpy, 0)


def main():
    args = sys.argv[1:]
    attendre, etat = '--attendre' in args, '--etat' in args
    xid = int(args[args.index('--xid') + 1], 0) if '--xid' in args else None

    dpy = x11.XOpenDisplay(None)
    if not dpy:
        print('decoupe-hud : serveur X injoignable', file=sys.stderr)
        return 1
    x11.XSetErrorHandler(_ignorer)
    try:
        w = xid
        if w is None:
            racine = x11.XDefaultRootWindow(dpy)
            limite = time.monotonic() + (3 if attendre else 0)
            while True:
                w = trouver(dpy, racine)
                if w or time.monotonic() >= limite:
                    break
                time.sleep(0.1)
        if not w:
            if etat:
                print('fenetre hud : absente')
            return 2
        if etat:
            print(f'fenetre hud {hex(w)} : forme {"OUI" if a_une_forme(dpy, w) else "NON"}')
            return 0 if a_une_forme(dpy, w) else 3
        if a_une_forme(dpy, w):
            return 0
        poser(dpy, w)
        if not a_une_forme(dpy, w):
            return 3
        print(f'decoupe posee sur {hex(w)}')
        return 0
    finally:
        x11.XCloseDisplay(dpy)


if __name__ == '__main__':
    sys.exit(main())
