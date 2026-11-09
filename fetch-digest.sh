#!/usr/bin/env bash
# Boite de reception : sections de mails construites par n8n, via ~/.netrc.
# Contrat (format, regles, pourquoi) : docs/contrat-bus-n8n.md.
# n8n decide QUELS mails, dans QUELLE section, dans QUEL ordre, avec quel
# libelle, et ecrit le resume de l'en-tete. Ce script ne fait que la mise en
# forme qui depend de l'heure locale ou de l'ecran : age ("3 h"), sujet
# tronque, emojis retires (nettoyer.py), ligne "expediteur · age", lien
# Gmail, index by_id pour la modale. Il ne connait aucune categorie.
URL="https://n8n.power-of-automation.link/webhook/c9d179c1-870f-4973-ae04-29f4d2c22766"
# DIGEST_EXEMPLE permet de tester avec un faux fichier au lieu de n8n :
#   DIGEST_EXEMPLE=~/.config/eww/exemples/mails-test.json bash ~/.config/eww/sync.sh digest
# (le prochain rafraichissement automatique, <= 5 min, remet les vrais mails)
if [ -n "$DIGEST_EXEMPLE" ]; then
  OUT="$(cat "$DIGEST_EXEMPLE" 2>/dev/null)"
else
  OUT="$(curl -s --netrc --max-time 8 "$URL")"
fi
[ -z "$OUT" ] && OUT='{}'
printf '%s' "$OUT" | python3 -c '
import sys, json, datetime
import os
sys.path.insert(0, os.path.expanduser("~/.config/eww"))
from nettoyer import propre    # sans emoji, espaces normalises
def age_from(s):
    if not s: return ""
    try:
        dt=datetime.datetime.fromisoformat(str(s).replace("Z","+00:00"))
        now=datetime.datetime.now(dt.tzinfo) if dt.tzinfo else datetime.datetime.now()
        diff=max((now-dt).total_seconds(),0)
    except Exception: return ""
    if diff<60: return "à l\x27instant"
    if diff<3600: return f"{int(diff//60)} min"
    if diff<86400: return f"{int(diff//3600)} h"
    if diff<604800: return f"{int(diff//86400)} j"
    return dt.strftime("%d/%m")
def short(s, n=55):
    s = s or ""
    return (s[:n].rstrip()+" [...]") if len(s) > n else s
def norm(m):
    mid=m.get("mail_id") or ""
    frm=propre(m.get("sender_name"))
    age=age_from(m.get("createdAt"))
    subj=propre(m.get("mail_title")) or "(sans objet)"
    return {"subject":subj,"subject_short":short(subj),
            "from":frm,"email":m.get("sender_email") or "","age":age,
            "meta":" · ".join(p for p in (frm,age) if p),
            "read":m.get("lu") is True,
            "urgent":m.get("urgent") is True,
            "important":m.get("important") is True,
            "category":m.get("category") or "","intent":m.get("intent") or "",
            "reason":m.get("reason") or "","summary":m.get("mail_summary") or "",
            "mail_id":mid,
            "url":("https://mail.google.com/mail/u/0/#all/"+mid) if mid else ""}
try: raw=json.loads(sys.stdin.read() or "{}")
except Exception: raw={}
# "Respond to Webhook" renvoie un objet ; une liste d un seul objet est
# toleree (autre reglage possible du noeud).
if isinstance(raw,list) and len(raw)==1: raw=raw[0]
if not isinstance(raw,dict): raw={}
sections=[]
for s in raw.get("sections") or []:
    if not isinstance(s,dict): continue
    items=[norm(m) for m in s.get("items") or [] if isinstance(m,dict)]
    if items:   # jamais de titre orphelin
        sections.append({"cle":s.get("cle") or "","libelle":propre(s.get("libelle")),"items":items})
by_id={it["mail_id"]:it for s in sections for it in s["items"] if it["mail_id"]}
print(json.dumps({"sections":sections,"by_id":by_id,"resume":raw.get("resume") or "",
                  "sync":datetime.datetime.now().strftime("%H:%M")},ensure_ascii=False))
' | bash "$HOME/.config/eww/publier.sh" digest   # copie dans le bus + recalcul des hauteurs
