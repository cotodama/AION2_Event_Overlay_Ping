import datetime as dt
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'AION2-Event-Overlay'))
from tracker_model import Tracker, defaults, next_occurrence, validate_catalog, safe_link, UTC
from server_data import balance_groups, filtered_servers

class TrackerTests(unittest.TestCase):
    def test_unknown_is_not_a_schedule(self):
        c=defaults(); t=Tracker(c,{})
        self.assertIsNone(next_occurrence(None,dt.datetime.now(UTC)))
        for group in ('daily','weekly','bosses'):
            for item in c[group]: t.state['bells'][item['id']]=True
        t.tick(dt.datetime(2026,10,6,tzinfo=UTC))
        self.assertEqual(t.tick(dt.datetime(2026,10,7,tzinfo=UTC))[1],[])

    def test_offline_reset_only_clears_its_period(self):
        c=defaults(); c['resets']['daily']={'kind':'daily','time':'01:00','utc_offset':9}
        c['resets']['weekly']={'kind':'weekly','time':'01:00','utc_offset':9,'weekday':2}
        t=Tracker(c,{})
        start=dt.datetime(2026,10,5,15,tzinfo=UTC); t.tick(start)
        for group in ('il','daily','weekly'): t.checked(c[group][0]['id'],True)
        state=json.loads(json.dumps(t.state)); t=Tracker(c,state)
        t.tick(start+dt.timedelta(hours=2))
        self.assertFalse(t.done(c['daily'][0]['id']))
        self.assertTrue(t.done(c['weekly'][0]['id']))
        self.assertTrue(t.done(c['il'][0]['id']))

    def test_notification_once_across_restart_and_skipped_tick(self):
        c=defaults(); s={'kind':'interval','anchor':'2026-10-06T12:00:00+00:00','minutes':180}
        c['bosses'][0]['schedule']=s; t=Tracker(c,{})
        ident=c['bosses'][0]['id']; t.state['bells'][ident]=True
        t.tick(dt.datetime(2026,10,6,11,54,tzinfo=UTC))
        self.assertEqual(t.tick(dt.datetime(2026,10,6,11,56,tzinfo=UTC))[1],[c['bosses'][0]['name']])
        self.assertEqual(t.tick(dt.datetime(2026,10,6,11,57,tzinfo=UTC))[1],[])
        t=Tracker(c,json.loads(json.dumps(t.state)))
        t.tick(dt.datetime(2026,10,6,11,54,tzinfo=UTC))
        self.assertEqual(t.tick(dt.datetime(2026,10,6,11,56,tzinfo=UTC))[1],[])
        self.assertEqual(len(t.tick(dt.datetime(2026,10,6,14,56,tzinfo=UTC))[1]),1)

    def test_zero_lead_and_week_boundary(self):
        c=defaults(); c['resets']['weekly']={'kind':'weekly','time':'01:00','utc_offset':9,'weekday':2}
        t=Tracker(c,{}); ident=c['weekly'][0]['id']; t.state['bells'][ident]=True; t.state['leads'][ident]=0
        a=dt.datetime(2026,10,6,15,59,59,tzinfo=UTC); t.tick(a)
        self.assertEqual(len(t.tick(a+dt.timedelta(seconds=1))[1]),1)
        self.assertEqual(t.tick(a+dt.timedelta(seconds=2))[1],[])

    def test_definitions_reject_untrusted_links_and_unverified_coordinates(self):
        self.assertFalse(safe_link('https://aion2.gaming.tools.evil/ja/maps'))
        self.assertFalse(safe_link('javascript:alert(1)'))
        c=defaults(); c['bosses'][0]['coordinates']=[1,2]
        with self.assertRaises(ValueError): validate_catalog(c)

    def test_new_servers_survive_old_region_pair_limit(self):
        def server(n,f,i): return dict(name=n,faction=f,serverId=i,region='AS',players=100,isRunning=True,inMaintenance=False)
        s={'regions':[{'code':'AS','servers':[server('Meslamtaeda','Elyos',1508),server('Beritra','Asmodian',2508),server('Future','Elyos',9999)]}]}
        self.assertEqual(len(filtered_servers(s,'AS')),3)
        r,totals,pairs,unpaired=balance_groups(s,'AS')[0]
        self.assertEqual((pairs[0][0],pairs[0][1]),('Meslamtaeda','Beritra'))
        self.assertEqual(unpaired[0]['name'],'Future')
        self.assertEqual(totals,{'Elyos':200,'Asmodian':100})

    def test_live_october6_fixture_has_all_98_servers_and_eight_asia_pairs(self):
        fixture=Path(__file__).parent/'fixtures'/'servers_2026-10-06.json'
        s=json.loads(fixture.read_text(encoding='utf-8'))
        self.assertEqual(len(filtered_servers(s)),98)
        self.assertEqual(len(filtered_servers(s,'AS')),16)
        r,totals,pairs,unpaired=balance_groups(s,'AS')[0]
        self.assertEqual(len(pairs),8)
        self.assertEqual(unpaired,[])
        self.assertEqual(sum(totals.values()),sum(x['players'] for x in r['servers']))

    def test_invalid_editor_shapes_raise_validation_error(self):
        for value in ([],{'resets':[]},dict(defaults(),daily=['bad'])):
            with self.assertRaises(ValueError): validate_catalog(value)

if __name__=='__main__': unittest.main()
