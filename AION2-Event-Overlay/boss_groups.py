"""Display groups only: original faction schedules/state IDs stay persistent."""
from tracker_model import next_occurrence
import re

GARTUA_IDS=('gartua-elyos','gartua-asmo')
GROUPS={'NM ガルトゥア':GARTUA_IDS,'軍団長ラグタ':('ragta-elyos','ragta-asmo')}

def members(item):
    return item.get('_members',[item])

def base_name(name):
    name=re.sub(r'\s*[（(](?:天族|魔族)[）)]\s*$','',name).strip()
    return re.sub(r'^(?:天族|魔族)[ ：:・_-]+','',name).strip()

def boss_display_items(rows):
    result=[]; added=set()
    for row in rows:
        name=next((n for n,ids in GROUPS.items() if row['id'] in ids),None)
        def key(r):
            known=next((n for n,ids in GROUPS.items() if r['id'] in ids),None)
            return known or r.get('boss_group') or base_name(r.get('name','')).casefold()
        group=key(row)
        if group in added:continue
        added.add(group)
        grouped=[r for r in rows if key(r)==group]
        if name is None and len(grouped)==1:result.append(row);continue
        display=dict(grouped[0],id=grouped[0]['id']+'-display',name=grouped[0].get('display_name') or name or base_name(grouped[0]['name']),_members=grouped)
        display['faction']='天族・魔族' if len(grouped)>1 else grouped[0].get('faction','未確認')
        display['area']=' / '.join(r.get('area','未確認') for r in grouped)
        result.append(display)
    return result

def next_boss_occurrence(item,now):
    candidates=[(next_occurrence(r.get('schedule'),now),r) for r in members(item)]
    return min((p for p in candidates if p[0] is not None),key=lambda p:p[0],default=(None,None))

def map_label(item):
    return '天族MAP' if item['id'].endswith('-elyos') else '魔族MAP' if item['id'].endswith('-asmo') else 'MAP'

def boss_map_links(item):
    result=[]
    for row in sorted(members(item),key=lambda r:0 if '天族' in r.get('faction','') and '魔族' in r.get('faction','') else 1):
        if row.get('map_links'):
            result.extend(row['map_links']);continue
        faction=row.get('faction','')
        labels=['天族MAP','魔族MAP'] if '天族' in faction and '魔族' in faction else [
            '天族MAP' if '天族' in faction else '魔族MAP' if '魔族' in faction else map_label(row)]
        for label in labels:
            link={'label':label,'url':row.get('map_url') or row.get('npc_url')}
            if link not in result:result.append(link)
    by_label={link['label']:link for link in result}
    return sorted(by_label.values(),key=lambda link:0 if link['label']=='魔族MAP' else 1)
