#!/usr/bin/env bash
# Mails (JSON a plat sous "data") depuis n8n via ~/.netrc.
# 2 sections : À TRAITER (inclut category=urgent, flag urgent) et EN ATTENTE.
# read/unread via status ; lien Gmail via mail_id ; index by_id pour survol/clic.
URL="https://n8n.power-of-automation.link/webhook/c9d179c1-870f-4973-ae04-29f4d2c22766"
OUT="$(curl -s --netrc --max-time 8 "$URL")"
[ -z "$OUT" ] && OUT='{}'
printf '%s' "$OUT" | python3 -c '
import sys, json, datetime
LABELS = {"a_traiter":"À TRAITER","en_attente":"EN ATTENTE"}
def mails(raw):
    if isinstance(raw, list):
        if len(raw)==1 and isinstance(raw[0],dict) and isinstance(raw[0].get("data"),list):
            return raw[0]["data"]
        return raw
    if isinstance(raw, dict):
        for k in ("data","items","mails","results"):
            if isinstance(raw.get(k),list): return raw[k]
        for k in ("body","json"):
            if isinstance(raw.get(k),(dict,list)): return mails(raw[k])
    return []
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
def truthy(v): return v in (True,"true","True",1,"1")
def short(s, n=55):
    s = s or ""
    return (s[:n].rstrip()+" [...]") if len(s) > n else s
def norm(m):
    mid=m.get("mail_id") or ""
    frm=m.get("sender_name") or m.get("from") or ""
    cat=(m.get("category") or "").strip()
    age=age_from(m.get("createdAt") or m.get("date") or "")
    subj=m.get("mail_title") or m.get("subject") or "(sans objet)"
    return {"subject":subj,"subject_short":short(subj),
            "from":frm,"email":m.get("sender_email") or "","age":age,
            "meta":" · ".join(p for p in (frm,age) if p),
            "read":("mail_read" in (m.get("status") or "")),
            "urgent":cat in ("urgent","urgences"),
            "category":cat,"intent":m.get("intent") or "",
            "reason":m.get("reason") or "","summary":m.get("mail_summary") or "",
            "mail_id":mid,
            "url":("https://mail.google.com/mail/u/0/#all/"+mid) if mid else ""}
try: raw=json.loads(sys.stdin.read() or "{}")
except Exception: raw={}
items=[norm(m) for m in mails(raw) if isinstance(m,dict)]
buckets={}
for it in items:
    b="a_traiter" if it["category"] in ("a_traiter","urgent","urgences") else it["category"]
    buckets.setdefault(b,[]).append(it)
sections=[{"label":LABELS[c],"items":buckets[c]} for c in ("a_traiter","en_attente") if buckets.get(c)]
by_id={it["mail_id"]:it for it in items if it["mail_id"]}
print(json.dumps({"sections":sections,"by_id":by_id,
                  "sync":datetime.datetime.now().strftime("%H:%M")},ensure_ascii=False))
'

# Garde-fou : la liste va etre redessinee -> si un item etait survole a cet
# instant precis, son onhoverlost peut ne jamais se declencher (widget detruit
# pendant le survol). On referme l'apercu par securite ; il se rouvre au
# prochain survol. N'affecte pas la modale de detail (opened_id/detail).
EWW="$HOME/.cargo/bin/eww"
"$EWW" update hovered_id="" >/dev/null 2>&1
"$EWW" close preview >/dev/null 2>&1
