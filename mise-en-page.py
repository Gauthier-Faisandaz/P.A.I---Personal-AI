#!/usr/bin/env python3
"""
mise-en-page.py - calcule la hauteur de chaque panneau de la colonne eww
(recommandations, a venir, boite de reception) et la position verticale
(y) de leur bord haut.

Pourquoi un script : eww ne sait pas dire ou GTK a place un widget a
l'ecran. En calculant nous-memes les hauteurs, on connait aussi les y, et
la modale (etape 5) pourra s'aligner sur le haut de son panneau.

Usage :
  mise-en-page.py          lit les donnees actuelles des panneaux (le bus :
                           ~/.cache/eww/bus/*.json) et affiche le resultat,
                           sans rien envoyer a eww.
  mise-en-page.py --pousser
                           meme calcul, puis envoie a eww les hauteurs
                           (h_reco h_venir h_mail), les positions (y_*) et
                           les indicateurs de coupe (t_* : true/false).
                           Lance par publier.sh apres chaque fetch-*.sh.
  mise-en-page.py test     verifie l'algorithme sur le tableau de reference
                           du brief (section 3), plus des invariants.
  mise-en-page.py simuler --recos 3 --venir 7 --groupes 4 --mails 9
                           meme calcul sur des donnees inventees.
"""
import argparse
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

SECTION_MARGE = 12     # $section-marge, sous chaque groupe SAUF le dernier
LIGNE_PAD = 2          # $ligne-pad, en haut ET en bas d'une ligne
RECO_TETE_MARGE = 2    # $reco-tete-marge
RECO_MARGE = 12        # $reco-marge, sous chaque reco SAUF la derniere
RECO_BAS = 8 + BORDURE + RECO_MARGE   # $reco-pad-bas + bordure + $reco-marge
RECO_PUCE = CHASSE_12 + 8             # le "●" + $reco-puce-marge
RECO_RETRAIT = 18      # $reco-detail-retrait

# Decoration sans texte sous le dernier element de chaque panneau (reco,
# a venir, mails) : on peut la rogner sans que le panneau soit "tronque".
DECOR_FIN = (8 + BORDURE, LIGNE_PAD, LIGNE_PAD)   # $reco-pad-bas + trait ; $ligne-pad

BANDEAU = 38 + 2 * BORDURE            # $bandeau-haut + bordures
ECART = 16             # :spacing de la box "colonne" (eww.yuck)
LARGEUR_PCT = 33       # :width "33%" de la fenetre colonne (eww.yuck)


@dataclass
class Constantes:
    """Hauteurs (px) des briques d'un panneau. Deux jeux : les valeurs
    reelles (tirees de eww.scss, ci-dessus) et celles du brief, qui ne
    servent qu'a verifier l'algorithme contre son tableau de reference."""
    habillage: int           # bordures + padding + en-tete + separateur
    ligne_vide: int          # "Aucune recommandation..." / "Rien a venir."
    section_titre: int       # "► À TRAITER", "► DEMAIN · ven. 11"
    section_marge: int       # espace sous chaque groupe
    ligne_mail: int          # sujet + ligne "expediteur · age"
    ligne_mail_sans_meta: int
    ligne_venir: int
    reco_base: int           # reco avec un titre d'UNE ligne, sans detail
    reco_ligne_titre: int    # chaque ligne de titre en plus
    reco_ligne_detail: int   # chaque ligne de detail
    reco_marge: int          # marge comprise dans reco_base, absente sous
                             # la derniere reco (":last-child" dans eww.scss)

    @property
    def plancher(self):
        # Hauteur minimale d'un panneau = celle d'un panneau vide (en-tete
        # + une ligne). Choisie EGALE pour les trois panneaux : c'est ce
        # qui fait tomber trois panneaux vides exactement sur un tiers.
        return self.habillage + self.ligne_vide


REELLES = Constantes(
    habillage=HABILLAGE,
    ligne_vide=LIGNE_15,
    section_titre=LIGNE_15,
    section_marge=SECTION_MARGE,
    ligne_mail=2 * LIGNE_PAD + LIGNE_15 + LIGNE_12,     # 37
    ligne_mail_sans_meta=2 * LIGNE_PAD + LIGNE_15,      # 22
    ligne_venir=2 * LIGNE_PAD + LIGNE_15,               # 22
    reco_base=LIGNE_15 + RECO_TETE_MARGE + RECO_BAS,    # 41
    reco_ligne_titre=LIGNE_15,
    reco_ligne_detail=LIGNE_13,
    reco_marge=RECO_MARGE,
)

# Valeurs du brief (section 4) : en-tete 34 + padding 16, ligne vide 26...
BRIEF = Constantes(
    habillage=34 + 16, ligne_vide=26, section_titre=22, section_marge=0,
    ligne_mail=26, ligne_mail_sans_meta=26, ligne_venir=24,
    reco_base=40, reco_ligne_titre=18, reco_ligne_detail=17, reco_marge=0,
)


# ==========================================================================
#  ALGORITHME DE REPARTITION (brief, section 3)
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


def repartir(A, besoins, plancher):
    """A = hauteur a partager entre les trois panneaux ; besoins = hauteur
    naturelle de chacun. Renvoie trois hauteurs entieres de somme A."""
    # Ecran trop petit pour garantir le plancher a tout le monde : tiers.
    if A <= 3 * plancher:
        return arrondir([A / 3] * 3, A)
    # 1. ce que chaque panneau reclame
    h = [max(plancher, b) for b in besoins]
    S = sum(h)
    if S < A:
        # 2. personne ne remplit : le surplus est partage egalement
        h = [x + (A - S) / 3 for x in h]
    elif S > A:
        # 3. ca deborde : on rogne au prorata du "gras" de chacun (ce qu'il
        #    a au-dessus du plancher). Jamais sous le plancher : le total du
        #    gras (S - 3 x plancher) depasse toujours l'exces (S - A).
        gras = [x - plancher for x in h]
        h = [x - (S - A) * g / sum(gras) for x, g in zip(h, gras)]
    return arrondir(h, A)


# ==========================================================================
#  BESOIN DE CHAQUE PANNEAU (a partir des memes JSON que eww)
# ==========================================================================
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


def besoin_venir(venir, c):
    groupes = venir.get("groupes") or []
    if not groupes:
        return c.habillage + c.ligne_vide
    return c.habillage - c.section_marge + sum(   # pas de marge sous le dernier
        c.section_titre + len(g.get("items") or []) * c.ligne_venir + c.section_marge
        for g in groupes)


def besoin_mails(digest, c):
    sections = digest.get("sections") or []
    if not sections:
        return c.habillage + c.ligne_vide      # "Aucun mail."
    total = c.habillage
    for s in sections:
        total += c.section_titre + c.section_marge
        for it in s.get("items") or []:
            total += c.ligne_mail if it.get("meta") else c.ligne_mail_sans_meta
    return total - c.section_marge             # pas de marge sous la derniere


def calculer(recos, venir, digest, c, hauteur_colonne, largeur, marge):
    """Tout le calcul : besoins -> hauteurs -> positions y."""
    A = hauteur_colonne - BANDEAU - 3 * ECART
    besoins = [besoin_recos(recos, c, largeur),
               besoin_venir(venir, c),
               besoin_mails(digest, c)]
    h = repartir(A, besoins, c.plancher)
    # y[i] = marge + somme des (h[j] + ecart) pour j < i
    y = [marge, marge + h[0] + ECART, marge + h[0] + h[1] + 2 * ECART]
    # Tronque = du TEXTE est cache. Rogner seulement la decoration sous le
    # dernier element (padding + trait d'une reco, padding d'une ligne)
    # ne cache rien de lisible : pas de chevron ni de degrade pour ca.
    return {"A": A, "besoin": besoins, "h": h, "y": y,
            "tronque": [bi - hi > tol for hi, bi, tol in zip(h, besoins, DECOR_FIN)]}


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


def factices(recos=0, venir=0, groupes=4, mails=0, sections=1):
    """Donnees inventees au format des fetch-*.sh : titres courts (une
    ligne), mails avec leur ligne "expediteur · age"."""
    def decouper(n, paquets):
        paquets = min(paquets, n)
        return [n // paquets + (1 if k < n % paquets else 0) for k in range(paquets)] if n else []
    return (
        {"recommandations": [{"titre": f"Reco {k + 1}", "detail": ""} for k in range(recos)]},
        {"groupes": [{"items": [{}] * t} for t in decouper(venir, groupes)]},
        {"sections": [{"items": [{"meta": "x · 1 h"}] * t} for t in decouper(mails, sections)]},
    )


# ==========================================================================
#  SORTIES
# ==========================================================================
NOMS = ("Recommandations", "À venir", "Boîte de réception")
VARS = ("reco", "venir", "mail")


def affectations(res):
    """["h_reco=128", ..., "t_mail=false"] : les neuf variables pour eww."""
    return ([f"h_{v}={x}" for v, x in zip(VARS, res["h"])] +
            [f"y_{v}={x}" for v, x in zip(VARS, res["y"])] +
            [f"t_{v}={'true' if t else 'false'}" for v, t in zip(VARS, res["tronque"])])


def pousser(res):
    """UN seul "eww update" pour toutes les variables : les trois panneaux
    changent de taille (et de signal de coupe) dans le meme rendu, sans
    etat intermediaire ou la colonne serait trop haute ou trop courte."""
    subprocess.run([EWW, "update", *affectations(res)], timeout=5, check=False)


def afficher(res):
    print(f"{'':20}{'besoin':>8}{'hauteur':>9}{'%':>5}{'y':>6}")
    for i, nom in enumerate(NOMS):
        coupe = "  tronqué (défile)" if res["tronque"][i] else ""
        print(f"{nom:20}{res['besoin'][i]:>8}{res['h'][i]:>9}"
              f"{round(100 * res['h'][i] / res['A']):>5}{res['y'][i]:>6}{coupe}")
    print(f"{'total':20}{'':>8}{sum(res['h']):>9}   (A = {res['A']})")
    print(f"\ncommande envoyée par --pousser :  eww update {' '.join(affectations(res))}")


def test():
    """Critere d'acceptation de l'etape 1 : tableau du brief a +-2 px, et
    somme des hauteurs == A dans tous les cas."""
    ok = True
    print("1) Tableau de référence du brief (ses constantes, A = 917)\n")
    cas = [  # (situation, compteurs, valeurs attendues)
        ("Tous vides", {}, (306, 306, 306)),
        ("Journée normale", dict(recos=3, venir=7, groupes=4, mails=9), (215, 351, 351)),
        ("Mails pleins, reste vide", dict(mails=25), (90, 90, 736)),
        ("Tous pleins", dict(recos=5, venir=14, groupes=4, mails=25), (174, 301, 441)),
    ]
    print(f"{'situation':26}{'obtenu':>18}{'attendu':>18}   verdict")
    for nom, compteurs, attendu in cas:
        # hauteur de colonne telle que A = 917 (bandeau et ecarts reels)
        res = calculer(*factices(**compteurs), BRIEF, 917 + BANDEAU + 3 * ECART, 633, 26)
        h = res["h"]
        bon = all(abs(a - b) <= 2 for a, b in zip(h, attendu)) and sum(h) == 917
        ok &= bon
        print(f"{nom:26}{str(tuple(h)):>18}{str(attendu):>18}   {'OK' if bon else 'ÉCHEC'}")

    print("\n2) Invariants, constantes réelles, écran 1080 et 768 (marge 20)")
    n = 0
    for h_col in (1040, 728):
        A = h_col - BANDEAU - 3 * ECART
        for r in range(0, 13):
            for v in range(0, 31, 2):
                for m in range(0, 41, 2):
                    res = calculer(*factices(recos=r, venir=v, mails=m), REELLES, h_col, 633, 20)
                    h, b = res["h"], res["besoin"]
                    n += 1
                    erreurs = []
                    if sum(h) != A:
                        erreurs.append(f"somme {sum(h)} != A {A}")
                    if min(h) < REELLES.plancher:
                        erreurs.append("sous le plancher")
                    if sum(max(REELLES.plancher, x) for x in b) <= A and any(hi < bi for hi, bi in zip(h, b)):
                        erreurs.append("tronqué alors que tout tient")
                    if erreurs:
                        ok = False
                        print(f"  ÉCHEC r={r} v={v} m={m} h_col={h_col} : {', '.join(erreurs)}")
    vides = calculer(*factices(), REELLES, 1040, 633, 20)["h"]
    tiers = max(vides) - min(vides) <= 1
    ok &= tiers
    print(f"  {n} cas : somme == A, jamais sous le plancher ({REELLES.plancher} px),")
    print("  personne n'est tronqué quand tout tient.")
    print(f"  Tous vides, écran 1080 : {vides} -> {'tiers exacts' if tiers else 'ÉCHEC'}")
    print("\nRÉSULTAT :", "tout est OK" if ok else "ÉCHEC")
    return ok


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", nargs="?", choices=("test", "simuler"))
    p.add_argument("--recos", type=int, default=0)
    p.add_argument("--venir", type=int, default=0, help="nombre d'items à venir")
    p.add_argument("--groupes", type=int, default=4, help="répartis en N groupes")
    p.add_argument("--mails", type=int, default=0)
    p.add_argument("--sections", type=int, default=1, help="mails répartis en N sections")
    p.add_argument("--pousser", action="store_true",
                   help="envoyer le résultat à eww (utilisé par publier.sh)")
    a = p.parse_args()

    if a.mode == "test":
        sys.exit(0 if test() else 1)

    if a.pousser:
        # Au demarrage, les trois fetch finissent presque en meme temps et
        # lancent chacun un calcul. Le verrou les fait passer l'un APRES
        # l'autre : chacun relit le bus une fois son tour venu, donc le
        # dernier a passer voit forcement les trois fichiers a jour -- et
        # c'est lui qui ecrit en dernier dans eww.
        with open(os.path.join(CACHE, "mise-en-page.lock"), "w") as verrou:
            fcntl.flock(verrou, fcntl.LOCK_EX)
            h_col, largeur, marge, _ = geometrie()
            res = calculer(lire_bus("recos"), lire_bus("venir"), lire_bus("digest"),
                           REELLES, h_col, largeur, marge)
            pousser(res)
            print(" ".join(affectations(res)))      # -> mise-en-page.log
        return

    h_col, largeur, marge, ecran = geometrie()
    if a.mode == "simuler":
        donnees = factices(a.recos, a.venir, a.groupes, a.mails, a.sections)
        origine = "données simulées"
    else:
        donnees = (lire_bus("recos"), lire_bus("venir"), lire_bus("digest"))
        origine = "données actuelles des panneaux"
    res = calculer(*donnees, REELLES, h_col, largeur, marge)
    print(f"Écran {ecran} : colonne {largeur} x {h_col} px, marge {marge} px, "
          f"A = {res['A']} px — {origine}\n")
    afficher(res)


if __name__ == "__main__":
    main()
