# Contrat n8n → eww

Chaque panneau interroge un webhook n8n (`curl --netrc`, GET, 8 s maximum) depuis
son `fetch-*.sh`, qui met en forme puis passe la main à `publier.sh`
(copie dans `~/.cache/eww/bus/<nom>.json` + recalcul des hauteurs).
n8n n'écrit jamais de fichier.

Une fiche par panneau : ce que n8n renvoie, et qui décide de quoi.
Les fiches « Veille » et « À venir » restent à écrire (voir `A-FAIRE.md`).

---

## Boîte de réception

Webhook servi par le workflow n8n `XX_Webhook_Email_dispenser`, lu par
`fetch-digest.sh` toutes les 5 min. Source : la table `PAI_Emails` du module mail v5.

### Décision d'architecture (9/11/2026)

**n8n construit les sections ; eww ne fait que les afficher.**

- n8n choisit quels mails apparaissent, dans quelle section, dans quel ordre,
  avec quel libellé, et écrit le résumé de l'en-tête.
- `fetch-digest.sh` ne fait que de la mise en forme qui dépend de l'heure locale
  ou de l'écran : âge (« 3 h »), troncature du sujet, nettoyage des emojis
  (`nettoyer.py`), ligne « expéditeur · âge », lien Gmail, index `by_id`.
- `eww.yuck` affiche ce qu'il reçoit, sans connaître les catégories.

**Pourquoi.** La règle du projet (`P.A.I/config/CLAUDE.md`) veut un dashboard
« bête » : pas de logique de tri ou de regroupement côté affichage. Avant ce
changement, `fetch-digest.sh` regroupait lui-même les catégories et écrivait
les libellés en dur ; chaque évolution du tri (par exemple la fusion
« en attente » → « à lire », prévue à l'étape 5) aurait demandé de modifier
eww en même temps que n8n. Désormais, la correspondance catégorie → section
vit dans n8n, à côté du tri : on la change à un seul endroit.

**Option écartée : n8n renvoie un bloc de texte prêt à afficher.** On aurait
perdu le clic par mail, la modale de détail, le marquage lu / non lu et le
calcul des hauteurs (`mise-en-page.py` compte les lignes).

### Format

```json
{
  "resume": "2 à traiter · 13 à lire",
  "sections": [
    { "cle": "a_traiter", "libelle": "À TRAITER",
      "items": [
        { "mail_id": "…", "mail_title": "…", "sender_name": "…",
          "sender_email": "…", "createdAt": "2026-11-09T10:34:00.000Z",
          "lu": false, "urgent": true, "important": false,
          "category": "urgent", "intent": "…", "domaine": "…",
          "echeance": "…", "reason": "…", "mail_summary": "…" } ] },
    { "cle": "a_lire", "libelle": "À LIRE", "items": [ … ] }
  ]
}
```

- `sections` : dans l'ordre d'affichage. Une section vide n'est **pas** envoyée
  (jamais de titre orphelin). `cle` sert au style, `libelle` est affiché tel quel.
- `items` : dans l'ordre d'affichage.
- `lu` : le mail a été lu (ou supprimé) dans Gmail (statut `04_mail_read`).
- `urgent` : catégorie `urgent` (échéance proche, voir `decision.csv`). Signe « ! ».
- `important` : colonne `important` de `decision.csv` (étape 5). Signe « ★ ».
  **Absent = `false`** : le contrat marche avant et après l'étape 5.
- `resume` : texte de l'en-tête, affiché tel quel, même panneau replié.

### Règles appliquées par n8n

| Section | Catégories | Mail non lu | Mail lu |
|---|---|---|---|
| À TRAITER | `urgent`, `a_traiter` | toujours affiché | affiché 3 jours après sa lecture |
| EN ATTENTE | `en_attente` | toujours affiché | affiché 3 jours après sa lecture |
| À LIRE | `a_lire` | affiché 7 jours après sa réception | affiché 24 h après sa lecture |

- `ignorer` n'est jamais affiché.
- EN ATTENTE disparaît à l'étape 5 (fusion dans À LIRE) : seule la table de
  correspondance du workflow n8n change.
- Ordre dans une section : urgents, puis importants, puis du plus récent au plus ancien.
- Résumé : nombre de mails **non lus** par section (« 2 à traiter · 13 à lire »),
  « rien de neuf » s'il n'y en a aucun.
- « Date de lecture » = `updatedAt` de la ligne : c'est `04_Sync_read_status`
  qui la touche en dernier, quand il passe le mail en `04_mail_read`
  (au plus une heure après la lecture dans Gmail). Si un autre workflow se met
  un jour à réécrire des lignes déjà lues, cette date deviendra fausse.
- Statut « lu » : `04_Sync_read_status` le relit dans Gmail pour les mails des
  **30 derniers jours** (sauf « ignorer », jamais affichés). Au-delà, un mail
  reste dans l'état où il était.
- Pourquoi 7 jours pour un « à lire » non lu : les alertes (emploi, newsletters)
  ne sont pas toutes lues ; sans limite, elles s'entasseraient dans le panneau.
- Durées (24 h, 3 jours, 7 jours) choisies par Gauthier le 9/11, à revoir à l'usage
  (voir `A-FAIRE.md`).
