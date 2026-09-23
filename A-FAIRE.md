# À faire — dashboard PAI

Liste des sujets **reportés** : décidés « plus tard », ou en attente d'une décision de Gauthier.
Chaque point garde son contexte, pour qu'on puisse le reprendre sans tout redécouvrir.
Un point réglé est **supprimé** de ce fichier (l'historique git en garde la trace).

---

## À venir (agenda + tâches)

### Plusieurs agendas
Le webhook agenda ne lit aujourd'hui qu'un agenda (`sourceCalendar: "Personnal"`).
D'autres viendront : « work », et des agendas partagés (celui de la conjointe de Gauthier).
- **Doublons** : un même évènement présent dans deux agendas (une invitation) apparaîtra
  deux fois. À dédoublonner côté n8n, par exemple sur titre + heure de début.
- **Agenda partagé** : tous les évènements de la conjointe, ou seulement ceux auxquels
  Gauthier participe ?
- Aucune distinction visuelle par agenda : la couleur est réservée au sens (urgent, retard).

### Évènements annulés
Pour l'instant ils sont affichés (`status: "cancelled"`), sans signe distinctif.
Décision de Gauthier (23/09) : on verra plus tard. Le filtre se ferait côté n8n.

### D'où viennent les tâches Taskwarrior
Taskwarrior est sur cette machine ; n8n est distant. Aujourd'hui **aucun chemin** ne fait
passer les tâches vers n8n (pas de table miroir, pas de synchro, pas de cron).
Lié au point suivant : si le regroupement se fait localement, `fetch-venir.sh` peut lire
Taskwarrior directement (comme `fetch-vrac.sh`), et la question disparaît.

### Libellés et groupes calculés localement (en discussion, 23/09)
Proposition de Gauthier : n8n n'envoie que les évènements bruts (ce que le webhook fait déjà),
et le script local calcule les groupes (EN RETARD / AUJOURD'HUI / DEMAIN / PROCHAINS JOURS)
et leurs libellés à partir des dates. Contredit la règle 3 du brief v9 (« regroupement côté
n8n ») : à acter par Gauthier avant de coder.

### Brancher le webhook
Adresse de production connue (webhook agenda). À mettre dans `URL=` de `fetch-venir.sh`
**une fois** que la réponse a la forme attendue par le script — sinon le panneau affiche
« n8n injoignable ».

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
Aujourd'hui le panneau se **vide** (« n8n injoignable ») et son heure de synchro reste
à jour, au lieu de garder la dernière réponse et de laisser l'heure vieillir.
(`fetch-meteo.sh` garde déjà la dernière réponse : modèle possible.) À décider.

### Contrat n8n ↔ eww
Écrire les fiches « Veille » et « À venir » dans `docs/contrat-bus-n8n.md` (proposé le 23/09),
une fois la question des libellés tranchée.

---

## Écarts connus avec les briefs
- `BRIEF-refonte-colonne.md` (v9) est dans `~/Downloads`, pas dans le dépôt.
- Constantes réelles ≠ brief : ligne de veille 22 px (brief : 26), en-tête replié 59 px
  (brief : 34), A = 992 px (brief : 904).
- Le bandeau du bas a été supprimé le 15/09 ; le brief le décrit encore.
- Le digest nomme son heure `sync`, les autres panneaux `synchro`.
