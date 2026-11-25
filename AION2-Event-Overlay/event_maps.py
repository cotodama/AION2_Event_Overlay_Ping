"""Verified Japanese gaming.tools interactive-map search links (2026-10-12).

The site's map UI exposes q=<name>&map=<region>. These show candidate/static
positions, never the live availability of a rift or a boss on a user's server.
"""
from urllib.parse import urlencode

def mapped_url(name, map_id):
    return 'https://aion2.gaming.tools/ja/map?'+urlencode({'q':name,'map':str(map_id)})

RIFT_MAP_LINKS=[{'label':'MAP天','url':mapped_url('時空の亀裂','1010')},
                {'label':'MAP魔','url':mapped_url('時空の亀裂','1110')}]
FIELD_BOSS_MAPS={
    'gartua-elyos':mapped_url('永遠のガルトゥア','1010'),
    'gartua-asmo':mapped_url('不滅のガルトゥア','1110'),
}
