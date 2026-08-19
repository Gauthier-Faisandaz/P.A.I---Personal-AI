# Workflows n8n — Digest mail

Exports (JSON) des workflows n8n qui alimentent le panneau **Boîte de réception** du dashboard. Seule la partie "digest mail" est incluse ici (le tri des mails Gmail par IA jusqu'à leur exposition via webhook) ; l'automatisation "recommandations du jour" et "agenda" n'en font pas partie.

## Pipeline

1. **`00-main-orchestrator.json`** — déclenché par un trigger Gmail (poll toutes les 5 min sur les mails non lus). Nettoie le contenu du mail, l'enregistre dans une data table n8n, puis appelle en cascade les workflows 2 à 5 ci-dessous (référencés dans n8n par leur `workflowId`, pas par ce fichier).
2. **`02-sub-determine-data-table.json`** — trouve ou crée la data table du projet (`PAI_Emails`) et renvoie son id.
3. **`03-organize-mail.json`** — pour chaque mail, un agent IA (Groq Llama 3.3 70B, repli sur OpenRouter) le classe en catégorie (`urgent` / `a_traiter` / `en_attente` / `ignorer`), détecte l'intention et une éventuelle deadline.
4. **`04-summarize-mail.json`** — résume en 1 à 3 phrases les mails jugés pertinents (ignore ceux catégorisés `ignorer`).
5. **`05-mark-mail-read.json`** — tourne toutes les heures (ou à la demande) : vérifie sur Gmail si un mail traité a été lu depuis, et met à jour son statut dans la data table en conséquence.
6. **`01-webhook-digest.json`** — webhook (auth Basic) interrogé par `fetch-digest.sh` du dashboard : lit la data table, filtre les mails `summarized`/`read` et répond en JSON.

## Réimport

Ces fichiers sont des exports bruts de l'éditeur n8n (`...` → *Download*). Pour les réimporter : n8n → *Import from File*. Il faudra reconnecter tes propres credentials (Gmail OAuth2, Groq, OpenRouter, Basic Auth du webhook) et mettre à jour les `workflowId` référencés dans `00-main-orchestrator.json` pour qu'ils pointent vers tes propres copies des workflows 1 à 5.

⚠️ Les credentials ne sont **pas** exportées (n8n ne stocke que leur id/nom de référence) — les noms de credentials ont été anonymisés avant publication, mais l'URL du webhook (déjà présente dans `fetch-digest.sh`) reste visible dans ces fichiers.
