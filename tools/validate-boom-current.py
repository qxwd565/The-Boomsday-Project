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
   owned={}; refs={}; strings={}
   for t in list(e):
    kind=t.tag.rsplit("}",1)[-1]
    if kind not in ("Tag","ReferencedTag") or "enumID" not in t.attrib: continue
    tid=str(int(t.attrib["enumID"]))
    target=owned if kind=="Tag" else refs
    target[tid]=str(t.attrib.get("value",""))
    if kind=="Tag" and tid in ("184","185"):
     locales={}
     for child in list(t.iter())[1:]:
      locale=child.tag.rsplit("}",1)[-1]
      if locale in ("koKR","enUS"):
       locales[locale]={"present":True,"value":"".join(child.itertext())}
     strings[tid]={"present":True,"locales":locales,"valueAttributePresent":"value" in t.attrib,
                   "valueAttribute":t.attrib.get("value"),"textContent":"".join(t.itertext())}
   if cid in out: raise AssertionError((path,cid,"duplicate entity"))
   dbf_id=e.attrib.get("ID")
   out[cid]={"dbfId":int(dbf_id) if dbf_id and dbf_id.isdigit() else None,"owned":owned,"referenced":refs,"strings":strings}
  e.clear()
 return out
def display_text(raw):
 return raw.replace("[x]","").replace("\r\n","\n").replace("\r","\n").replace("\n","<br></br>")
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
 catalog=read(ROOT/"cards.json"); render=read(ROOT/"render.json"); legacy=read(ROOT/"history.json"); central=read(ROOT/"data/history.json"); obs=read(ROOT/"sources/boomsday-observations.json")
 cards=catalog["cards"]; ids={x["id"] for x in cards}; byid={x["id"]:x for x in cards}; rbyid={x["id"]:x for x in render["cards"]}
 assert len(manifest["entries"])==37 and all(len(x["commit"])==40 and len(x["xmlSha256"])==64 and len(x["extractionSha256"])==64 and len(x["gitBlobSHA1"])==40 for x in manifest["entries"])
 xml={}
 for build in sorted(bybuild):
  meta=bybuild[build]; path=xml_dir/f"{build}.xml"
  assert hashlib.sha256(path.read_bytes()).hexdigest()==meta["xmlSha256"],(build,"XML SHA")
  parsed=parse_xml(path,ids)
  assert len(parsed)==meta["observedCardCount"],(build,"entity count")
  assert set(ids)-set(parsed)==set(meta.get("absentOriginalIds",[])),(build,"missing original IDs")
  for cid,item in parsed.items(): assert item["dbfId"]==byid[cid]["dbfId"],(build,cid,"immutable XML DBF ID")
  xml[build]=parsed
 # Parse and inspect every immutable archive in the 37-entry manifest, including
 # intermediate snapshots used only to establish undated representation changes.
 assert len(xml)==37 and set(xml)==set(bybuild)
 def xml_tag(cid,build,role,tag_id):
  return xml[build][cid][role].get(str(tag_id),"ABSENT")
 def xml_text(cid,build,locale="koKR"):
  return xml[build][cid]["strings"].get("184",{}).get("locales",{}).get(locale,{}).get("value")
 def undated_tag(cid,tag_id,role,before,after):
  matches=[x for x in central.get("observations",{}).get("undatedRawTags",{}).get(cid,[])
           if x["tagId"]==tag_id and x["role"]==role]
  assert any(x["before"]==before and x["after"]==after and x["date"] is None for x in matches),(
   cid,tag_id,role,before,after,"undated raw-tag observation")
 # R001: choice UI cost metadata only; no dated gameplay COST event.
 for cid in ("BOT_422a","BOT_422b"):
  assert xml_tag(cid,30103,"owned",48)=="ABSENT" and xml_tag(cid,30795,"owned",48)=="6",(cid,"choice COST XML")
 assert xml_text("BOT_422a",30103)=="[x]내 다른 하수인들에게\\n+1/+1을 부여합니다."
 assert xml_text("BOT_422a",30795)==xml_text("BOT_422a",30103)
 assert xml_text("BOT_422b",30103)=="2/2 나무정령을 둘 소환합니다."
 assert xml_text("BOT_422b",30795)==xml_text("BOT_422b",30103)
 for cid in ("BOT_422a","BOT_422b"):
  undated=central["observations"]["undated"][cid]["cost"]
  assert undated["date"] is None and undated["before"]=="ABSENT" and undated["after"]==6,(cid,"undated choice cost")
  undated_tag(cid,48,"owned","ABSENT","6")
 # R002: non-collectible token rarity metadata removal, not gameplay.
 assert xml_tag("BOT_270t",27358,"owned",203)=="1"
 assert xml_tag("BOT_270t",27405,"owned",203)=="ABSENT"
 assert xml_text("BOT_270t",27358)==xml_text("BOT_270t",27405)
 undated_tag("BOT_270t",203,"owned","1","ABSENT")
 # R003: OVERLOAD_OWED removal does not change owned OVERLOAD or printed wording.
 for cid,value in (("BOT_246","2"),("BOT_451","1")):
  assert xml_tag(cid,28556,"owned",296)==value
  assert xml_tag(cid,28855,"owned",296)=="ABSENT"
  assert xml_tag(cid,28556,"owned",215)==value and xml_tag(cid,28855,"owned",215)==value
  assert xml_text(cid,28556)==xml_text(cid,28855)
  undated_tag(cid,296,"owned",value,"ABSENT")
 # R004: SPELLPOWER raw normalization leaves printed +2 text intact.
 assert xml_tag("BOT_604",209698,"owned",192)=="2"
 assert xml_tag("BOT_604",210009,"owned",192)=="1"
 assert xml_text("BOT_604",209698)=="<b>주문 공격력 +2</b>"
 assert xml_text("BOT_604",210009)==xml_text("BOT_604",209698)
 undated_tag("BOT_604",192,"owned","2","1")
 # R007: temporary wording is an undated observation, with exact [x] and LF.
 bot568_before="[x]카드를 3장 뽑습니다.\\n내 턴이 끝날 때,\\n그 카드들을 버립니다."
 bot568_after="[x]카드를 3장 뽑습니다.\\n그 카드들은 <b>일시적</b>입니다."
 assert xml_text("BOT_568",202360)==bot568_before
 assert xml_text("BOT_568",203120)==bot568_after
 assert xml_tag("BOT_568",202360,"referenced",3630)=="ABSENT"
 assert xml_tag("BOT_568",203120,"referenced",3630)=="1"
 for field,value in (("text",display_text(bot568_before)),("nativeRawText",bot568_before)):
  observation=central["observations"]["undated"]["BOT_568"][field]
  assert observation["date"] is None and observation["before"]==value,(field,"BOT_568 undated before")
 assert central["observations"]["undated"]["BOT_568"]["nativeRawText"]["after"]==bot568_after
 undated_tag("BOT_568",3630,"referenced","ABSENT","1")
 # R008: original bomb text keeps [x]; later keyword wording has no invented date.
 bot511_before="[x]내게 피해를 5 줍니다.\\n카드를 1장 뽑습니다.\\n이 카드를 뽑아도\\n폭발합니다."
 bot511_after="<b>뽑을 때 시전</b>\\n내게 피해를 5 줍니다."
 assert xml_text("BOT_511t",25770)==bot511_before
 assert xml_text("BOT_511t",26757)==bot511_after
 assert xml_tag("BOT_511t",26757,"referenced",1077)=="1"
 undated=central["observations"]["undated"]["BOT_511t"]["nativeRawText"]
 assert undated["date"] is None and undated["before"]==bot511_before,("BOT_511t undated raw")
 # R009: six Discover references move from ReferencedTag 415 to owned Tag 415.
 discover_cards=("BOT_238p4","BOT_243","BOT_402","BOT_419","BOT_435","BOT_539")
 for cid in discover_cards:
  assert xml_tag(cid,31761,"referenced",415)=="1",(cid,"discover reference before")
  assert xml_tag(cid,32708,"referenced",415)=="ABSENT",(cid,"discover reference after")
  assert xml_tag(cid,32708,"owned",415)=="1",(cid,"discover owned after")
  undated_tag(cid,415,"referenced","1","ABSENT")
  undated_tag(cid,415,"owned","ABSENT","1")
 for cid in ("BOT_238p4","BOT_435"):
  assert xml_tag(cid,31761,"referenced",1052)=="1"
  assert xml_tag(cid,32708,"owned",1052)=="1" and xml_tag(cid,32708,"referenced",1052)=="ABSENT"
 for cid in ("BOT_243","BOT_402","BOT_419","BOT_539"):
  assert xml_tag(cid,32708,"owned",1342)=="1"
 # BOT_237: launch wording is not the later pre-29.0 wording; only the confirmed
 # 2024 representation transition is dated.
 assert xml_text("BOT_237",25770)=="<b>합체</b>, 이 하수인은 주문이나 영웅 능력의 대상으로 지정되지 않습니다."
 assert xml_text("BOT_237",195316)=="[x]<b>합체</b>, 주문이나\\n영웅 능력의 대상으로\\n지정되지 않습니다."
 assert xml_text("BOT_237",195635)=="<b>합체</b>, <b>모면</b>"
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
  assert src["_meta"]["launchStrings"]==xml[release_build][cid]["strings"],(cid,"launch Tag184/185 XML strings")
  assert src["_meta"]["currentStrings"]==xml[256589][cid]["strings"],(cid,"current Tag184/185 XML strings")
  launch_strings=src["_meta"]["launchStrings"]; current_strings=src["_meta"]["currentStrings"]
  assert src["_meta"]["launchStringTagPresence"]=={"184":"184" in launch_strings,"185":"185" in launch_strings}
  assert src["_meta"]["currentStringTagPresence"]=={"184":"184" in current_strings,"185":"185" in current_strings}
  launch_name=launch_strings.get("185",{}).get("locales",{}).get("koKR")
  if launch_name is not None: assert src[days[0]]["name"]==launch_name["value"],(cid,"launch CARDNAME")
  launch_text=src["_meta"]["launchStrings"].get("184",{}).get("locales",{}).get("koKR")
  if launch_text is not None:
   assert src[days[0]]["nativeRawText"]==launch_text["value"],(cid,"launch raw text")
   assert src[days[0]]["text"]==display_text(launch_text["value"]),(cid,"launch display text")
  else:
   assert "nativeRawText" not in src[days[0]] and "text" not in src[days[0]],(cid,"absent launch text")
  current_name=current_strings.get("185",{}).get("locales",{}).get("koKR")
  if current_name is not None:
   assert src["_current"]["name"]==current_name["value"] and byid[cid]["name"]==current_name["value"],(cid,"current CARDNAME")
  current_text=current_strings.get("184",{}).get("locales",{}).get("koKR")
  if current_text is not None:
   assert src["_current"]["nativeRawText"]==current_text["value"],(cid,"current raw text")
   assert rbyid[cid].get("nativeRawText")==current_text["value"],(cid,"render current raw text")
  else:
   assert "nativeRawText" not in src["_current"] and "nativeRawText" not in rbyid[cid],(cid,"absent current raw text")
  state=copy.deepcopy(src[days[0]])
  assert state["nativeTagsOwned"]==xml[release_build][cid]["owned"],(cid,"release owned raw")
  assert state["nativeTagsReferenced"]==xml[release_build][cid]["referenced"],(cid,"release referenced raw")
  assert state["nativeTags"].count({"id":48,"name":"마나 비용","value":6})==0 or cid not in ("BOT_422a","BOT_422b")
  for day in days[1:]:
   row=src[day]; source=row["source"]
   assert source["beforeStrings"]==xml[source["beforeBuild"]][cid]["strings"],(cid,day,"before localized strings")
   assert source["afterStrings"]==xml[source["afterBuild"]][cid]["strings"],(cid,day,"after localized strings")
   if "nativeRawText" in row:
    assert row["nativeRawText"]==source["afterStrings"]["184"]["locales"]["koKR"]["value"],(cid,day,"dated raw text evidence")
    assert row["text"]==display_text(row["nativeRawText"]),(cid,day,"dated display text evidence")
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
   for k in ("name","type","cardClass","classes","rarity","collectible","cost","attack","health","durability","armor","text","races","race","spellSchool","mechanics","nativeRawText","nativeTags","nativeTagsOwned","nativeTagsReferenced"):
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
 bot237=read(ROOT/"data/BOT_237.json")
 launch_raw=bot237["_meta"]["launchStrings"]["184"]["locales"]["koKR"]["value"]
 assert launch_raw=="<b>합체</b>, 이 하수인은 주문이나 영웅 능력의 대상으로 지정되지 않습니다."
 assert bot237["2018-08-08"]["nativeRawText"]==launch_raw
 assert bot237["2018-08-08"]["text"]=="<b>합체</b>, 이 하수인은 주문이나 영웅 능력의 대상으로 지정되지 않습니다."
 row=bot237["2024-03-12"]
 assert row["nativeRawText"]=="<b>합체</b>, <b>모면</b>"
 assert row["text"]=="<b>합체</b>, <b>모면</b>"
 raw={(x["role"],int(x["id"])):(x["before"],x["after"]) for x in row["rawTagDelta"]}
 assert raw[("owned",311)]==("1","ABSENT") and raw[("owned",332)]==("1","ABSENT")
 assert raw[("owned",1211)]==("ABSENT","1")
 assert central["events"]["2018-10-19"]["BOT_270"]["dateConfidence"]=="candidate"
 for cid in ("BOT_568","BOT_511t"):
  undated=central["observations"]["undated"][cid]
  assert undated["text"]["date"] is None and undated["nativeRawText"]["date"] is None,(cid,"wording remains undated")
 assert read(ROOT/"data/BOT_568.json")["2018-08-08"]["nativeRawText"]=="[x]카드를 3장 뽑습니다.\n내 턴이 끝날 때,\n그 카드들을 버립니다."
 assert read(ROOT/"data/BOT_511t.json")["2018-08-08"]["nativeRawText"]=="[x]내게 피해를 5 줍니다.\n카드를 1장 뽑습니다.\n이 카드를 뽑아도\n폭발합니다."
 assert read(ROOT/"data/BOT_444.json")["2018-08-08"]["nativeRawText"]=="이번 턴에\n하수인이 죽을 때마다 이번 턴에만 마나\u00a0수정을 1개 획득합니다."
 assert read(ROOT/"data/BOT_444.json")["2018-08-08"]["text"]==display_text(read(ROOT/"data/BOT_444.json")["2018-08-08"]["nativeRawText"])
 assert read(ROOT/"data/BOT_558.json")["2018-08-08"]["nativeRawText"]=="<b>죽음의 메아리:</b>\n내가 이 하수인에게\n시전한 모든 주문을 내 손으로 가져옵니다."
 assert read(ROOT/"data/BOT_558.json")["2018-08-08"]["text"]==display_text(read(ROOT/"data/BOT_558.json")["2018-08-08"]["nativeRawText"])
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
  assert byid[cid].get("flavor","")==oldcard.get("flavor",""),(cid,"flavor changed")
 assert sum("<br></br>" in x.get("text","") for x in cards)==85
 print(json.dumps({"cards":155,"xmlSnapshots":len(xml),"initialStates":155,"followupEvents":78,"totalStates":233,"rawTagEventsChecked":sum(len(read(ROOT/"data"/(cid+".json"))[d].get("rawTagDelta",[])) for cid in ids for d in read(ROOT/"data"/(cid+".json")) if DATE.fullmatch(d)),"legacyHistoryCards":len(legacy["cards"]),"rules":9,"representationGroups":11,"grammarSuggestions":8},ensure_ascii=False))
if __name__=="__main__": main()
