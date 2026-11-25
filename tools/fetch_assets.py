"""One-time maintainer asset download. The application never scrapes pages."""
from pathlib import Path
import hashlib,json,urllib.request
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
ASSETS={
 'gartua':('ut_256_mob_gartua_01_v02.webp','2101074'),
 'ragta':('ut_256_mob_lagta_01.webp','2101131'),
 'argo':('ut_256_mob_eleking_01_v02.webp','2600097'),
 'kaira':('ut_256_mob_beritrad_01.webp','2600098'),
 'nafma':('ut_256_mob_abboss_01.webp','2600084'),
}
folder=ROOT/'assets/bosses';folder.mkdir(parents=True,exist_ok=True);sources=[]
for name,(filename,npc) in ASSETS.items():
    url='https://cdn-hosted.gaming.tools/aion2/images/ui/resource/texture/portrait/portrait_256/'+filename
    request=urllib.request.Request(url,headers={'User-Agent':'AION2-Event-Overlay-Ping asset preparation'})
    with urllib.request.urlopen(request,timeout=40) as response:data=response.read(2*1024*1024)
    original=folder/(name+'.webp');original.write_bytes(data)
    with Image.open(original) as image:image.convert('RGBA').save(folder/(name+'.png'))
    sources.append(dict(name=name,page='https://aion2.gaming.tools/ja/npcs/'+npc,url=url,sha256=hashlib.sha256(data).hexdigest()))
    print(name,len(data),flush=True)
(ROOT/'assets/sources.json').write_text(json.dumps(sources,indent=2),encoding='utf-8')
(ROOT/'assets/THIRD_PARTY.md').write_text('''# Game portraits

Original NPC portraits are AION 2 game artwork, copyright NCSOFT. They are not covered by this repository's MIT code license.
The publicly accessible portrait files were obtained from AION2 Gaming Tools for identifying the corresponding game bosses.
Source pages, image URLs and original-file hashes are recorded in sources.json. No game files are read by the application.
User-selected replacements are stored under data/assets/bosses and are not included in public releases.
''',encoding='utf-8')
