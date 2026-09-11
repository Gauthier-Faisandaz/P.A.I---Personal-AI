#!/usr/bin/env python3
"""
mise-en-page.py - calcule la hauteur de chaque panneau de la colonne eww
(recommandations, a venir, boite de reception) et la position verticale
(y) de leur bord haut.

Un panneau peut etre REPLIE (clic sur son en-tete) : il ne garde que son
en-tete (HAUTEUR_ENTETE) et sort du partage ; les panneaux ouverts se
repartissent la place avec exactement le meme algorithme qu'avant,
applique a eux seuls. Le defaut reste "tout ouvert" : le repli est une
exception, pas un accordeon.

Pourquoi un script : eww ne sait pas dire ou GTK a place un widget a
l'ecran. En calculant nous-memes les hauteurs, on connait aussi les y, et
la modale peut s'aligner sur le haut de son panneau.

Usage :
  mise-en-page.py          lit les donnees actuelles des panneaux (le bus :
                           ~/.cache/eww/bus/*.json) et l'etat de repli
                           actuel, affiche le resultat, sans rien envoyer.
  mise-en-page.py --replies reco,venir
                           meme chose, en supposant CES panneaux replies
                           (noms : reco, venir, mail ; "" = aucun).
  mise-en-page.py --pousser
                           meme calcul, puis envoie a eww les hauteurs
                           (h_*), les positions (y_*), les indicateurs de
                           coupe (t_*) et de repli (r_*). Lance par
                           publier.sh apres chaque fetch-*.sh.
  mise-en-page.py --basculer reco
                           replie ce panneau s'il est ouvert, le deplie
                           sinon, puis pousse comme --pousser. Lance par un
                           clic sur l'en-tete du panneau (eww.yuck).
                           L'etat est garde dans ~/.cache/pai/replies.json :
                           il survit aux redemarrages d'eww et du PC.
                           Replier la boite de reception ferme la modale
                           mail si elle est ouverte.
  mise-en-page.py test     verifie l'algorithme sur le tableau de reference
                           du brief v9 (section 3), plus des invariants.
  mise-en-page.py simuler --recos 3 --venir 7 --groupes 4 --mails 9 [--replies reco]
                           meme calcul sur des donnees inventees.
"""
import argparse
import contextlib
import dataclasses
import fcntl
import io
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import textwrap
from dataclasses import dataclass

EWW = os.path.expanduser("~/.cargo/bin/eww")
UI = os.path.expanduser("~/.config/eww/ui.sh")       # ouvre / ferme la modale
CACHE = os.path.expanduser("~/.cache/eww")
BUS = os.path.join(CACHE, "bus")          # rempli par publier.sh
# Etat de repli : une PREFERENCE d'affichage, gardee sur disque pour
# survivre aux redemarrages (les variables eww repartent de zero a chaque
# lancement du demon). Dossier a part, ~/.cache/pai, et non le bus : c'est
# un etat d'INTERFACE, ecrit par ce script seul, jamais lu par n8n.
REPLIES = os.path.expanduser("~/.cache/pai/replies.json")
# RUST_LOG=error : le demon est lance avec RUST_LOG=debug (start.sh) et le
# transmet aux scripts qu'il lance ; sans ca, chaque appel a eww noierait
# mise-en-page.log sous ses messages de debogage.
ENV_EWW = {**os.environ, "RUST_LOG": "error"}


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
# sous l'en-tete ($entete-marge) : il n'y a plus rien dessous, et eww.scss
# la retire (regle ".panel.replie .header"). Reporte dans eww.scss (bloc
# CONSTANTES, "panneau replie").
HAUTEUR_ENTETE = 2 * BORDURE + 2 * PANNEAU_PAD_V + LIGNE_24         # 59

SECTION_MARGE = 12     # $section-marge, sous chaque groupe SAUF le dernier
LIGNE_PAD = 2          # $ligne-pad, en haut ET en bas d'une ligne
RECO_TETE_MARGE = 2    # $reco-tete-marge
RECO_MARGE = 12        # $reco-marge, sous chaque reco SAUF la derniere
RECO_BAS = 8 + BORDURE + RECO_MARGE   # $reco-pad-bas + bordure + $reco-marge
RECO_PUCE = CHASSE_12 + 8             # le "●" + $reco-puce-marge
RECO_RETRAIT = 18      # $reco-detail-retrait

BANDEAU = 38 + 2 * BORDURE            # $bandeau-haut + bordures
ECART = 16             # :spacing des box "colonne" et "panneaux" (eww.yuck)
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
    var: str          # suffixe des variables eww : h_ y_ t_ r_<var>
    nom: str          # pour l'affichage
    bus: str          # fichier du bus : ~/.cache/eww/bus/<bus>.json
    besoin: object    # fonction (donnees, constantes, largeur) -> px
    decor_fin: int    # decoration sans texte sous le dernier element : on
                      # peut la rogner sans que le panneau soit "tronque"
    modale: bool = False   # ses lignes ouvrent la modale (ui.sh) : le
                           # replier la ferme (voir fermer_modale)


PANNEAUX = (
    Panneau("reco", "Recommandations", "recos", besoin_recos,
            8 + BORDURE),     # $reco-pad-bas + trait
    Panneau("venir", "À venir", "venir", besoin_venir, LIGNE_PAD),
    Panneau("mail", "Boîte de réception", "digest", besoin_mails, LIGNE_PAD,
            modale=True),
)
VARS = tuple(p.var for p in PANNEAUX)
PAR_NOM = {p.var: p for p in PANNEAUX}


def calculer(donnees, c, hauteur_colonne, largeur, marge, replies=frozenset()):
    """Tout le calcul : besoins -> hauteurs -> positions y.
    donnees = {nom du bus: JSON} ; replies = ensemble de noms de PANNEAUX
    (VARS) replies."""
    n = len(PANNEAUX)
    # n panneaux + le bandeau, separes par n ecarts (voir la fenetre
    # colonne dans eww.yuck).
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
#  ENTREES : geometrie de l'ecran, donnees des panneaux, etat de repli
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


def lire_replies(chemin=REPLIES):
    """Panneaux replies, lus dans le fichier d'etat : {"replies": ["reco"]}.

    C'est la SEULE source de verite. Les variables r_* d'eww n'en sont que
    le reflet, repousse a chaque calcul : c'est ce qui restaure l'etat au
    demarrage, sans rien ajouter a start.sh (ouvrir-colonne.sh lance un
    calcul juste apres avoir ouvert la colonne, eww-watchdog.sh aussi).

    Fichier absent (jamais rien replie) : tout ouvert. Fichier abime : tout
    ouvert aussi, avec un message dans mise-en-page.log -- le defaut, sans
    risque, plutot qu'une colonne qui ne s'affiche plus. Un nom inconnu
    (panneau renomme ou supprime) est ignore."""
    try:
        with open(chemin) as f:
            donnees = json.load(f)
        noms = donnees.get("replies") if isinstance(donnees, dict) else None
        if not isinstance(noms, list):
            raise ValueError('pas de liste "replies"')
    except FileNotFoundError:
        return frozenset()
    except (OSError, ValueError) as e:      # ValueError couvre le JSON invalide
        print(f"{chemin} illisible ({e}) : tout ouvert", file=sys.stderr)
        return frozenset()
    return frozenset(n for n in noms if n in VARS)


def ecrire_replies(replies, chemin=REPLIES):
    """Ecrit le fichier d'etat. Fichier temporaire puis os.replace
    (instantane, comme le "mv" de publier.sh) : une lecture ne tombe jamais
    sur un fichier a moitie ecrit, meme si le PC s'eteint pendant
    l'ecriture. Les noms sont ranges dans l'ordre des panneaux, pour que le
    fichier reste lisible a l'oeil."""
    os.makedirs(os.path.dirname(chemin), exist_ok=True)
    tmp = chemin + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"replies": [v for v in VARS if v in replies]}, f)
        f.write("\n")
    os.replace(tmp, chemin)


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
    """["h_reco=128", ..., "r_mail=false"] : les variables pour eww."""
    return ([f"h_{v}={x}" for v, x in zip(VARS, res["h"])] +
            [f"y_{v}={x}" for v, x in zip(VARS, res["y"])] +
            [f"t_{v}={'true' if t else 'false'}" for v, t in zip(VARS, res["tronque"])] +
            [f"r_{v}={'true' if r else 'false'}" for v, r in zip(VARS, res["replie"])])


def pousser(res):
    """UN seul "eww update" pour toutes les variables : au repli, le
    chevron, le corps qui disparait et les nouvelles hauteurs arrivent dans
    le meme rendu, sans etat intermediaire ou la colonne serait trop haute
    ou trop courte."""
    subprocess.run([EWW, "update", *affectations(res)], timeout=5, check=False,
                   env=ENV_EWW)


def fermer_modale():
    """Ferme la modale mail si elle est ouverte (etape 4 du repli).

    Pourquoi la fermer : la modale fige son y a l'ouverture (ui.sh, bord
    haut aligne sur le panneau mails). Si ce panneau se replie, elle
    resterait accrochee dans le vide, a cote d'un simple en-tete. La fermer
    est plus simple et plus sur que la deplacer.

    On passe par "ui.sh close", le seul endroit qui sait la fermer
    proprement : la fenetre ET la variable mail_modale (qui marque la ligne
    choisie). Et seulement si elle est ouverte : "eww close" est justement
    le genre d'appel sur lequel eww peut se bloquer (bug #451), inutile
    d'en lancer un pour rien. Delais courts (1 + 1 + 2 s) : le tout doit
    tenir dans le :timeout "5s" du clic. Demon bloque : on abandonne ;
    eww-watchdog.sh relancera eww, et ouvrir-colonne.sh ferme alors la
    modale de toute facon."""
    try:
        fenetres = subprocess.run([EWW, "active-windows"], capture_output=True,
                                  text=True, timeout=1, env=ENV_EWW).stdout
        choisi = subprocess.run([EWW, "get", "mail_modale"], capture_output=True,
                                text=True, timeout=1, env=ENV_EWW).stdout.strip()
        if re.search(r"^modale:", fenetres, re.M) or choisi:
            subprocess.run(["bash", UI, "close"], timeout=2, check=False, env=ENV_EWW,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("modale fermée (panneau d'origine replié)")    # -> mise-en-page.log
    except subprocess.TimeoutExpired:
        print("eww ne répond pas : modale non fermée", file=sys.stderr)


def mettre_a_jour(basculer=None):
    """--pousser (basculer=None) et --basculer <var> : relit tout, bascule
    eventuellement un panneau, recalcule, pousse.

    Tout se fait sous verrou. Au demarrage, les fetch finissent presque en
    meme temps et lancent chacun un calcul ; un clic sur un en-tete peut
    aussi tomber pendant un calcul. Le verrou les fait passer l'un APRES
    l'autre : chacun relit le bus ET l'etat de repli une fois son tour
    venu, donc aucun ne pousse un etat perime par-dessus celui d'un autre
    (deux clics rapides replient puis deplient, sans s'annuler au hasard)."""
    with open(os.path.join(CACHE, "mise-en-page.lock"), "w") as verrou:
        fcntl.flock(verrou, fcntl.LOCK_EX)
        replies = lire_replies()
        if basculer:
            replies ^= {basculer}          # ^ = ajoute s'il manque, retire sinon
            # Ecrit AVANT de pousser : si eww ne repond pas, l'etat est quand
            # meme garde, et le prochain calcul l'appliquera.
            ecrire_replies(replies)
            # On vient de REPLIER le panneau d'ou vient la modale : la fermer
            # AVANT de changer les hauteurs, pour qu'elle ne reste pas un
            # instant a cote d'un panneau qui n'a plus de liste.
            if basculer in replies and PAR_NOM[basculer].modale:
                fermer_modale()
        h_col, largeur, marge, _ = geometrie()
        res = calculer(lire_tout_le_bus(), REELLES, h_col, largeur, marge, replies)
        pousser(res)
        print(" ".join(affectations(res)))      # -> mise-en-page.log


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

    print("\n4) Fichier d'état des repliés (dans un dossier temporaire, jamais le vrai)\n")
    with tempfile.TemporaryDirectory() as d:
        chemin = os.path.join(d, "pai", "replies.json")   # dossier pai absent : a creer
        verifs = [("fichier absent -> tout ouvert", lire_replies(chemin) == frozenset())]
        ecrire_replies(frozenset({"mail", "reco"}), chemin)
        verifs.append(("écrit puis relu (dossier créé)", lire_replies(chemin) == {"reco", "mail"}))
        with open(chemin) as f:
            verifs.append(("rangé dans l'ordre des panneaux",
                           json.load(f) == {"replies": ["reco", "mail"]}))
        verifs.append(("pas de fichier temporaire oublié", not os.path.exists(chemin + ".tmp")))
        ecrire_replies(frozenset(), chemin)
        verifs.append(("tout rouvert -> liste vide", lire_replies(chemin) == frozenset()))
        with open(chemin, "w") as f:
            f.write('{"replies": ["reco", "inconnu"]}')
        verifs.append(("nom inconnu ignoré", lire_replies(chemin) == {"reco"}))
        for nom, contenu in (("JSON abîmé -> tout ouvert", "{pas du json"),
                             ("mauvaise forme -> tout ouvert", '["reco"]')):
            with open(chemin, "w") as f:
                f.write(contenu)
            # le message "illisible" est attendu ici : on le fait taire
            with contextlib.redirect_stderr(io.StringIO()):
                verifs.append((nom, lire_replies(chemin) == frozenset()))
    for nom, bon in verifs:
        ok &= bon
        print(f"  {nom:40}{'OK' if bon else 'ÉCHEC'}")
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
    p.add_argument("--replies", type=liste_replies, default=None,
                   help=f"panneaux supposés repliés, séparés par des virgules "
                        f"({', '.join(VARS)}) ; sans cette option : l'état actuel "
                        f"(affichage) ou aucun (simuler)")
    p.add_argument("--pousser", action="store_true",
                   help="envoyer le résultat à eww (utilisé par publier.sh)")
    p.add_argument("--basculer", choices=VARS,
                   help="replier ce panneau s'il est ouvert, le déplier sinon, "
                        "puis pousser (clic sur un en-tête)")
    a = p.parse_args()

    if a.mode == "test":
        sys.exit(0 if test() else 1)

    if a.pousser or a.basculer:
        # --replies ne fait que SUPPOSER un etat, pour regarder : il ne doit
        # jamais partir dans eww. Pour replier pour de vrai : --basculer.
        if a.replies is not None:
            p.error("--replies sert à simuler ; pour replier pour de vrai : --basculer")
        mettre_a_jour(a.basculer)
        return

    h_col, largeur, marge, ecran = geometrie()
    if a.mode == "simuler":
        donnees = factices(a.recos, a.venir, a.groupes, a.mails, a.sections)
        replies = a.replies or frozenset()
        origine = "données simulées"
    else:
        donnees = lire_tout_le_bus()
        replies = lire_replies() if a.replies is None else a.replies
        origine = "données actuelles des panneaux"
    res = calculer(donnees, REELLES, h_col, largeur, marge, replies)
    texte = f", repliés : {', '.join(v for v in VARS if v in replies)}" if replies else ""
    print(f"Écran {ecran} : colonne {largeur} x {h_col} px, marge {marge} px, "
          f"A = {res['A']} px — {origine}{texte}\n")
    afficher(res)


if __name__ == "__main__":
    main()
