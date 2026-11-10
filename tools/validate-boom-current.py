#!/usr/bin/env python3
"""Independent final Boomsday validator: immutable XML, every card/date, raw roles and legacy replay."""
import copy,hashlib,json,re,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE="a947de650d42b47c8dca15cc0dd4f829a970a535"
DATE=re.compile(r"^\d{4}-\d{2}-\d{2}$")
def read(p): return json.loads(p.read_text(encoding="utf-8"))
def git_json(path): return json.loads(subprocess.check_output(["git","show",f"{BASE}:{path}"],cwd=ROOT,text=True))
def parse_xml(path,wanted):
 out={}
 for _,e in ET.iterparse(path,events=("end",)):
  if e.tag.rsplit("}",1)[-1]!="Entity": continue
  cid=e.attrib.get("CardID")
  if cid in wanted:
   owned={}; refs={}
   for t in list(e):
    kind=t.tag.rsplit("}",1)[-1]
    if kind not in ("Tag","ReferencedTag") or "enumID" not in t.attrib: continue
    target=owned if kind=="Tag" else refs
    target[str(int(t.attrib["enumID"]))]=str(t.attrib.get("value",""))
   if cid in out: raise AssertionError((path,cid,"duplicate entity"))
   out[cid]={"owned":owned,"referenced":refs}
  e.clear()
 return out
def apply(state,row):
 out=copy.deepcopy(state)
 for k,v in row.items():
  if k not in ("rawTagDelta","source"): out[k]=copy.deepcopy(v)
 for d in row.get("rawTagDelta",[]):
  key="nativeTagsOwned" if d["role"]=="owned" else "nativeTagsReferenced"
  m=out.setdefault(key,{})
  tid=str(d["id"])
  assert m.get(tid,"ABSENT")==d["before"],(d["id"],d["role"],tid,d["before"],m.get(tid,"ABSENT"))
  if d["after"]=="ABSENT": m.pop(tid,None)
  else: m[tid]=str(d["after"])
 return out
def main():
 xml_dir=Path(sys.argv[1]) if len(sys.argv)>1 else Path("/tmp/boom-xml")
 manifest=read(ROOT/"sources/archive-manifest.json")
 bybuild={int(x["build"]):x for x in manifest["entries"]}
 catalog=read(ROOT/"cards.json"); render=read(ROOT/"render.json"); legacy=read(ROOT/"history.json"); central=read(ROOT/"data/history.json")
 cards=catalog["cards"]; ids={x["id"] for x in cards}; byid={x["id"]:x for x in cards}; rbyid={x["id"]:x for x in render["cards"]}
 assert len(manifest["entries"])==37 and all(len(x["commit"])==40 and len(x["xmlSha256"])==64 for x in manifest["entries"])
 xml={}
 for build in (25770,26757,27358,31022,31268,33157,33402,44222,77662,155409,158725,163976,165029,168129,168788,170126,170824,198314,198608,209698,210009,195316,195635,217489,217964,237510,247416,256589):
  meta=bybuild[build]; path=xml_dir/f"{build}.xml"
  assert hashlib.sha256(path.read_bytes()).hexdigest()==meta["xmlSha256"],(build,"XML SHA")
  parsed=parse_xml(path,ids)
  assert len(parsed)==meta["observedCardCount"],(build,"entity count")
  assert set(ids)-set(parsed)==set(meta.get("absentOriginalIds",[])),(build,"missing original IDs")
  xml[build]=parsed
 assert len(cards)==155 and sum(bool(x.get("collectible")) for x in cards)==136
 assert len(obs["intentionalRulesAndAvailability"])==9 and len(obs["displayAndNativeRepresentationContext"])==11
 assert sum(not bool(x.get("collectible")) for x in cards)==19
 assert central["format"]=="date-first-delta-v2"
 assert (central["initialStates"],central["followupEvents"],central["totalStates"])==(155,78,233)
 assert len(central["events"]["2018-08-08"])==154 and "BOT_700" not in central["events"]["2018-08-08"]
 assert "BOT_700" in central["events"]["2019-06-04"]
 assert len(central["events"]["2019-06-04"])==21 and len(central["events"]["2019-08-27"])==4
 assert len(central["events"]["2022-11-30"])==7 and len(central["events"]["2023-02-15"])==12
 assert len(central["events"]["2023-04-05"])==4
 assert "2022-12-07" not in central["events"] and "2024-11-06" not in central["events"]
 assert len(central["events"]["2024-03-12"])==1 and len(central["events"]["2025-03-19"])==3
 # Immutable current preservation from original prepared API.
 original=git_json("cards.json")
 old={x["id"]:x for x in original["cards"]}
 omit={"MINION":{"durability":0,"armor":0,"spellSchool":""},
 "SPELL":{"attack":0,"health":0,"durability":0,"armor":0,"races":[],"race":""},
 "WEAPON":{"health":0,"armor":0,"spellSchool":"","races":[],"race":""},
 "HERO":{"attack":0,"durability":0,"spellSchool":"","races":[],"race":""},
 "HERO_POWER":{"attack":0,"health":0,"durability":0,"armor":0,"spellSchool":"","races":[],"race":""}}
 for cid,cur in byid.items():
  expected=copy.deepcopy(old[cid])
  for k,v in omit.get(expected["type"],{}).items():
   if expected.get(k,"ABSENT")==v: expected.pop(k,None)
  if cid=="BOT_246":
   for t in expected["nativeTags"]:
    if t["id"]==215: t["value"]=2
  diff={k:(expected.get(k,"ABSENT"),cur.get(k,"ABSENT")) for k in sorted(set(expected)|set(cur)) if expected.get(k,"ABSENT")!=cur.get(k,"ABSENT")}
  assert cur==expected,(cid,"current API changed beyond approved type omissions and BOT_246 Tag215",diff)
  src=read(ROOT/"data"/(cid+".json")); olddata=git_json("data/"+cid+".json")
  assert src["_meta"]["mode"]==olddata["mode"] and src["_meta"]["artworkProvenance"]==olddata["artworkProvenance"],(cid,"mode/artwork provenance")
  assert src["_current"]["portrait"]==olddata["card"]["portrait"] and src["_current"]["art"]==olddata["card"]["art"]
  type_omit_for_card={"MINION":{"durability":0,"armor":0,"spellSchool":""},"SPELL":{"attack":0,"health":0,"durability":0,"armor":0,"races":[],"race":""},"WEAPON":{"health":0,"armor":0,"spellSchool":"","races":[],"race":""},"HERO":{"attack":0,"durability":0,"spellSchool":"","races":[],"race":""},"HERO_POWER":{"attack":0,"health":0,"durability":0,"armor":0,"spellSchool":"","races":[],"race":""}}.get(byid[cid]["type"],{})
  for field,value in olddata["card"].items():
   if field not in byid[cid] and type_omit_for_card.get(field,"__NOT_OMITTED__")!=value:
    assert src["_current"].get(field,"ABSENT")==value,(cid,field,"preserve original extra relation/current field")
  assert src["_current"]["nativeTagsOwned"]==xml[256589][cid]["owned"],(cid,"current owned raw")
  assert src["_current"]["nativeTagsReferenced"]==xml[256589][cid]["referenced"],(cid,"current referenced raw")
  days=sorted(k for k in src if DATE.fullmatch(k))
  assert days[0]==("2019-06-04" if cid=="BOT_700" else "2018-08-08"),(cid,"first date")
  release_build=31268 if cid=="BOT_700" else 25770
  state=copy.deepcopy(src[days[0]])
  assert state["nativeTagsOwned"]==xml[release_build][cid]["owned"],(cid,"release owned raw")
  assert state["nativeTagsReferenced"]==xml[release_build][cid]["referenced"],(cid,"release referenced raw")
  assert state["nativeTags"].count({"id":48,"name":"마나 비용","value":6})==0 or cid not in ("BOT_422a","BOT_422b")
  for day in days[1:]:
   row=src[day]; source=row["source"]
   before_build=source["beforeBuild"]; after_build=source["afterBuild"]
   assert source["beforeCommit"]==bybuild[before_build]["commit"]
   assert source["afterCommit"]==bybuild[after_build]["commit"]
   before=xml[before_build][cid]; after=xml[after_build][cid]
   for d in row.get("rawTagDelta",[]):
    role=d["role"]; tid=str(d["id"])
    assert before[role].get(tid,"ABSENT")==d["before"],(cid,day,role,tid,"XML before")
    assert after[role].get(tid,"ABSENT")==d["after"],(cid,day,role,tid,"XML after")
   prev=copy.deepcopy(state)
   state=apply(state,row)
   for k,v in row.items():
    if k in ("rawTagDelta","source"): continue
    assert prev.get(k,"ABSENT")!=v,(cid,day,k,"redundant sparse delta")
   assert central["events"][day][cid]==row,(cid,day,"central source mismatch")
  # Every date is available through public render/history and current+changes/removedFields.
  current=copy.deepcopy(rbyid[cid]); revisions=current.get("history",[])
  for day in days:
   rev=next((x for x in revisions if x.get("from")==day),None)
   assert rev is not None,(cid,day,"missing legacy reverse revision")
   restored={k:copy.deepcopy(v) for k,v in current.items() if k!="history"}
   restored.update(copy.deepcopy(rev["changes"]))
   for k in rev.get("removedFields",[]): restored.pop(k,None)
   target=copy.deepcopy(src[days[0]])
   for d in days[1:]:
    if d>day: break
    target=apply(target,src[d])
   for k in ("name","type","cardClass","classes","rarity","collectible","cost","attack","health","durability","armor","text","races","race","spellSchool","mechanics","nativeTags","nativeTagsOwned","nativeTagsReferenced"):
    assert restored.get(k,"ABSENT")==target.get(k,"ABSENT"),(cid,day,k,"legacy consumer replay")
 # Four confirmed representation events are dated separately from gameplay.
 assert central["events"]["2024-03-12"]["BOT_237"]["eventKind"]=="confirmed-representation"
 assert central["events"]["2025-03-19"]["BOT_042t"]["eventKind"]=="confirmed-representation"
 for cid,health in (("BOT_042t",3),("BOT_286",2),("BOT_406",3)):
  src=read(ROOT/"data"/(cid+".json")); row=src["2025-03-19"]
  raw={(x["role"],int(x["id"])):(x["before"],x["after"]) for x in row["rawTagDelta"]}
  assert raw[("owned",187)]==("3" if cid!="BOT_286" else "2","ABSENT"),(cid,"DURABILITY removal")
  assert raw[("owned",45)]==("ABSENT",str(health)),(cid,"HEALTH storage")
  state=copy.deepcopy(src["2018-08-08"])
  for d in sorted(k for k in src if DATE.fullmatch(k) and k<="2025-03-19" and k!="2018-08-08"):
   state=apply(state,src[d])
  assert state["nativeTagsOwned"].get("45")==str(health),(cid,"same durability stored as HEALTH")
  assert state.get("durability")==src["2018-08-08"].get("durability"),(cid,"no logical durability change")
 row=read(ROOT/"data/BOT_237.json")["2024-03-12"]
 assert row["text"]=="<b>합체</b>, <b>모면</b>"
 raw={(x["role"],int(x["id"])):(x["before"],x["after"]) for x in row["rawTagDelta"]}
 assert raw[("owned",311)]==("1","ABSENT") and raw[("owned",332)]==("1","ABSENT")
 assert raw[("owned",1211)]==("ABSENT","1")
 assert central["events"]["2018-10-19"]["BOT_270"]["dateConfidence"]=="candidate"
 # Explicit card-specific constraints.
 for cid in ("BOT_031","BOT_537","BOT_558"): assert byid[cid]["attack"]==0
 for cid in ("BOT_246","BOT_517"): assert byid[cid]["cost"]==0
 for cid in ("BOT_042t","BOT_066t","BOT_309","BOT_312t","BOT_445t","BOT_537t"): assert byid[cid]["text"]==""
 assert byid["BOT_238"]["health"]==30 and byid["BOT_238"]["armor"]==7
 for cid,v in (("BOT_042t",3),("BOT_286",2),("BOT_406",3)):
  assert "health" not in byid[cid] and any(x["id"]==45 and x["value"]==v for x in byid[cid]["nativeTags"])
 assert byid["BOT_246"]["cost"]==0 and next(x for x in byid["BOT_246"]["nativeTags"] if x["id"]==215)["value"]==2
 assert read(ROOT/"data/BOT_246.json")["2018-08-08"]["nativeTagsOwned"]["215"]=="2"
 assert read(ROOT/"data/BOT_246.json")["2021-03-26"]["spellSchool"]=="NATURE"
 assert read(ROOT/"data/BOT_246.json")["_current"]["nativeTagsOwned"]["215"]=="2"
 for cid in ("BOT_422a","BOT_422b"):
  src=read(ROOT/"data"/(cid+".json"))
  assert "48" not in src["2018-08-08"]["nativeTagsOwned"],(cid,"choice UI launch raw COST absent")
  assert all("cost" not in src[d] for d in src if DATE.fullmatch(d)),(cid,"choice UI cost must remain undated")
  assert byid[cid]["cost"]==6 and src["_current"]["cost"]==6
 assert len(legacy["cards"])==sum(1 for c in cards if rbyid[c["id"]].get("history"))
 # All 85 repaired current text strings remain untouched.
 for cid,oldcard in old.items():
  assert byid[cid].get("text","")==oldcard.get("text",""),(cid,"text changed")
 assert sum("<br></br>" in x.get("text","") for x in cards)==85
  assert byid[cid].get("flavor","")==oldcard.get("flavor",""),(cid,"flavor changed")
 print(json.dumps({"cards":155,"xmlSnapshots":len(xml),"initialStates":155,"followupEvents":78,"totalStates":233,"rawTagEventsChecked":sum(len(read(ROOT/"data"/(cid+".json"))[d].get("rawTagDelta",[])) for cid in ids for d in read(ROOT/"data"/(cid+".json")) if DATE.fullmatch(d)),"legacyHistoryCards":len(legacy["cards"]),"rules":9,"representationGroups":11,"grammarSuggestions":8},ensure_ascii=False))
if __name__=="__main__": main()
