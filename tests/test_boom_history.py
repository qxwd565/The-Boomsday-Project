#!/usr/bin/env python3
import copy,json,re,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE="a947de650d42b47c8dca15cc0dd4f829a970a535"
DATE=re.compile(r"^\d{4}-\d{2}-\d{2}$")
def read(p): return json.loads(p.read_text(encoding="utf-8"))
def git_file(path):
 return json.loads(subprocess.check_output(["git","show",f"{BASE}:{path}"],cwd=ROOT,text=True))
def scalar(m): return {str(k):str(v) for k,v in m.items()}
def display_text(raw): return raw.replace("[x]","").replace("\r\n","\n").replace("\r","\n").replace("\n","<br></br>")
def apply_row(state,row):
 out=copy.deepcopy(state)
 for k,v in row.items():
  if k not in ("rawTagDelta","source"): out[k]=copy.deepcopy(v)
 for d in row.get("rawTagDelta",[]):
  key="nativeTagsOwned" if d["role"]=="owned" else "nativeTagsReferenced"
  tags=out.setdefault(key,{})
  tid=str(d["id"])
  assert tags.get(tid,"ABSENT")==d["before"],(d["id"],d["role"],tid,d["before"],tags.get(tid,"ABSENT"))
  if d["after"]=="ABSENT": tags.pop(tid,None)
  else: tags[tid]=str(d["after"])
 return out
def parse_xml(path,cid):
 found=None
 for _,e in ET.iterparse(path,events=("end",)):
  if e.tag.rsplit("}",1)[-1]=="Entity" and e.attrib.get("CardID")==cid:
   owned={}; refs={}
   for t in list(e):
    k=t.tag.rsplit("}",1)[-1]
    if k not in ("Tag","ReferencedTag") or "enumID" not in t.attrib: continue
    target=owned if k=="Tag" else refs
    target[str(int(t.attrib["enumID"]))]=str(t.attrib.get("value",""))
   found={"owned":owned,"referenced":refs}
  e.clear()
 return found
def check():
 catalog=read(ROOT/"cards.json"); render=read(ROOT/"render.json"); legacy=read(ROOT/"history.json")
 central=read(ROOT/"data/history.json"); obs=read(ROOT/"sources/boomsday-observations.json")
 baseline=git_file("cards.json")
 cards=catalog["cards"]; byid={x["id"]:x for x in cards}; rbyid={x["id"]:x for x in render["cards"]}
 assert len(cards)==155 and len(byid)==155
 assert obs["counts"]["missingGameplayEvents"]==23 and obs["counts"]["initialGameplayErrors"]==21 and obs["counts"]["existingLaterEventChecks"]==51
 assert sum(bool(x.get("collectible")) for x in cards)==136
 assert sum(not bool(x.get("collectible")) for x in cards)==19
 assert central["schema"]==2 and central["format"]=="date-first-delta-v2"
 assert (central["initialStates"],central["followupEvents"],central["totalStates"])==(155,78,233)
 assert len(central["events"]["2018-08-08"])==154
 assert "BOT_700" not in central["events"]["2018-08-08"]
 assert "BOT_700" in central["events"]["2019-06-04"]
 assert len(central["events"]["2019-06-04"])==21
 assert len(central["events"]["2019-08-27"])==4
 assert len(central["events"]["2022-11-30"])==7
 assert len(central["events"]["2023-02-15"])==12
 assert len(central["events"]["2023-04-05"])==4
 assert "2022-12-07" not in central["events"] and "2024-11-06" not in central["events"]
 assert len(central["events"]["2024-03-12"])==1 and len(central["events"]["2025-03-19"])==3
 assert "2018-10-19" in central["events"] and "BOT_270" in central["events"]["2018-10-19"]
 assert len(obs["intentionalRulesAndAvailability"])==9
 assert len(obs["displayAndNativeRepresentationContext"])==11
 assert len(obs["grammarSuggestions"])==8 and len(obs["grammarHold"])==1
 # Only approved current API changes: type-inapplicable fields omitted and BOT_246 Tag215 corrected.
 type_omit={"MINION":{"durability":0,"armor":0,"spellSchool":""},
  "SPELL":{"attack":0,"health":0,"durability":0,"armor":0,"races":[],"race":""},
  "WEAPON":{"health":0,"armor":0,"spellSchool":"","races":[],"race":""},
  "HERO":{"attack":0,"durability":0,"spellSchool":"","races":[],"race":""},
  "HERO_POWER":{"attack":0,"health":0,"durability":0,"armor":0,"spellSchool":"","races":[],"race":""}}
 base={x["id"]:x for x in baseline["cards"]}
 for cid,cur in byid.items():
  expected=copy.deepcopy(base[cid])
  for k,v in type_omit.get(expected["type"],{}).items():
   if expected.get(k,"ABSENT")==v: expected.pop(k,None)
  if cid=="BOT_246":
   for t in expected["nativeTags"]:
    if t["id"]==215: t["value"]=2
  diff={k:(expected.get(k,"ABSENT"),cur.get(k,"ABSENT")) for k in sorted(set(expected)|set(cur)) if expected.get(k,"ABSENT")!=cur.get(k,"ABSENT")}
  assert cur==expected,(cid,"current API changed outside approved omissions/BOT_246",diff)
  src=read(ROOT/"data"/(cid+".json"))
  old=git_file("data/"+cid+".json")
  assert src["_meta"]["mode"]==old["mode"],(cid,"mode")
  assert src["_meta"]["artworkProvenance"]==old["artworkProvenance"],(cid,"artwork provenance")
  assert src["_current"]["portrait"]==old["card"]["portrait"]
  assert src["_current"]["art"]==old["card"]["art"]
  type_omit_for_card={"MINION":{"durability":0,"armor":0,"spellSchool":""},"SPELL":{"attack":0,"health":0,"durability":0,"armor":0,"races":[],"race":""},"WEAPON":{"health":0,"armor":0,"spellSchool":"","races":[],"race":""},"HERO":{"attack":0,"durability":0,"spellSchool":"","races":[],"race":""},"HERO_POWER":{"attack":0,"health":0,"durability":0,"armor":0,"spellSchool":"","races":[],"race":""}}.get(cur["type"],{})
  for field,value in old["card"].items():
   if field not in cur and type_omit_for_card.get(field,"__NOT_OMITTED__")!=value:
    assert src["_current"].get(field,"ABSENT")==value,(cid,field,"preserve original extra relation/current field")
  assert src["_current"]["nativeTags"]==cur["nativeTags"]
  assert src["_meta"]["artworkProvenance"]["portrait"]==old["artworkProvenance"]["portrait"]
  days=sorted(k for k in src if DATE.fullmatch(k))
  assert days[0]==("2019-06-04" if cid=="BOT_700" else "2018-08-08"),(cid,days[0])
  state=copy.deepcopy(src[days[0]])
  assert state["id"]==cid and state["dbfId"]==cur["dbfId"]
  for day in days[1:]:
   row=src[day]
   prev=copy.deepcopy(state)
   state=apply_row(state,row)
   for k,v in row.items():
    if k in ("source","rawTagDelta"): continue
    assert prev.get(k,"ABSENT")!=v,(cid,day,k,"redundant sparse field")
   assert central["events"][day][cid]==row,(cid,day,"central sync mismatch")
  assert state["nativeTagsOwned"] and state["nativeTagsReferenced"] is not None
  # Old consumer: current render + reverse changes + removedFields must restore each dated state.
  current=copy.deepcopy(rbyid[cid])
  revisions=current.get("history",[])
  for day in days:
   rev=next((x for x in revisions if x.get("from")==day),None)
   assert rev is not None,(cid,day,"missing public history revision")
   restored={k:copy.deepcopy(v) for k,v in current.items() if k!="history"}
   restored.update(copy.deepcopy(rev["changes"]))
   for k in rev.get("removedFields",[]): restored.pop(k,None)
   target=copy.deepcopy(src[day])
   # Replay target's full state to this date.
   target=copy.deepcopy(src[days[0]])
   for d in days[1:]:
    if d>day: break
    target=apply_row(target,src[d])
   for k in ("name","type","cardClass","classes","rarity","collectible","cost","attack","health","durability","armor","text","races","race","spellSchool","mechanics","nativeRawText","nativeTags","nativeTagsOwned","nativeTagsReferenced"):
    assert restored.get(k,"ABSENT")==target.get(k,"ABSENT"),(cid,day,k,"legacy replay")
 # Immutable launch/current localized strings: preserve Tag presence, locale presence,
 # exact [x] markers and LF independently from display text.
 for cid,cur in byid.items():
  src=read(ROOT/"data"/(cid+".json"))
  launch=src["_meta"]["launchStrings"]; current=src["_meta"]["currentStrings"]
  for strings,label in ((launch,"launch"),(current,"current")):
   for tid in ("184","185"):
    if tid in strings:
     assert strings[tid]["present"] is True,(cid,label,tid,"tag presence")
     for locale in ("koKR","enUS"):
      if locale in strings[tid]["locales"]:
       assert strings[tid]["locales"][locale]["present"] is True,(cid,label,tid,locale)
  release_day="2019-06-04" if cid=="BOT_700" else "2018-08-08"
  launch_text=launch.get("184",{}).get("locales",{}).get("koKR")
  if launch_text is not None:
   assert src[release_day]["nativeRawText"]==launch_text["value"],(cid,"launch raw text")
   assert src[release_day]["text"]==launch_text["value"].replace("[x]","").replace("\\r\\n","\\n").replace("\\r","\\n").replace("\\n","<br></br>"),(cid,"launch display text")
  else:
   assert "nativeRawText" not in src[release_day] and "text" not in src[release_day],(cid,"absent launch CARDTEXT")
  current_text=current.get("184",{}).get("locales",{}).get("koKR")
  if current_text is not None:
   assert src["_current"]["nativeRawText"]==current_text["value"],(cid,"current raw text")
  else:
   assert "nativeRawText" not in src["_current"],(cid,"absent current CARDTEXT")
 bot237=read(ROOT/"data/BOT_237.json")
 assert bot237["_meta"]["launchStrings"]["184"]["locales"]["koKR"]["value"]=="<b>합체</b>, 이 하수인은 주문이나 영웅 능력의 대상으로 지정되지 않습니다."
 assert bot237["2018-08-08"]["nativeRawText"]=="<b>합체</b>, 이 하수인은 주문이나 영웅 능력의 대상으로 지정되지 않습니다."
 assert bot237["2024-03-12"]["nativeRawText"]==bot237["2024-03-12"]["source"]["afterStrings"]["184"]["locales"]["koKR"]["value"]
 assert read(ROOT/"data/BOT_568.json")["2018-08-08"]["nativeRawText"]=="카드를 3장 뽑습니다.\n내 턴이 끝날 때,\n그 카드들을 버립니다."
 assert read(ROOT/"data/BOT_511t.json")["2018-08-08"]["nativeRawText"]=="내게 피해를 5 줍니다.\n카드를 1장 뽑습니다.\n이 카드를 뽑아도\n폭발합니다."
 # 21 corrected launch values.
 initial_fixes={"BOT_021":{"attack":1},"BOT_066":{"races":["MECHANICAL"],"race":"기계"},
 "BOT_066t":{"races":["MECHANICAL"],"race":"기계"},"BOT_251":{"races":["MECHANICAL"],"race":"기계"},
 "BOT_283":{"races":["MECHANICAL"],"race":"기계"},"BOT_312":{"health":1},
 "BOT_444":{"text":"이번 턴에\n하수인이 죽을 때마다 이번 턴에만 마나\u00a0수정을 1개 획득합니다."},
 "BOT_445":{"races":["MECHANICAL"],"race":"기계"},"BOT_445t":{"races":["MECHANICAL"],"race":"기계"},
 "BOT_448":{"races":["MECHANICAL"],"race":"기계"},"BOT_523":{"races":["MECHANICAL"],"race":"기계"},
 "BOT_533":{"health":2},"BOT_534":{"races":["MECHANICAL"],"race":"기계"},
 "BOT_537t":{"races":["MECHANICAL"],"race":"기계"},
 "BOT_558":{"text":"<b>죽음의 메아리:</b>\n내가 이 하수인에게\n시전한 모든 주문을 내 손으로 가져옵니다."},
 "BOT_559":{"races":["BEAST"],"race":"야수"},"BOT_562":{"races":["MECHANICAL"],"race":"기계"},
 "BOT_563":{"attack":5},"BOT_573":{"races":["BEAST"],"race":"야수"},
 "BOT_603":{"races":["MECHANICAL"],"race":"기계"},"BOT_700":{"races":["MECHANICAL"],"race":"기계"}}
 for cid,fields in initial_fixes.items():
  day="2019-06-04" if cid=="BOT_700" else "2018-08-08"
  for k,v in fields.items(): assert read(ROOT/"data"/(cid+".json"))[day][k]==v,(cid,k,"initial fix")
 # Confirmed representation history is dated, but does not alter gameplay stats.
 assert central["events"]["2024-03-12"]["BOT_237"]["eventKind"]=="confirmed-representation"
 assert central["events"]["2025-03-19"]["BOT_042t"]["eventKind"]=="confirmed-representation"
 for cid,health in (("BOT_042t",3),("BOT_286",2),("BOT_406",3)):
  src=read(ROOT/"data"/(cid+".json")); row=src["2025-03-19"]
  raw={(x["role"],int(x["id"])):(x["before"],x["after"]) for x in row["rawTagDelta"]}
  assert raw.get(("owned",187))==("3" if cid!="BOT_286" else "2","ABSENT"),(cid,"Tag187 expected removal",raw)
  assert raw.get(("owned",45))==("ABSENT",str(health)),(cid,"HEALTH storage delta",raw)
  state=copy.deepcopy(src["2018-08-08"])
  for d in sorted(k for k in src if DATE.fullmatch(k) and k<="2025-03-19" and k!="2018-08-08"):
   state=apply_row(state,src[d])
  assert state["nativeTagsOwned"].get("45")==str(health)
  assert state.get("durability")==src["2018-08-08"].get("durability")
 bot237=read(ROOT/"data/BOT_237.json")
 assert bot237["2018-08-08"]["nativeRawText"]=="[x]<b>합체</b>, 주문이나\n영웅 능력의 대상으로\n지정되지 않습니다."
 assert bot237["2018-08-08"]["text"]=="<b>합체</b>, 주문이나<br></br>영웅 능력의 대상으로<br></br>지정되지 않습니다."
 row=bot237["2024-03-12"]
 assert row["nativeRawText"]=="<b>합체</b>, <b>모면</b>"
 assert row["text"]=="<b>합체</b>, <b>모면</b>"
 raw={(x["role"],int(x["id"])):(x["before"],x["after"]) for x in row["rawTagDelta"]}
 assert raw[("owned",311)]==("1","ABSENT") and raw[("owned",332)]==("1","ABSENT")
 assert raw[("owned",1211)]==("ABSENT","1")
 assert central["events"]["2018-10-19"]["BOT_270"]["dateConfidence"]=="candidate"
 # Specific cautions and genuine zero/empty values.
 for cid in ("BOT_031","BOT_537","BOT_558"): assert byid[cid]["attack"]==0
 for cid in ("BOT_246","BOT_517"): assert byid[cid]["cost"]==0
 for cid in ("BOT_042t","BOT_066t","BOT_309","BOT_312t","BOT_445t","BOT_537t"): assert byid[cid]["text"]==""
 assert byid["BOT_238"]["health"]==30 and byid["BOT_238"]["armor"]==7
 for cid,want in (("BOT_042t",3),("BOT_286",2),("BOT_406",3)):
  assert byid[cid].get("health") is None
  assert any(x["id"]==45 and x["value"]==want for x in byid[cid]["nativeTags"])
 for cid in ("BOT_422a","BOT_422b"):
  src=read(ROOT/"data"/(cid+".json"))
  assert "48" not in src["2018-08-08"]["nativeTagsOwned"],(cid,"choice UI raw COST must be absent at launch")
  assert all("cost" not in src[d] for d in src if DATE.fullmatch(d)),(cid,"modern choice UI cost must not be backdated")
  assert byid[cid]["cost"]==6 and src["_current"]["cost"]==6
  assert central.get("observations",{}).get("undated",{}).get(cid,{}).get("cost",{}).get("date") is None


 assert any(x["id"]==215 and x["value"]==2 for x in byid["BOT_246"]["nativeTags"])
 bot246=read(ROOT/"data/BOT_246.json")
 bot246_state=copy.deepcopy(bot246["2018-08-08"])
 for day in sorted(d for d in bot246 if DATE.fullmatch(d) and d!="2018-08-08" and d<="2021-03-26"):
  bot246_state=apply_row(bot246_state,bot246[day])
 assert bot246_state["nativeTagsOwned"].get("215")=="2"
 assert bot246["_current"]["nativeTagsOwned"].get("215")=="2"
 # Current line-break repairs are unchanged from the immutable preparation snapshot.
 for cid,old in base.items():
  assert byid[cid].get("text","")==old.get("text",""),(cid,"current text changed")
  assert byid[cid].get("flavor","")==old.get("flavor",""),(cid,"current flavor changed")
 # The corrected legacy current nativeTags are byte-for-byte equivalent except BOT_246/215.
 for cid,old in base.items():
  a=copy.deepcopy(old["nativeTags"]); b=copy.deepcopy(byid[cid]["nativeTags"])
  if cid=="BOT_246":
   for x in a:
    if x["id"]==215: x["value"]=2
  assert a==b,(cid,"legacy nativeTags changed")
 # Confirm 156 source archive snapshots were not collapsed into an assumed same-day release.
 assert len([x for x in cards if x["id"]!="BOT_700"])==154
 assert len(legacy["cards"])==sum(1 for c in cards if rbyid[c["id"]].get("history"))
 print(json.dumps({"cards":155,"collectible":136,"nonCollectible":19,"initialStates":155,"followupEvents":78,"totalStates":233,"dateCorrections":5,"initialFixes":21,"missingGameplayEvents":23,"intentionalRules":9,"representationGroups":11,"grammarSuggestions":8,"grammarHold":1,"legacyHistoryCards":len(legacy["cards"])},ensure_ascii=False))
if __name__=="__main__": check()
