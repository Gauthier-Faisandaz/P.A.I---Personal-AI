#!/usr/bin/env python3
"""
mise-en-page.py - calcule la hauteur de chaque panneau de la colonne eww
(recommandations, a venir, boite de reception) et la position verticale
(y) de leur bord haut.

Un panneau peut etre REPLIE : il ne garde que son en-tete (HAUTEUR_ENTETE)
et sort du partage ; les panneaux ouverts se repartissent la place avec
exactement le meme algorithme qu'avant, applique a eux seuls. Le defaut
reste "tout ouvert" : le repli est une exception, pas un accordeon.

Pourquoi un script : eww ne sait pas dire ou GTK a place un widget a
l'ecran. En calculant nous-memes les hauteurs, on connait aussi les y, et
la modale peut s'aligner sur le haut de son panneau.

Usage :
  mise-en-page.py          lit les donnees actuelles des panneaux (le bus :
                           ~/.cache/eww/bus/*.json) et affiche le resultat,
                           sans rien envoyer a eww.
  mise-en-page.py --replies reco,venir
                           meme chose, en supposant ces panneaux replies
                           (noms : reco, venir, mail).
  mise-en-page.py --pousser
                           meme calcul, puis envoie a eww les hauteurs
                           (h_reco h_venir h_mail), les positions (y_*) et
                           les indicateurs de coupe (t_* : true/false).
                           Lance par publier.sh apres chaque fetch-*.sh.
                           Pour l'instant, rien n'y est replie (l'etat de
                           repli sera branche aux etapes 2 et 3).
  mise-en-page.py test     verifie l'algorithme sur le tableau de reference
                           du brief v9 (section 3), plus des invariants.
  mise-en-page.py simuler --recos 3 --venir 7 --groupes 4 --mails 9 [--replies reco]
                           meme calcul sur des donnees inventees.
"""
import argparse
import dataclasses
import fcntl
import json
import math
import os
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass

EWW = os.path.expanduser("~/.cargo/bin/eww")
CACHE = os.path.expanduser("~/.cache/eww")
BUS = os.path.join(CACHE, "bus")          # rempli par publier.sh


# ==========================================================================
#  CONSTANTES DE MISE EN PAGE (px)
# ==========================================================================
# !! Ces valeurs DOUBLENT le style : bloc "CONSTANTES DE MISE EN PAGE" en
# tete de eww.scss, plus l'ecart :spacing et la largeur "33%" de la colonne
# dans eww.yuck. Toute retouche la-bas (padding, marge, taille de police)
# doit etre reportee ici, sinon les panneaux ne tombent plus juste.
#
# Hauteur d'une ligne de texte, police DejaVu Sans Mono (mesuree avec
# Pango, le moteur de texte de GTK) :
LIGNE_15 = 18          # $police        (15px)
LIGNE_13 = 17          # $police-petite (13px)
LIGNE_12 = 15          # $police-meta   (12px)
LIGNE_24 = 29          # $police-sync   (24px, le bouton de synchro)
# Largeur d'un caractere (police a chasse fixe : tous identiques) :
CHASSE_15 = 9
CHASSE_13 = 8
CHASSE_12 = 7

BORDURE = 1            # $bordure
PANNEAU_PAD_V = 14     # $panneau-pad-v (haut ET bas)
PANNEAU_PAD_H = 18     # $panneau-pad-h (gauche ET droite)
ENTETE = LIGNE_24 + 4                 # bouton ↻ + $entete-marge
SEPARATEUR = 6 + 1 + 12               # $sep-haut + trait + $sep-bas
# Tout ce qu'un panneau occupe en dehors de son contenu :
HABILLAGE = 2 * BORDURE + 2 * PANNEAU_PAD_V + ENTETE + SEPARATEUR   # 82

# Panneau REPLIE : son cadre et son en-tete, rien d'autre. Sans la marge
# sous l'en-tete ($entete-marge) : il n'y a plus rien dessous. Le style du
# panneau replie (etape 2) devra donc la retirer, sinon il ferait 63 px et
# non 59 -- et reporter cette valeur dans eww.scss (regle d'or n°6).
HAUTEUR_ENTETE = 2 * BORDURE + 2 * PANNEAU_PAD_V + LIGNE_24         # 59

SECTION_MARGE = 12     # $section-marge, sous chaque groupe SAUF le dernier
LIGNE_PAD = 2          # $ligne-pad, en haut ET en bas d'une ligne
RECO_TETE_MARGE = 2    # $reco-tete-marge
RECO_MARGE = 12        # $reco-marge, sous chaque reco SAUF la derniere
RECO_BAS = 8 + BORDURE + RECO_MARGE   # $reco-pad-bas + bordure + $reco-marge
RECO_PUCE = CHASSE_12 + 8             # le "●" + $reco-puce-marge
RECO_RETRAIT = 18      # $reco-detail-retrait

BANDEAU = 38 + 2 * BORDURE            # $bandeau-haut + bordures
ECART = 16             # :spacing de la box "colonne" (eww.yuck)
LARGEUR_PCT = 33       # :width "33%" de la fenetre colonne (eww.yuck)


@dataclass
class Constantes:
    """Hauteurs (px) des briques d'un panneau. Trois jeux : les valeurs
    reelles (tirees de eww.scss, ci-dessus) et celles de deux versions du
    brief, qui ne servent qu'a verifier l'algorithme contre leurs tableaux
    de reference."""
    habillage: int           # bordures + padding + en-tete + separateur
    ligne_vide: int          # "Aucune recommandation..." / "Rien a venir."
    section_titre: int       # "► DEMAIN · ven. 11" (a venir)
    mail_titre_section: int  # "► À TRAITER" (boite de reception)
    section_marge: int       # espace sous chaque groupe
    ligne_mail: int          # sujet + ligne "expediteur · age"
    ligne_mail_sans_meta: int
    ligne_venir: int
    reco_base: int           # reco avec un titre d'UNE ligne, sans detail
    reco_ligne_titre: int    # chaque ligne de titre en plus
    reco_ligne_detail: int   # chaque ligne de detail
    reco_marge: int          # marge comprise dans reco_base, absente sous
                             # la derniere reco (":last-child" dans eww.scss)
    replie: int              # hauteur d'un panneau replie

    @property
    def plancher(self):
        # Hauteur minimale d'un panneau OUVERT = celle d'un panneau vide
        # (en-tete + une ligne). Choisie EGALE pour tous les panneaux :
        # c'est ce qui fait tomber des panneaux vides sur des parts egales.
        return self.habillage + self.ligne_vide


REELLES = Constantes(
    habillage=HABILLAGE,
    ligne_vide=LIGNE_15,
    section_titre=LIGNE_15,
    mail_titre_section=LIGNE_15,
    section_marge=SECTION_MARGE,
    ligne_mail=2 * LIGNE_PAD + LIGNE_15 + LIGNE_12,     # 37
    ligne_mail_sans_meta=2 * LIGNE_PAD + LIGNE_15,      # 22
    ligne_venir=2 * LIGNE_PAD + LIGNE_15,               # 22
    reco_base=LIGNE_15 + RECO_TETE_MARGE + RECO_BAS,    # 41
    reco_ligne_titre=LIGNE_15,
    reco_ligne_detail=LIGNE_13,
    reco_marge=RECO_MARGE,
    replie=HAUTEUR_ENTETE,
)

# Brief precedent (v8, section 4) : en-tete 34 + padding 16, ligne vide
# 26... Ne sert plus qu'a un test de NON-REGRESSION : sans rien de replie,
# l'algorithme doit donner exactement ce qu'il donnait avant le repli. Le
# v8 ne repliait rien ; replie=34 est la valeur du v9.
BRIEF_V8 = Constantes(
    habillage=34 + 16, ligne_vide=26, section_titre=22, mail_titre_section=22,
    section_marge=0, ligne_mail=26, ligne_mail_sans_meta=26, ligne_venir=24,
    reco_base=40, reco_ligne_titre=18, reco_ligne_detail=17, reco_marge=0,
    replie=34,
)

# Brief actuel (v9, section 3) : memes briques, mais son tableau compte les
# mails comme une liste PLATE, sans la ligne "► À TRAITER" (verifie par le
# calcul : c'est la seule hypothese qui retombe sur ses valeurs). Le vrai
# panneau, lui, affiche cette ligne : REELLES la compte.
BRIEF_V9 = dataclasses.replace(BRIEF_V8, mail_titre_section=0)


# ==========================================================================
#  ALGORITHME DE REPARTITION (brief v9, section 3)
# ==========================================================================
def arrondir(hauteurs, total):
    """Arrondit a l'entier en gardant une somme EXACTEMENT egale a total
    (methode du plus fort reste). Un arrondi naif ferait gagner ou perdre
    un pixel a la colonne selon les cas, et le bandeau bougerait."""
    entiers = [math.floor(h) for h in hauteurs]
    manque = total - sum(entiers)
    par_reste = sorted(range(len(hauteurs)),
                       key=lambda i: hauteurs[i] - entiers[i], reverse=True)
    for i in par_reste[:manque]:
        entiers[i] += 1
    return entiers


def partager(A, besoins, plancher):
    """L'algorithme d'avant le repli, inchange, mais pour un nombre
    quelconque de panneaux (n = len(besoins), plus de "3" ecrit en dur).
    A = hauteur a partager ; besoins = hauteur naturelle de chacun.
    Renvoie des hauteurs entieres de somme A."""
    n = len(besoins)
    # Place trop petite pour garantir le plancher a tout le monde : parts
    # egales.
    if A <= n * plancher:
        return arrondir([A / n] * n, A)
    # 1. ce que chaque panneau reclame
    h = [max(plancher, b) for b in besoins]
    S = sum(h)
    if S < A:
        # 2. personne ne remplit : le surplus est partage egalement
        h = [x + (A - S) / n for x in h]
    elif S > A:
        # 3. ca deborde : on rogne au prorata du "gras" de chacun (ce qu'il
        #    a au-dessus du plancher). Jamais sous le plancher : le total du
        #    gras (S - n x plancher) depasse toujours l'exces (S - A).
        gras = [x - plancher for x in h]
        h = [x - (S - A) * g / sum(gras) for x, g in zip(h, gras)]
    return arrondir(h, A)


def repartir(A, besoins, plancher, replie, hauteur_replie):
    """A = hauteur a partager entre TOUS les panneaux (bandeau et ecarts
    deja retires) ; besoins = hauteur naturelle de chacun ; replie = un
    booleen par panneau, dans le meme ordre.

    Il n'y a pas deux mecanismes : les replies prennent leur en-tete et
    sortent du partage, puis partager() -- l'algorithme de toujours --
    travaille sur les ouverts seulement. n devient n_o, A devient A_o.

    Somme des hauteurs == A, sauf quand TOUT est replie : les en-tetes en
    haut, le bandeau en bas, le fond d'ecran entre les deux (mode bureau
    calme, permis expres)."""
    h = [hauteur_replie] * len(besoins)
    ouverts = [i for i, r in enumerate(replie) if not r]
    if not ouverts:
        return h
    A_o = A - hauteur_replie * (len(besoins) - len(ouverts))
    for i, x in zip(ouverts, partager(A_o, [besoins[i] for i in ouverts], plancher)):
        h[i] = x
    return h


# ==========================================================================
#  BESOIN DE CHAQUE PANNEAU (a partir des memes JSON que eww)
# ==========================================================================
# Meme signature pour tous (donnees, constantes, largeur), pour pouvoir les
# ranger dans la table PANNEAUX ; seules les recos se servent de la largeur
# (leurs titres et details passent a la ligne).
def nb_lignes(texte, largeur_px, chasse):
    """Nombre de lignes d'un label ":wrap true". Police a chasse fixe :
    chaque caractere fait exactement `chasse` px, on peut donc rejouer la
    coupure de GTK (entre deux mots) avec textwrap. C'est une estimation :
    une ligne d'ecart decale un peu la repartition, sans rien casser (le
    panneau defile)."""
    if not texte:
        return 0
    par_ligne = max(1, int(largeur_px // chasse))
    return max(1, len(textwrap.wrap(texte, width=par_ligne)))


def besoin_recos(recos, c, largeur):
    items = recos.get("recommandations") or []
    if not items:
        return c.habillage + c.ligne_vide
    interieur = largeur - 2 * BORDURE - 2 * PANNEAU_PAD_H
    total = c.habillage
    for r in items:
        lt = nb_lignes(r.get("titre") or "(sans titre)", interieur - RECO_PUCE, CHASSE_15)
        ld = nb_lignes(r.get("detail") or "", interieur - RECO_RETRAIT, CHASSE_13)
        total += c.reco_base + (lt - 1) * c.reco_ligne_titre + ld * c.reco_ligne_detail
    return total - c.reco_marge                # pas de marge sous la derniere


def besoin_venir(venir, c, largeur):
    groupes = venir.get("groupes") or []
    if not groupes:
        return c.habillage + c.ligne_vide
    return c.habillage - c.section_marge + sum(   # pas de marge sous le dernier
        c.section_titre + len(g.get("items") or []) * c.ligne_venir + c.section_marge
        for g in groupes)


def besoin_mails(digest, c, largeur):
    sections = digest.get("sections") or []
    if not sections:
        return c.habillage + c.ligne_vide      # "Aucun mail."
    total = c.habillage
    for s in sections:
        total += c.mail_titre_section + c.section_marge
        for it in s.get("items") or []:
            total += c.ligne_mail if it.get("meta") else c.ligne_mail_sans_meta
    return total - c.section_marge             # pas de marge sous la derniere


# ==========================================================================
#  LES PANNEAUX, de haut en bas
# ==========================================================================
# C'est ICI, et seulement ici, que le script apprend combien il y a de
# panneaux : n = len(PANNEAUX). Ajouter un panneau (la veille, etape 5) =
# une ligne de plus dans cette table (+ eww.yuck et publier.sh).
@dataclass(frozen=True)
class Panneau:
    var: str          # suffixe des variables eww : h_<var>, y_<var>, t_<var>
    nom: str          # pour l'affichage
    bus: str          # fichier du bus : ~/.cache/eww/bus/<bus>.json
    besoin: object    # fonction (donnees, constantes, largeur) -> px
    decor_fin: int    # decoration sans texte sous le dernier element : on
                      # peut la rogner sans que le panneau soit "tronque"


PANNEAUX = (
    Panneau("reco", "Recommandations", "recos", besoin_recos,
            8 + BORDURE),     # $reco-pad-bas + trait
    Panneau("venir", "À venir", "venir", besoin_venir, LIGNE_PAD),
    Panneau("mail", "Boîte de réception", "digest", besoin_mails, LIGNE_PAD),
)
VARS = tuple(p.var for p in PANNEAUX)


def calculer(donnees, c, hauteur_colonne, largeur, marge, replies=frozenset()):
    """Tout le calcul : besoins -> hauteurs -> positions y.
    donnees = {nom du bus: JSON} ; replies = ensemble de noms de PANNEAUX
    (VARS) replies."""
    n = len(PANNEAUX)
    # n panneaux + le bandeau = n+1 enfants dans la box colonne, donc n
    # ecarts entre eux.
    A = hauteur_colonne - BANDEAU - n * ECART
    besoins = [p.besoin(donnees.get(p.bus) or {}, c, largeur) for p in PANNEAUX]
    replie = [p.var in replies for p in PANNEAUX]
    h = repartir(A, besoins, c.plancher, replie, c.replie)
    # y[i] = marge + somme des (h[j] + ecart) pour j < i
    y, bord = [], marge
    for hi in h:
        y.append(bord)
        bord += hi + ECART
    # Tronque = du TEXTE est cache. Rogner seulement la decoration sous le
    # dernier element (padding + trait d'une reco, padding d'une ligne)
    # ne cache rien de lisible : pas de chevron ni de degrade pour ca. Un
    # panneau replie n'est jamais "tronque" : il n'a plus de liste.
    tronque = [not r and b - hi > p.decor_fin
               for p, r, hi, b in zip(PANNEAUX, replie, h, besoins)]
    return {"A": A, "besoin": besoins, "h": h, "y": y,
            "tronque": tronque, "replie": replie}


# ==========================================================================
#  ENTREES : geometrie de l'ecran, donnees des panneaux
# ==========================================================================
def geometrie():
    """(hauteur_colonne, largeur_colonne, marge, nom_ecran), lus la ou
    start.sh les a laisses : jamais supposes (regle d'or n°2, multi-ecran)."""
    try:
        with open(f"{CACHE}/colonne_args") as f:
            args = f.read()
        with open(f"{CACHE}/target_screen") as f:
            ecran = f.read().strip()
    except OSError as e:
        sys.exit(f"geometrie inconnue ({e}) : lancer start.sh d'abord")
    marge = int(re.search(r"marge=(\d+)px", args).group(1))
    hauteur = re.search(r"hauteur=(\S+)", args).group(1)
    xr = subprocess.run(["xrandr", "--query"], capture_output=True, text=True).stdout
    m = re.search(rf"^{re.escape(ecran)} connected\D*?(\d+)x(\d+)\+\d+\+\d+", xr, re.M)
    if not m:
        sys.exit(f"ecran '{ecran}' introuvable dans xrandr")
    W, H = int(m[1]), int(m[2])
    if hauteur.endswith("px"):
        h_col = int(hauteur[:-2])
    else:                                   # repli de start.sh : "93%"
        h_col = int(H * float(hauteur.rstrip("%")) / 100)
    return h_col, int(W * LARGEUR_PCT / 100), marge, ecran


def lire_bus(nom):
    """Derniere reponse de fetch-<nom>.sh, deposee par publier.sh. Fichier
    absent (tout premier demarrage) ou illisible : panneau compte vide. Pas
    grave : il sera recalcule des que ce fetch aura repondu."""
    try:
        with open(os.path.join(BUS, f"{nom}.json")) as f:
            donnees = json.load(f)
        return donnees if isinstance(donnees, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def lire_tout_le_bus():
    return {p.bus: lire_bus(p.bus) for p in PANNEAUX}


def factices(recos=0, venir=0, groupes=4, mails=0, sections=1):
    """Donnees inventees au format des fetch-*.sh : titres courts (une
    ligne), mails avec leur ligne "expediteur · age"."""
    def decouper(n, paquets):
        paquets = min(paquets, n)
        return [n // paquets + (1 if k < n % paquets else 0) for k in range(paquets)] if n else []
    return {
        "recos": {"recommandations": [{"titre": f"Reco {k + 1}", "detail": ""} for k in range(recos)]},
        "venir": {"groupes": [{"items": [{}] * t} for t in decouper(venir, groupes)]},
        "digest": {"sections": [{"items": [{"meta": "x · 1 h"}] * t} for t in decouper(mails, sections)]},
    }


# ==========================================================================
#  SORTIES
# ==========================================================================
def affectations(res):
    """["h_reco=128", ..., "t_mail=false"] : les variables pour eww."""
    return ([f"h_{v}={x}" for v, x in zip(VARS, res["h"])] +
            [f"y_{v}={x}" for v, x in zip(VARS, res["y"])] +
            [f"t_{v}={'true' if t else 'false'}" for v, t in zip(VARS, res["tronque"])])


def pousser(res):
    """UN seul "eww update" pour toutes les variables : les panneaux
    changent de taille (et de signal de coupe) dans le meme rendu, sans
    etat intermediaire ou la colonne serait trop haute ou trop courte."""
    # RUST_LOG=error : le demon est lance avec RUST_LOG=debug (start.sh) et
    # le transmet aux scripts qu'il lance ; sans ca, ce "eww update" noierait
    # mise-en-page.log sous ses messages de debogage.
    subprocess.run([EWW, "update", *affectations(res)], timeout=5, check=False,
                   env={**os.environ, "RUST_LOG": "error"})


def afficher(res):
    print(f"{'':20}{'besoin':>8}{'hauteur':>9}{'%':>5}{'y':>6}")
    for i, p in enumerate(PANNEAUX):
        if res["replie"][i]:
            etat = "  replié (en-tête seul)"
        elif res["tronque"][i]:
            etat = "  tronqué (défile)"
        else:
            etat = ""
        print(f"{p.nom:20}{res['besoin'][i]:>8}{res['h'][i]:>9}"
              f"{round(100 * res['h'][i] / res['A']):>5}{res['y'][i]:>6}{etat}")
    total = sum(res["h"])
    fond = "" if total == res["A"] else f", tout replié : {res['A'] - total} px de fond d'écran"
    print(f"{'total':20}{'':>8}{total:>9}   (A = {res['A']}{fond})")
    print(f"\ncommande envoyée par --pousser :  eww update {' '.join(affectations(res))}")


# ==========================================================================
#  TEST
# ==========================================================================
def _cellule(h, tronque, replie):
    """Une case au format du tableau du brief : "222", "194▾" ou "replié"."""
    return "replié" if replie else f"{h}{'▾' if tronque else ''}"


def test():
    """Critere d'acceptation de l'etape 1 : tableau v9 du brief a +-2 px
    (hauteurs, replies et signes ▾), somme des hauteurs == A sauf si tout
    est replie ; plus la non-regression v8 et des invariants."""
    ok = True
    h_col_917 = 917 + BANDEAU + len(PANNEAUX) * ECART   # colonne ou A = 917

    print("1) Tableau de référence du brief v9, section 3 (ses constantes, A = 917)")
    print("   ▾ = tronqué ; mails comptés sans titre de section, comme le brief\n")
    normale = dict(recos=3, venir=7, mails=9)
    chargee = dict(recos=5, venir=12, mails=20)
    cas = [  # (situation, compteurs, replies, attendu au format du brief)
        ("Normale 3/7/9", normale, set(), ("222", "358", "336")),
        ("… reco replié", normale, {"reco"}, ("replié", "452", "430")),
        ("Chargée 5/12/20", chargee, set(), ("194▾", "313▾", "410▾")),
        ("… reco replié", chargee, {"reco"}, ("replié", "379▾", "504▾")),
        ("… tout replié sauf mails", chargee, {"reco", "venir"}, ("replié", "replié", "849")),
        # Pas dans le tableau du brief : le mode bureau calme (section 2).
        ("Tout replié", normale, set(VARS), ("replié", "replié", "replié")),
    ]
    print(f"{'situation':28}{'obtenu':>28}{'attendu':>28}   somme   verdict")
    for nom, compteurs, replies, attendu in cas:
        res = calculer(factices(**compteurs), BRIEF_V9, h_col_917, 633, 26, frozenset(replies))
        obtenu = tuple(_cellule(*x) for x in zip(res["h"], res["tronque"], res["replie"]))
        bon = True
        for o, a, h in zip(obtenu, attendu, res["h"]):
            if a == "replié":
                bon &= o == "replié" and h == BRIEF_V9.replie
            else:
                # meme signe ▾ (ou absence de signe), hauteur a +-2 px
                bon &= o.endswith("▾") == a.endswith("▾") and o != "replié" \
                       and abs(h - int(a.rstrip("▾"))) <= 2
        somme = sum(res["h"])
        attendue = 917 if any(not r for r in res["replie"]) else len(PANNEAUX) * BRIEF_V9.replie
        bon &= somme == attendue
        ok &= bon
        print(f"{nom:28}{' / '.join(obtenu):>28}{' / '.join(attendu):>28}"
              f"{somme:>8}   {'OK' if bon else 'ÉCHEC'}")

    print("\n2) Non-régression : rien de replié, constantes du brief v8, A = 917")
    print("   (l'algorithme doit donner exactement ce qu'il donnait avant le repli)\n")
    cas = [  # (situation, compteurs, valeurs obtenues avant cette etape)
        ("Tous vides", {}, (306, 306, 305)),
        ("Journée normale", dict(recos=3, venir=7, mails=9), (215, 351, 351)),
        ("Mails pleins, reste vide", dict(mails=25), (90, 90, 737)),
        ("Tous pleins", dict(recos=5, venir=14, mails=25), (174, 301, 442)),
    ]
    print(f"{'situation':28}{'obtenu':>18}{'avant':>18}   verdict")
    for nom, compteurs, avant in cas:
        h = tuple(calculer(factices(**compteurs), BRIEF_V8, h_col_917, 633, 26)["h"])
        bon = h == avant
        ok &= bon
        print(f"{nom:28}{str(h):>18}{str(avant):>18}   {'OK' if bon else 'ÉCHEC'}")

    print("\n3) Invariants, constantes réelles, écran 1080 et 768 (marge 20),")
    print("   pour chacune des combinaisons de panneaux repliés")
    # Toutes les combinaisons de replies : {}, {reco}, {venir}, ... {tout}
    combinaisons = [frozenset(v for k, v in enumerate(VARS) if masque >> k & 1)
                    for masque in range(2 ** len(VARS))]
    n = 0
    for h_col in (1040, 728):
        A = h_col - BANDEAU - len(PANNEAUX) * ECART
        for r in range(0, 13, 2):
            for v in range(0, 31, 3):
                for m in range(0, 41, 3):
                    donnees = factices(recos=r, venir=v, mails=m)
                    res = {rep: calculer(donnees, REELLES, h_col, 633, 20, rep)
                           for rep in combinaisons}
                    for rep, x in res.items():
                        n += 1
                        h, b = x["h"], x["besoin"]
                        ouv = [i for i, p in enumerate(PANNEAUX) if p.var not in rep]
                        A_o = A - REELLES.replie * (len(PANNEAUX) - len(ouv))
                        erreurs = []
                        if any(h[i] != REELLES.replie for i in range(len(h)) if i not in ouv):
                            erreurs.append("un replié ne fait pas HAUTEUR_ENTETE")
                        if any(t for i, t in enumerate(x["tronque"]) if i not in ouv):
                            erreurs.append("un replié est marqué tronqué")
                        if ouv and sum(h) != A:
                            erreurs.append(f"somme {sum(h)} != A {A}")
                        if not ouv and sum(h) != len(PANNEAUX) * REELLES.replie:
                            erreurs.append("tout replié : somme != n x en-tête")
                        if any(h[i] < REELLES.plancher for i in ouv):
                            erreurs.append("un ouvert est sous le plancher")
                        if sum(max(REELLES.plancher, b[i]) for i in ouv) <= A_o \
                                and any(h[i] < b[i] for i in ouv):
                            erreurs.append("tronqué alors que tout tient")
                        if any(x["y"][i + 1] != x["y"][i] + h[i] + ECART for i in range(len(h) - 1)):
                            erreurs.append("y incohérents")
                        # Le repli DONNE de la place : replier un panneau de
                        # plus ne retrecit aucun des autres (a 1 px
                        # d'arrondi pres). Vrai tant que HAUTEUR_ENTETE <
                        # plancher : le replie rend toujours plus qu'il ne
                        # garde.
                        for var in VARS:
                            if var in rep:
                                continue
                            apres = res[rep | {var}]["h"]
                            if any(apres[i] < h[i] - 1 for i in ouv if VARS[i] != var):
                                erreurs.append(f"replier {var} rétrécit un autre panneau")
                        if erreurs:
                            ok = False
                            print(f"  ÉCHEC r={r} v={v} m={m} h_col={h_col} "
                                  f"repliés={sorted(rep)} : {', '.join(erreurs)}")
    vides = calculer(factices(), REELLES, 1040, 633, 20)["h"]
    parts = max(vides) - min(vides) <= 1
    ok &= parts
    print(f"  {n} cas : repliés à {REELLES.replie} px, somme == A (sauf tout replié),")
    print(f"  jamais sous le plancher ({REELLES.plancher} px), personne n'est tronqué quand")
    print("  tout tient, y cohérents, replier ne rétrécit jamais un autre panneau.")
    print(f"  Tous vides, écran 1080 : {vides} -> {'parts égales' if parts else 'ÉCHEC'}")
    print("\nRÉSULTAT :", "tout est OK" if ok else "ÉCHEC")
    return ok


def liste_replies(texte):
    """Argument --replies : "reco,venir" -> frozenset({"reco", "venir"})."""
    noms = frozenset(x.strip() for x in texte.split(",") if x.strip())
    inconnus = noms - set(VARS)
    if inconnus:
        raise argparse.ArgumentTypeError(
            f"panneau inconnu : {', '.join(sorted(inconnus))} (choix : {', '.join(VARS)})")
    return noms


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", nargs="?", choices=("test", "simuler"))
    p.add_argument("--recos", type=int, default=0)
    p.add_argument("--venir", type=int, default=0, help="nombre d'items à venir")
    p.add_argument("--groupes", type=int, default=4, help="répartis en N groupes")
    p.add_argument("--mails", type=int, default=0)
    p.add_argument("--sections", type=int, default=1, help="mails répartis en N sections")
    p.add_argument("--replies", type=liste_replies, default=frozenset(),
                   help=f"panneaux repliés, séparés par des virgules ({', '.join(VARS)})")
    p.add_argument("--pousser", action="store_true",
                   help="envoyer le résultat à eww (utilisé par publier.sh)")
    a = p.parse_args()

    if a.mode == "test":
        sys.exit(0 if test() else 1)

    if a.pousser:
        # Etape 1 : le repli n'est pas encore branche sur eww. Refuser
        # plutot que pousser des hauteurs que le yuck ne sait pas afficher.
        if a.replies:
            p.error("--replies ne se combine pas encore avec --pousser (étapes 2-3)")
        # Au demarrage, les fetch finissent presque en meme temps et lancent
        # chacun un calcul. Le verrou les fait passer l'un APRES l'autre :
        # chacun relit le bus une fois son tour venu, donc le dernier a
        # passer voit forcement tous les fichiers a jour -- et c'est lui qui
        # ecrit en dernier dans eww.
        with open(os.path.join(CACHE, "mise-en-page.lock"), "w") as verrou:
            fcntl.flock(verrou, fcntl.LOCK_EX)
            h_col, largeur, marge, _ = geometrie()
            res = calculer(lire_tout_le_bus(), REELLES, h_col, largeur, marge)
            pousser(res)
            print(" ".join(affectations(res)))      # -> mise-en-page.log
        return

    h_col, largeur, marge, ecran = geometrie()
    if a.mode == "simuler":
        donnees = factices(a.recos, a.venir, a.groupes, a.mails, a.sections)
        origine = "données simulées"
    else:
        donnees = lire_tout_le_bus()
        origine = "données actuelles des panneaux"
    res = calculer(donnees, REELLES, h_col, largeur, marge, a.replies)
    replies = f", repliés : {', '.join(v for v in VARS if v in a.replies)}" if a.replies else ""
    print(f"Écran {ecran} : colonne {largeur} x {h_col} px, marge {marge} px, "
          f"A = {res['A']} px — {origine}{replies}\n")
    afficher(res)


if __name__ == "__main__":
    main()
