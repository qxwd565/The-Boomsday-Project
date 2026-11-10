#!/usr/bin/env python3
"""Enrich already-migrated Boomsday canonical sources with every native string Tag.

This is intentionally an augmentation pass: it never rebuilds date-first states,
changes flattened nativeTags, or invents dates for string differences.
"""
import copy, hashlib, json, sys, xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
LOCALES={"deDE","enUS","esES","esMX","frFR","itIT","jaJP","koKR","plPL","ptBR","ruRU","thTH","zhCN","zhTW"}

def read(path):
    return json.loads(path.read_text(encoding="utf-8"))

def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+"\n", encoding="utf-8", newline="\n")

def extract(path, wanted, expected_sha, expected_count):
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected_sha:
        raise ValueError(f"{path.name}: XML SHA mismatch {digest}")
    out={}
    for _, entity in ET.iterparse(path, events=("end",)):
        if entity.tag.rsplit("}",1)[-1] != "Entity":
            continue
        cid=entity.attrib.get("CardID")
        if cid not in wanted:
            entity.clear()
            continue
        tags={}
        for tag in list(entity):
            if tag.tag.rsplit("}",1)[-1] != "Tag" or "enumID" not in tag.attrib:
                continue
            tid=str(int(tag.attrib["enumID"]))
            locales={}
            for child in list(tag):
                locale=child.tag.rsplit("}",1)[-1]
                if locale in LOCALES:
                    locales[locale]={"present":True,"value":"".join(child.itertext())}
            tag_type=tag.attrib.get("type")
            if tag_type in ("String","LocString") or locales:
                if tag_type is None:
                    tag_type="LocString" if locales else "String"
                tags[tid]={
                    "present":True,
                    "type":tag_type,
                    "valueAttributePresent":"value" in tag.attrib,
                    "valueAttribute":tag.attrib.get("value"),
                    "locales":locales,
                    "textContent":"".join(tag.itertext())
                }
        if cid in out:
            raise ValueError(f"{cid}: duplicate entity in {path.name}")
        dbf=entity.attrib.get("ID")
        out[cid]={"dbfId":int(dbf) if dbf and dbf.isdigit() else None,"stringTags":tags}
        entity.clear()
    if len(out)!=expected_count:
        raise ValueError(f"{path.name}: parsed {len(out)} cards, expected {expected_count}")
    return out

def main():
    xml_dir=Path(sys.argv[1]) if len(sys.argv)>1 else Path("/tmp/boom-xml")
    manifest=read(ROOT/"sources/archive-manifest.json")
    bybuild={int(x["build"]):x for x in manifest["entries"]}
    catalog=read(ROOT/"cards.json")
    cards=catalog["cards"]
    ids={c["id"] for c in cards}
    launch=extract(xml_dir/"25770.xml",ids,bybuild[25770]["xmlSha256"],bybuild[25770]["observedCardCount"])
    current=extract(xml_dir/"256589.xml",ids,bybuild[256589]["xmlSha256"],bybuild[256589]["observedCardCount"])
    changed=0
    for card in cards:
        cid=card["id"]
        path=ROOT/"data"/(cid+".json")
        source=read(path)
        if source.get("_meta",{}).get("schemaVersion")!=2:
            raise ValueError(f"{cid}: canonical v2 source required")
        if source["_current"].get("dbfId")!=launch[cid]["dbfId"] or source["_current"].get("dbfId")!=current[cid]["dbfId"]:
            raise ValueError(f"{cid}: immutable string snapshot DBF mismatch")
        meta=source["_meta"]
        meta["launchStringTags"]=copy.deepcopy(launch[cid]["stringTags"])
        meta["currentStringTags"]=copy.deepcopy(current[cid]["stringTags"])
        if cid=="BOT_270t":
            initial=source["2018-08-08"]
            if "rarity" not in initial:
                if launch[cid]["stringTags"] is None or initial.get("nativeTagsOwned",{}).get("203")!="1":
                    raise ValueError("BOT_270t: launch RARITY=COMMON evidence missing")
                initial["rarity"]="COMMON"
            if initial["rarity"]!="COMMON":
                raise ValueError("BOT_270t: launch rarity must be COMMON")
            if "rarity" in source["_current"]:
                raise ValueError("BOT_270t: current rarity must remain absent")
        write(path,source)
        changed+=1
    print(json.dumps({"cardsEnriched":changed,"launchStringTags":sum(len(x["stringTags"]) for x in launch.values()),
                      "currentStringTags":sum(len(x["stringTags"]) for x in current.values()),
                      "launchBuild":25770,"currentBuild":256589,"datedEventsAdded":0},ensure_ascii=False))

if __name__=="__main__":
    main()
