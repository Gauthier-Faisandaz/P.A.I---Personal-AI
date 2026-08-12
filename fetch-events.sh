#!/usr/bin/env bash
# fetch-events.sh — evenements Google Agenda depuis n8n via ~/.netrc.
# Trie par date de debut, tronque le nom, formate les dates en francais lisible
# et publie un index "by_id" pour le survol (apercu) et le clic (detail).
# Repli sur aucun evenement si le webhook est injoignable.

# >>> A COMPLETER : URL de PRODUCTION du webhook Agenda (workflow active) <<<
URL="https://n8n.power-of-automation.link/webhook/68231c0f-62ba-4474-914b-a6803084dd72"

OUT="$(curl -s --netrc --max-time 8 "$URL")"
[ -z "$OUT" ] && OUT='{}'

printf '%s' "$OUT" | python3 -c '
import sys, json, datetime, base64

JOURS = ["lun.","mar.","mer.","jeu.","ven.","sam.","dim."]      # weekday(): lun=0
MOIS  = ["janv.","févr.","mars","avr.","mai","juin","juil.","août",
         "sept.","oct.","nov.","déc."]
STATUTS = {"confirmed":"confirmé","tentative":"provisoire","cancelled":"annulé"}

def events(raw):
    """Localise la liste des evenements quelle que soit l enveloppe n8n."""
    if isinstance(raw, list):
        if len(raw)==1 and isinstance(raw[0],dict) and any(
            isinstance(raw[0].get(k),list) for k in ("data","events","items")):
            return events(raw[0])
        return [e for e in raw if e is not None]
    if isinstance(raw, dict):
        for k in ("data","events","items","results","value"):
            if isinstance(raw.get(k),list): return events(raw[k])
        for k in ("body","json","data"):
            if isinstance(raw.get(k),dict): return events(raw[k])
    return []

def pick(ev, *keys):
    for k in keys:
        v=ev.get(k)
        if v not in (None,""): return str(v).strip()
    return ""

def get_name(ev):
    return pick(ev,"title","summary","name","event_name","event_title") or "(sans titre)"

def get_bound(ev, which):
    """Date de debut ou de fin, forme Google (start.dateTime/date) ou aplatie."""
    st=ev.get(which)
    if isinstance(st,dict): return st.get("dateTime") or st.get("date") or ""
    if isinstance(st,str) and st: return st
    if which=="start":
        return pick(ev,"startDate","start_time","startTime","start_date","dateTime","date","begin")
    return pick(ev,"endDate","end_time","endTime","end_date","finish")

def parse_dt(s):
    """-> (datetime local sans tz, a_une_heure). AAAA-MM-JJ = journee entiere."""
    if not s: return (None, False)
    s=str(s).strip()
    if len(s)==10 and s.count("-")==2:
        try:
            d=datetime.date.fromisoformat(s)
            return (datetime.datetime(d.year,d.month,d.day), False)
        except Exception: return (None, False)
    try:
        dt=datetime.datetime.fromisoformat(s.replace("Z","+00:00"))
        if dt.tzinfo: dt=dt.astimezone().replace(tzinfo=None)
        return (dt, True)
    except Exception:
        return (None, False)

def jour(d, court=True):
    """Jour lisible : aujourd hui / demain / ven. / ven. 8 aout."""
    today=datetime.date.today(); delta=(d-today).days
    if   delta==0:  return "aujourd\x27hui"
    elif delta==1:  return "demain"
    elif delta==-1: return "hier"
    elif court and 1<delta<7: return JOURS[d.weekday()]
    s=f"{JOURS[d.weekday()]} {d.day} {MOIS[d.month-1]}"
    if d.year!=today.year: s+=f" {d.year}"
    return s

def heure(dt):
    return f"{dt.hour}h" if dt.minute==0 else f"{dt.hour}h{dt.minute:02d}"

def humanize(dt, has_time):
    """Ligne de liste : date de debut seule."""
    if dt is None: return ""
    return f"{jour(dt.date())} \u00b7 {heure(dt)}" if has_time else jour(dt.date())

def plage(sdt, s_time, edt, e_time):
    """Modale : plage complete debut -> fin."""
    if sdt is None: return ""
    fleche=" \u2192 "
    if not s_time:                                   # journee entiere
        if edt is None: return jour(sdt.date(), False)
        fin=edt.date()
        if e_time and edt.hour==23 and edt.minute>=59: pass   # fin de journee
        if fin<=sdt.date(): return jour(sdt.date(), False) + " (journée)"
        return jour(sdt.date(), False) + fleche + jour(fin, False)
    debut=f"{jour(sdt.date(), False)} \u00b7 {heure(sdt)}"
    if edt is None: return debut
    if edt.date()==sdt.date(): return debut + fleche + heure(edt)
    return debut + fleche + f"{jour(edt.date(), False)} \u00b7 {heure(edt)}"

def short(s, n=32):
    s=s or ""
    return (s[:n].rstrip()+"\u2026") if len(s)>n else s

def cal_url(ev_id, cal_mail, sdt):
    """Lien Google Agenda : evenement direct si possible, sinon vue du jour."""
    if ev_id and cal_mail:
        raw=f"{ev_id} {cal_mail}".encode()
        eid=base64.urlsafe_b64encode(raw).decode().rstrip("=")
        return "https://calendar.google.com/calendar/u/0/r/eventedit/"+eid
    if sdt is not None:
        d=sdt.date()
        return f"https://calendar.google.com/calendar/u/0/r/day/{d.year}/{d.month}/{d.day}"
    return "https://calendar.google.com/calendar/u/0/r"

try: raw=json.loads(sys.stdin.read() or "{}")
except Exception: raw={}

out=[]
for i,ev in enumerate(events(raw)):
    if not isinstance(ev,dict): continue
    sdt,s_time = parse_dt(get_bound(ev,"start"))
    edt,e_time = parse_dt(get_bound(ev,"end"))
    name = get_name(ev)
    gid  = pick(ev,"eventID","eventId","event_id","iCalUID")
    mail = pick(ev,"organizerEmail","creatorEmail","calendarId")
    key  = gid or pick(ev,"id") or f"ev{i}"
    statut = pick(ev,"status")
    out.append({
        "id":key, "name":name, "name_short":short(name),
        "when":humanize(sdt,s_time),          # ligne de liste
        "range":plage(sdt,s_time,edt,e_time), # modale
        "allday": (not s_time) and sdt is not None,
        "location":pick(ev,"location"),
        "meet":pick(ev,"conferenceURL","hangoutLink","meetURL"),
        "description":pick(ev,"description"),
        "calendar":pick(ev,"sourceCalendar","calendar","calendarName"),
        "status":STATUTS.get(statut.lower(), statut),
        "organizer":mail,
        "url":cal_url(gid, mail, sdt),
        "_k":sdt.isoformat() if sdt else "9999",   # sans date -> a la fin
    })

out.sort(key=lambda e:e["_k"])
for e in out: e.pop("_k",None)

print(json.dumps({"events":out,
                  "by_id":{e["id"]:e for e in out},
                  "sync":datetime.datetime.now().strftime("%H:%M")},
                 ensure_ascii=False))
'

