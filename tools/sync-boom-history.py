#!/usr/bin/env python3
"""Publish the central date-first Boomsday ledger from per-card canonical files."""
import copy,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DATE=re.compile(r"^\d{4}-\d{2}-\d{2}$")
def read(p): return json.loads(p.read_text(encoding="utf-8"))
def write(p,x): p.write_text(json.dumps(x,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8",newline="\n")
def apply(state,row):
 out=copy.deepcopy(state)
 for k,v in row.items():
  if k in ("rawTagDelta","source"): continue
  out[k]=copy.deepcopy(v)
 for d in row.get("rawTagDelta",[]):
  key="nativeTagsOwned" if d["role"]=="owned" else "nativeTagsReferenced"
  m=out.setdefault(key,{})
  tid=str(d["id"])
  if d["after"]=="ABSENT": m.pop(tid,None)
  else: m[tid]=d["after"]
 return out
def main():
 cards=read(ROOT/"cards.json")["cards"]
 observations=read(ROOT/"sources/boomsday-observations.json")
 events={}; observations_out={"undated":{},"undatedRawTags":{},"research":observations}
 card_files={}
 for c in cards:
  cid=c["id"]; p=ROOT/"data"/(cid+".json"); src=read(p)
  if src.get("_meta",{}).get("schemaVersion")!=2 or not isinstance(src.get("_current"),dict):
   raise ValueError(f"{cid}: not date-first v2 source")
  days=sorted(k for k in src if DATE.fullmatch(k))
  if not days: raise ValueError(f"{cid}: missing release state")
  if days[0] != ("2019-06-04" if cid=="BOT_700" else "2018-08-08"):
   raise ValueError(f"{cid}: wrong initial date {days[0]}")
  state=copy.deepcopy(src[days[0]])
  states={days[0]:copy.deepcopy(state)}
  for day in days[1:]:
   row=src[day]
   if not row: raise ValueError(f"{cid} {day}: empty delta")
   state=apply(state,row); states[day]=copy.deepcopy(state)
  current=src["_current"]
  # Verify date-first logical replay against current, but retain unresolved differences as undated evidence.
  logical_diff={}
  for field in set(state)|set(current):
   if field.startswith("nativeTags") or field in ("rawTagDelta","source"): continue
   a=state.get(field,"ABSENT"); b=current.get(field,"ABSENT")
   if a!=b: logical_diff[field]={"before":copy.deepcopy(a),"after":copy.deepcopy(b),"date":None}
  observations_out["undated"][cid]=logical_diff
  raw_obs=[]
  for role,key in (("owned","nativeTagsOwned"),("referenced","nativeTagsReferenced")):
   a=state.get(key,{})
   b=current.get(key,{})
   for tid in sorted(set(a)|set(b),key=int):
    av=a.get(tid,"ABSENT"); bv=b.get(tid,"ABSENT")
    if av!=bv:
     raw_obs.append({"tagId":int(tid),"role":role,"before":av,"after":bv,"date":None})
  observations_out["undatedRawTags"][cid]=raw_obs
  for day in days:
   events.setdefault(day,{})[cid]=copy.deepcopy(src[day])
  card_files[cid]=src
 total=sum(len(x) for x in events.values())
 initial=sum(len(x) for d,x in events.items() if d in ("2018-08-08","2019-06-04"))
 follow=total-initial
 if len(cards)!=155 or initial!=155 or follow!=74 or total!=229:
  raise ValueError(f"ledger counts cards={len(cards)} initial={initial} follow={follow} total={total}")
 expected={"2018-08-08":154,"2019-06-04":21,"2018-10-19":1,"2019-08-27":3,"2020-03-27":3,"2021-03-26":18,"2022-11-30":7,"2023-02-15":12,"2023-03-15":1,"2023-04-05":4,"2024-04-26":1,"2024-10-30":1,"2026-03-11":1,"2026-07-22":1}
 for day,count in expected.items():
  if len(events.get(day,{}))!=count: raise ValueError(f"{day}: expected {count} cards, got {len(events.get(day,{}))}")
 central={"schema":2,"timezone":"Asia/Seoul","format":"date-first-delta-v2","cards":155,"initialStates":155,"followupEvents":74,"totalStates":229,"events":events,"observations":observations_out}
 write(ROOT/"data/history.json",central)
 print(json.dumps({"cards":155,"initialStates":initial,"followupEvents":follow,"totalStates":total,"dates":{d:len(v) for d,v in sorted(events.items())},"undatedLogical":sum(len(x) for x in observations_out["undated"].values()),"undatedRaw":sum(len(x) for x in observations_out["undatedRawTags"].values())},ensure_ascii=False))
if __name__=="__main__": main()
