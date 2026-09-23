# À faire — dashboard PAI

Liste des sujets **reportés** : décidés « plus tard », ou en attente d'une décision de Gauthier.
Chaque point garde son contexte, pour qu'on puisse le reprendre sans tout redécouvrir.
Un point réglé est **supprimé** de ce fichier (l'historique git en garde la trace).

---

## À venir (agenda + tâches)

### Plusieurs agendas
Le webhook agenda ne renvoie aujourd'hui qu'un agenda (`sourceCalendar: "Personnal"`).
D'autres viendront : « work », et des agendas partagés par d'autres personnes.
- **Doublons** : un même évènement présent dans deux agendas (une invitation) apparaîtra
  deux fois. À dédoublonner (côté n8n, ou dans `fetch-venir.sh`), par exemple sur titre + heure de début.
- **Agendas partagés** : tous leurs évènements, ou seulement ceux auxquels Gauthier
  participe ?
- Aucune distinction visuelle par agenda : la couleur est réservée au sens (urgent, retard).

### Évènements annulés
Pour l'instant ils sont affichés (`status: "cancelled"`), sans signe distinctif.
Décision de Gauthier (23/09) : on verra plus tard. Le filtre tient en une ligne dans
`fetch-venir.sh` (le champ `status` arrive déjà du webhook).

---

## Veille

- **« N à lire »** compte aujourd'hui **tous** les items, pas seulement les neufs. Voulu ?
- **Sens de `neuf`** : eww ne renvoie aucun clic à n8n, donc « neuf » ne peut pas vouloir dire
  « pas encore ouvert ». Moins de 24 h ? Pas encore vu par n8n ?
- **Workflow n8n** à construire par Gauthier. La curation (IA) doit tourner sur un planning
  et remplir une table ; le webhook ne fait que la relire (limite de 8 s de `curl`).

---

## Tous les panneaux

### Plafonds du nombre d'items
Les plafonds du brief (3 / 7 / 7 / 4) ne suffisent pas avec les vraies constantes
(A = 992 px sur HDMI-1-1) : simulés, les quatre panneaux sont tronqués (besoins
193 + 344 + 359 + 170 = 1066 px). Pour À venir, un titre de groupe coûte 30 px, une ligne
22 px. Chiffres à choisir par Gauthier ; outil : `python3 mise-en-page.py simuler --help`.

### Comportement quand n8n est injoignable
Aujourd'hui le panneau se **vide** (« n8n injoignable » ; pour À venir, seules les tâches
restent, avec « agenda injoignable ») et son heure de synchro reste
à jour, au lieu de garder la dernière réponse et de laisser l'heure vieillir.
(`fetch-meteo.sh` garde déjà la dernière réponse : modèle possible.) À décider.

### Contrat n8n ↔ eww
Écrire les fiches « Veille » et « À venir » dans `docs/contrat-bus-n8n.md` (proposé le 23/09).
Pour À venir, le contrat est désormais simple : n8n renvoie les évènements BRUTS de sa table
(`title`, `startDate`, `endDate`) ; `fetch-venir.sh` groupe et lit Taskwarrior en local.

---

## Écarts connus avec les briefs
- `BRIEF-refonte-colonne.md` (v9) est dans `~/Downloads`, pas dans le dépôt.
- Constantes réelles ≠ brief : ligne de veille 22 px (brief : 26), en-tête replié 59 px
  (brief : 34), A = 992 px (brief : 904).
- Le bandeau du bas a été supprimé le 15/09 ; le brief le décrit encore.
- Le digest nomme son heure `sync`, les autres panneaux `synchro`.
