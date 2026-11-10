#!/usr/bin/env python3
"""Migrate Boomsday's audited current snapshots into date-first sparse source files."""
from __future__ import annotations
import copy, json, re, sys, hashlib, xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATE=re.compile(r"^\d{4}-\d{2}-\d{2}$")
TYPE_OMIT={
 "MINION":{"durability":0,"armor":0,"spellSchool":""},
 "SPELL":{"attack":0,"health":0,"durability":0,"armor":0,"races":[],"race":""},
 "WEAPON":{"health":0,"armor":0,"spellSchool":"","races":[],"race":""},
 "HERO":{"attack":0,"durability":0,"spellSchool":"","races":[],"race":""},
 "HERO_POWER":{"attack":0,"health":0,"durability":0,"armor":0,"spellSchool":"","races":[],"race":""},
}
INITIAL_FIX={
 "BOT_021":{"attack":1},
 "BOT_066":{"races":["MECHANICAL"],"race":"기계"},
 "BOT_066t":{"races":["MECHANICAL"],"race":"기계"},
 "BOT_251":{"races":["MECHANICAL"],"race":"기계"},
 "BOT_283":{"races":["MECHANICAL"],"race":"기계"},
 "BOT_312":{"health":1},
 "BOT_444":{"text":"이번 턴에\n하수인이 죽을 때마다 이번 턴에만 마나\u00a0수정을 1개 획득합니다."},
 "BOT_445":{"races":["MECHANICAL"],"race":"기계"},
 "BOT_445t":{"races":["MECHANICAL"],"race":"기계"},
 "BOT_448":{"races":["MECHANICAL"],"race":"기계"},
 "BOT_523":{"races":["MECHANICAL"],"race":"기계"},
 "BOT_533":{"health":2},
 "BOT_534":{"races":["MECHANICAL"],"race":"기계"},
 "BOT_537t":{"races":["MECHANICAL"],"race":"기계"},
 "BOT_558":{"text":"<b>죽음의 메아리:</b>\n내가 이 하수인에게\n시전한 모든 주문을 내 손으로 가져옵니다."},
 "BOT_559":{"races":["BEAST"],"race":"야수"},
 "BOT_562":{"races":["MECHANICAL"],"race":"기계"},
 "BOT_563":{"attack":5},
 "BOT_573":{"races":["BEAST"],"race":"야수"},
 "BOT_603":{"races":["MECHANICAL"],"race":"기계"},
 "BOT_700":{"races":["MECHANICAL"],"race":"기계"},
}
DATE_FIX={"2022-12-07":"2022-11-30","2024-11-06":"2024-10-30"}
# New confirmed events: only evidence-backed gameplay fields, not rules or editorial observations.
NEW_EVENTS={
 "2019-06-04":{
  "BOT_219t":{"cost":2}},
 "2019-08-27":{
  "BOT_219t":{"cost":3}},
 "2022-11-30":{
  "BOT_559":{"races":["BEAST","MECHANICAL"],"race":"야수, 기계"},
  "BOT_573":{"races":["BEAST","MECHANICAL"],"race":"야수, 기계"},
  "BOT_603":{"races":["MECHANICAL","ELEMENTAL"],"race":"기계, 정령"}},
 "2023-02-15":{
  "BOT_066":{"races":["MECHANICAL","DRAGON"],"race":"기계, 용족"},
  "BOT_066t":{"races":["MECHANICAL","DRAGON"],"race":"기계, 용족"},
  "BOT_251":{"races":["MECHANICAL","BEAST"],"race":"기계, 야수"},
  "BOT_283":{"races":["MECHANICAL","BEAST"],"race":"기계, 야수"},
  "BOT_445":{"races":["MECHANICAL","BEAST"],"race":"기계, 야수"},
  "BOT_445t":{"races":["MECHANICAL","BEAST"],"race":"기계, 야수"},
  "BOT_448":{"races":["MECHANICAL","BEAST"],"race":"기계, 야수"},
  "BOT_523":{"races":["MECHANICAL","BEAST"],"race":"기계, 야수"},
  "BOT_534":{"races":["MECHANICAL","BEAST"],"race":"기계, 야수"},
  "BOT_537t":{"races":["MECHANICAL","BEAST"],"race":"기계, 야수"},
  "BOT_562":{"races":["MECHANICAL","BEAST"],"race":"기계, 야수"},
  "BOT_700":{"races":["MECHANICAL","BEAST"],"race":"기계, 야수"}},
 "2023-04-05":{
  "BOT_021":{"attack":2},"BOT_312":{"health":2},"BOT_563":{"attack":6},"BOT_533":{"health":3}},
 "2023-03-15":{
  "BOT_558":{"text":"<b>죽음의 메아리:</b>\n내가 이 하수인에게\n시전한 모든 주문을 내 덱에 섞어 넣습니다."}},
 "2024-04-26":{
  "BOT_444":{"text":"이번 턴에 하수인이\n죽을 때마다 마나 수정을\n1개 회복합니다."}},
}
DATE_BUILDS={
 "2018-10-19":(26757,27358),
 "2019-06-04":(31022,31268),
 "2019-08-27":(33157,33402),
 "2020-03-27":(33402,44222),
 "2021-03-26":(44222,77662),
 "2022-11-30":(155409,158725),
 "2023-02-15":(163976,165029),
 "2023-03-15":(168129,168788),
 "2023-04-05":(170126,170824),
 "2024-04-26":(198314,198608),
 "2024-10-30":(209698,210009),
 "2026-03-11":(217964,237510),
 "2026-07-22":(237510,247416),
}
RELEVANT_TAGS={45,47,48,200,215,1635,2523,2534,2539,2540,2542}
LOGICAL_FIELDS=("name","type","cardClass","classes","rarity","collectible","cost","attack","health","durability","armor","text","races","race","spellSchool","mechanics","flavor")
def read(p): return json.loads(p.read_text(encoding="utf-8"))
def write(p,obj):
 p.parent.mkdir(parents=True,exist_ok=True)
 p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8",newline="\n")
def strip_type_fields(s):
 s=copy.deepcopy(s); omit=TYPE_OMIT.get(s.get("type"),{})
 for k,v in omit.items():
  if s.get(k,"__ABSENT__")==v: s.pop(k,None)
 return s
def parse_xml(path, wanted):
 result={}
 for _,e in ET.iterparse(path,events=("end",)):
  if e.tag.rsplit("}",1)[-1]!="Entity": continue
  cid=e.attrib.get("CardID")
  if cid not in wanted: e.clear(); continue
  owned={}; refs={}
  for t in list(e):
   kind=t.tag.rsplit("}",1)[-1]
   if kind not in ("Tag","ReferencedTag") or "enumID" not in t.attrib: continue
   target=owned if kind=="Tag" else refs
   target[str(int(t.attrib["enumID"]))]=str(t.attrib.get("value",""))
  if cid in result: raise ValueError(f"duplicate XML entity {cid} in {path}")
  result[cid]={"owned":owned,"referenced":refs}
  e.clear()
 return result
def tag_name_map(cards):
 out={}
 for c in cards:
  for t in c.get("nativeTags",[]): out[int(t["id"])]=t.get("name",f"게임 태그 {t['id']}")
 return out
def flat_tags(owned,refs,names):
 out=[]
 for role in (owned,refs):
  for tid,value in role.items():
   n=int(tid)
   try: v=int(value)
   except (ValueError,TypeError): v=value
   out.append({"id":n,"name":names.get(n,f"게임 태그 {n}"),"value":v})
 return sorted(out,key=lambda x:x["id"])
def raw_delta(before,after):
 out=[]
 for role in ("owned","referenced"):
  a=before[role]; b=after[role]
  for tid in sorted(set(a)|set(b),key=int):
   av=a.get(tid,"ABSENT"); bv=b.get(tid,"ABSENT")
   if av!=bv:
    out.append({"role":role,"id":int(tid),"before":av,"after":bv})
 return out
def merge(a,b):
 z=copy.deepcopy(a)
 for k,v in b.items(): z[k]=copy.deepcopy(v)
 return z
def main():
 xml_dir=Path(sys.argv[1]) if len(sys.argv)>1 else Path("/tmp/boom-xml")
 catalog=read(ROOT/"cards.json")
 central=read(ROOT/"data/history.json")
 if all((ROOT/"data"/(c["id"]+".json")).is_file() and read(ROOT/"data"/(c["id"]+".json")).get("_meta",{}).get("schemaVersion")==2 for c in catalog["cards"]):
  print("date-first source already migrated; idempotent validation only")
  return
 cards=catalog["cards"]; ids={c["id"] for c in cards}; names=tag_name_map(cards)
 manifest=read(ROOT/"sources/archive-manifest.json")
 bybuild={int(x["build"]):x for x in manifest["entries"]}
 required={25770,31268,256589}
 for pair in DATE_BUILDS.values(): required.update(pair)
 xml={}
 for build in sorted(required):
  meta=bybuild[build]; path=xml_dir/f"{build}.xml"
  if not path.is_file(): raise FileNotFoundError(path)
  digest=hashlib.sha256(path.read_bytes()).hexdigest()
  if digest!=meta["xmlSha256"]: raise ValueError(f"build {build} XML hash mismatch: {digest}")
  parsed=parse_xml(path,ids)
  if len(parsed)!=meta["observedCardCount"]: raise ValueError(f"build {build} card count {len(parsed)}")
  missing=set(ids)-set(parsed)
  if missing!=set(meta.get("absentOriginalIds",[])): raise ValueError(f"build {build} absent IDs mismatch {missing}")
  xml[build]=parsed
 current_xml=xml[256589]
 events=central["events"]
 # Merge legacy dated rows into per-card forward states; only confirmed changes are retained.
 by_card={}
 for cid in ids:
  release="2019-06-04" if cid=="BOT_700" else "2018-08-08"
  initial=copy.deepcopy(events[release][cid])
  initial.update(INITIAL_FIX.get(cid,{}))
  initial=strip_type_fields(initial)
  release_build=31268 if cid=="BOT_700" else 25770
  initial["nativeTagsOwned"]=copy.deepcopy(xml[release_build][cid]["owned"])
  initial["nativeTagsReferenced"]=copy.deepcopy(xml[release_build][cid]["referenced"])
  initial["nativeTags"]=flat_tags(initial["nativeTagsOwned"],initial["nativeTagsReferenced"],names)
  states=[(release,initial,{"findingId":"BOOM-RELEASE","build":release_build,
    "commit":bybuild[release_build]["commit"],"xmlSha256":bybuild[release_build]["xmlSha256"]})]
  rows={}
  for old_day,items in events.items():
   if cid in items and old_day!=release:
    day=DATE_FIX.get(old_day,old_day)
    rows[day]=copy.deepcopy(items[cid])
  for day,items in NEW_EVENTS.items():
   if cid in items:
    rows[day]=merge(rows.get(day,{}),items[cid])
  prev=copy.deepcopy(initial)
  prev_xml=xml[31268 if cid=="BOT_700" else 25770][cid]
  for day in sorted(rows):
   if day not in DATE_BUILDS: raise ValueError(f"no immutable XML pair for {day}")
   before_build,after_build=DATE_BUILDS[day]
   before_xml=xml[before_build].get(cid,prev_xml)
   after_xml=xml[after_build].get(cid)
   if after_xml is None: raise ValueError(f"{cid} missing in after XML {after_build}")
   event=rows[day]
   logical={k:copy.deepcopy(v) for k,v in event.items() if k not in ("nativeTags","id","dbfId","name","portrait","set","art","flavor") and k in LOGICAL_FIELDS}
   if cid in NEW_EVENTS.get(day,{}): logical=merge(logical,NEW_EVENTS[day][cid])
   next_state=merge(prev,logical)
   next_state=strip_type_fields(next_state)
   # Apply only raw scalar tags tied to the confirmed gameplay fields. Other raw
   # metadata changes remain current-vs-history observations, never invented dates.
   relevant=set()
   if "cost" in logical: relevant.add(48)
   if "attack" in logical: relevant.add(47)
   if "health" in logical: relevant.add(45)
   if "spellSchool" in logical: relevant.add(1635)
   if "races" in logical:
    relevant.update((200,2523,2534,2539,2540,2542))
   raw=[]
   for role in ("owned","referenced"):
    a=before_xml[role]; b=after_xml[role]
    for tid in sorted(relevant,key=int):
     av=a.get(str(tid),"ABSENT"); bv=b.get(str(tid),"ABSENT")
     if av!=bv: raw.append({"role":role,"id":int(tid),"before":av,"after":bv})
   # Keep the prior full raw state and apply the evidence-backed per-tag delta.
   prev_owned=copy.deepcopy(states[-1][1].get("nativeTagsOwned",{}))
   prev_ref=copy.deepcopy(states[-1][1].get("nativeTagsReferenced",{}))
   for d in raw:
    target=prev_owned if d["role"]=="owned" else prev_ref
    if d["after"]=="ABSENT": target.pop(str(d["id"]),None)
    else: target[str(d["id"])]=d["after"]
   next_state["nativeTagsOwned"]=prev_owned
   next_state["nativeTagsReferenced"]=prev_ref
   next_state["nativeTags"]=flat_tags(prev_owned,prev_ref,names)
   next_state["rawTagDelta"]=raw
   next_state["source"]={"beforeBuild":before_build,"afterBuild":after_build,
      "beforeCommit":bybuild[before_build]["commit"],"afterCommit":bybuild[after_build]["commit"],
      "beforeXmlSha256":bybuild[before_build]["xmlSha256"],"afterXmlSha256":bybuild[after_build]["xmlSha256"]}
   states.append((day,next_state,next_state["source"]))
   prev=next_state; prev_xml=after_xml
  # The 215 value is a current/source correction, not a new dated balance event.
  cur=copy.deepcopy(next((c for c in cards if c["id"]==cid),None))
  if cur is None: raise ValueError(cid)
  if cid=="BOT_246":
   for t in cur.get("nativeTags",[]):
    if t["id"]==215: t["value"]=2
  cur=strip_type_fields(cur)
  cur["nativeTagsOwned"]=copy.deepcopy(current_xml[cid]["owned"])
  cur["nativeTagsReferenced"]=copy.deepcopy(current_xml[cid]["referenced"])
  # Store full release state, then only changed logical fields and confirmed raw deltas.
  date_map={}
  prev_state=None
  for i,(day,state,source) in enumerate(states):
   if i==0:
    entry=copy.deepcopy(state)
    entry["source"]=source
   else:
    old=prev_state
    entry={k:copy.deepcopy(v) for k,v in state.items()
           if k not in ("nativeTagsOwned","nativeTagsReferenced","rawTagDelta","source") and old.get(k,"__ABSENT__")!=v}
    # Keep full role snapshots when any confirmed raw delta occurs, with the sparse delta as the replay contract.
    if state.get("rawTagDelta"):
     entry["rawTagDelta"]=copy.deepcopy(state["rawTagDelta"])
    entry["source"]=source
   date_map[day]=entry
   prev_state=state
  data=read(ROOT/"data"/(cid+".json"))
  meta={"schemaVersion":2,"mode":data.get("mode"),"artworkProvenance":copy.deepcopy(data.get("artworkProvenance",{}))}
  out={"_meta":meta,"_current":cur}
  out.update(date_map)
  write(ROOT/"data"/(cid+".json"),out)
 for record in cards:
  record.update(strip_type_fields(record))
  if record["id"]=="BOT_246":
   for tag in record.get("nativeTags",[]):
    if int(tag["id"])==215: tag["value"]=2
 write(ROOT/"cards.json",catalog)
 print(json.dumps({"migratedCards":len(ids),"initialCards":sum(1 for c in cards if c["id"]!="BOT_700"),"newGameplayEvents":sum(len(x) for x in NEW_EVENTS.values()),"dateCorrections":DATE_FIX,"requiredXmlBuilds":sorted(required)},ensure_ascii=False))
if __name__=="__main__": main()
