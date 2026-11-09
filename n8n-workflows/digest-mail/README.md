# Workflows n8n — Digest mail

Exports (JSON) des workflows n8n qui alimentent le panneau **Boîte de réception** du dashboard. Seule la partie "digest mail" est incluse ici (le tri des mails Gmail par IA jusqu'à leur exposition via webhook) ; l'automatisation "recommandations du jour" et "agenda" n'en font pas partie.

Version actuelle : **v5** (amélioration du tri : contenu nettoyé, type d'expéditeur, règles forcées, LLM limité à l'extraction de faits). Résultats de la première revue manuelle : [`docs/revue-tri-2026-11-03.md`](docs/revue-tri-2026-11-03.md).

## Pipeline

1. **`00-main-orchestrator.json`** — déclenché toutes les 10 min. Récupère les mails Gmail reçus depuis le dernier mail enregistré (marge de 5 h), nettoie le contenu (HTML converti en texte quand le `text` est vide ou pauvre, URLs remplacées par `[link]`, caractères invisibles des préheaders supprimés), détecte le **type d'expéditeur** (`source_type` : `humain_direct` / `liste_diffusion` / `automatique`, d'après les en-têtes `List-Id` / `List-Unsubscribe` / `Precedence`, l'adresse et le pied de page), l'enregistre dans une data table n8n, puis appelle en cascade les workflows ci-dessous (référencés dans n8n par leur `workflowId`, pas par ce fichier).
2. **`02-sub-determine-data-table.json`** — trouve ou crée la data table du projet (`PAI_Emails`) et renvoie son id.
3. **`03-organize-mail.json`** — tri des mails :
   - chaque mail passe d'abord par **`03b-sub-apply-rules.json`** (règles forcées) ; s'il correspond à une règle, sa catégorie est écrite directement (`category_origin = regle`) sans appel au LLM ;
   - sinon un agent IA (Ministral 14B, température 0, repli sur Gemini Flash Lite via OpenRouter) **constate des faits** sans juger l'importance du mail : `action` (`repondre` / `agir` / `attendre` / `lire` / `rien`), `domaine` (`emploi_formation` / `admin_finance` / `pro` / `recherche_reseau` / `perso` / `achats` / `promo`), `echeance` (AAAA-MM-JJ ou null) et une `raison` d'une phrase. Schéma catégoriel strict, sans score de confiance auto-évalué. Le prompt reçoit la date du jour en français, le nom et le type d'expéditeur, et un contenu tronqué à 2 000 caractères (1 600 au début + 400 à la fin) ;
   - un nœud Code **« Compute category »** déduit la catégorie de ces faits : `urgent` (répondre / agir avec échéance à 2 jours ou moins), `a_traiter`, `en_attente`, `a_lire` (information utile dans un domaine important) ou `ignorer` (`category_origin = llm`) ;
   - si les deux modèles échouent, le mail passe en `02_LLM_error` (`category_origin = llm_error`) et la boucle continue au lieu de tout arrêter.
4. **`03b-sub-apply-rules.json`** — sous-workflow 100 % nœuds natifs : croise les mails avec la data table `PAI_Email_rules`, garde les règles applicables (motif d'expéditeur et/ou motif d'objet, insensible à la casse), choisit la plus précise (deux critères > un critère, puis motif le plus long) et renvoie chaque mail avec `rule_match` / `rule_category` / `rule_note`.
5. **`04-summarize-mail.json`** — résume en 1 à 3 phrases les mails jugés pertinents (ignore ceux catégorisés `ignorer`).
6. **`05-mark-mail-read.json`** — tourne toutes les heures (ou à la demande) : vérifie sur Gmail si un mail traité a été lu depuis, et met à jour son statut dans la data table en conséquence. Un mail supprimé de Gmail entre-temps est considéré comme lu, au lieu de faire échouer tout le pipeline (erreur 404).
7. **`01-webhook-digest.json`** — webhook (auth Basic) interrogé par `fetch-digest.sh` du dashboard : lit la data table et **construit les sections** (À TRAITER, EN ATTENTE, À LIRE), leur ordre, leurs libellés et le résumé de l'en-tête ; le dashboard ne fait qu'afficher. Contrat et règles (durées d'affichage, ordre) : [`docs/contrat-bus-n8n.md`](../../docs/contrat-bus-n8n.md). Cet export est à jour au 9/11 ; les autres datent du 3/11.
8. **`06-test-prompt-tri.json`** — banc de test manuel : relit des mails réels de la data table, les classe avec le prompt et le code de décision (copies à reporter à la main) et sort, pour chaque mail, l'ancienne et la nouvelle catégorie. Sert de test de non-régression avant de modifier le prompt de `03-organize-mail.json`.

## Data tables

**`PAI_Emails`** — une ligne par mail. Colonnes ajoutées en v5 : `source_type`, `category_origin` (`regle` / `llm` / `llm_error`), `domaine`, `echeance` (la colonne `intent` reçoit désormais l'`action`, `is_deadline` vaut vrai quand une échéance existe).

**`PAI_Email_rules`** — règles forcées, appliquées avant le LLM :

| Colonne | Type | Rôle |
|---|---|---|
| `sender_pattern` | string | Morceau de l'adresse expéditeur (ex. `@business.amazon.fr`) |
| `title_pattern` | string | Morceau de l'objet (optionnel) |
| `forced_category` | string | `ignorer` / `a_lire` / `a_traiter` / `en_attente` / `urgent` |
| `note` | string | Raison de la règle, recopiée dans `reason` |
| `enabled` | boolean | Pour désactiver une règle sans la supprimer |
| `origin` | string | `manuel` (plus tard `hitl` : feedback depuis le dashboard) |

## Réimport

Ces fichiers sont des exports des workflows n8n. Pour les réimporter : n8n → *Import from File*. Il faudra reconnecter tes propres credentials (Gmail OAuth2, Mistral, Groq, OpenRouter, Basic Auth du webhook), recréer les data tables `PAI_Emails` et `PAI_Email_rules`, et mettre à jour les `workflowId` / ids de data tables référencés pour qu'ils pointent vers tes propres copies.

⚠️ Les credentials ne sont **pas** exportées (n8n ne stocke que leur id/nom de référence) — les noms de credentials ont été anonymisés avant publication, mais l'URL du webhook (déjà présente dans `fetch-digest.sh`) reste visible dans ces fichiers.
