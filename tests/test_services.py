import base64
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'AION2-Event-Overlay'))
from server_data import (decode_response,filtered_servers,balance_groups,
                         balance_fraction,status_label,validate_snapshot)
from ping_service import latency_color
from ping_catalog import build_default_profiles

def server(name,faction,ident,players=100):
    return dict(name=name,faction=faction,serverId=ident,players=players,capacity=1000,
                queue=0,region='EU',isRunning=True,inMaintenance=False,
                creationBlocked=True,load=players/1000,spark=[])

def snapshot():
    return {'regions':[{'code':'EU','servers':[server('Israphel','Asmodian',2,400),
                                            server('Unpaired','Elyos',3,123),
                                            server('Siel','Elyos',1,600)]}]}

class ServicesTest(unittest.TestCase):
    def test_actual_wire_encoding_and_schema_changes(self):
        data=snapshot(); raw=json.dumps(data).encode(); key=bytes([154,60,87,241,40,189,100,14])
        payload=base64.b64encode(bytes(v^key[i%8] for i,v in enumerate(raw))).decode()[::-1]
        wire={'nodes':[{'type':'skip'},{'data':[{'payload':1},payload]}]}
        self.assertEqual(decode_response(wire),data)
        with self.assertRaises(ValueError): decode_response({'nodes':[]})
        del data['regions'][0]['servers'][0]['creationBlocked']
        with self.assertRaises(ValueError): validate_snapshot(data)

    def test_pairs_are_matched_by_name_not_order_and_no_guess(self):
        region,totals,pairs,unpaired=balance_groups(snapshot(),'EU')[0]
        self.assertEqual(len(pairs),1)
        self.assertEqual((pairs[0][2]['name'],pairs[0][3]['name']),('Siel','Israphel'))
        self.assertEqual(unpaired[0]['name'],'Unpaired')
        self.assertEqual(totals,{'Elyos':723,'Asmodian':400})
        self.assertEqual(balance_fraction(600,400),.6)
        self.assertIsNone(balance_fraction(None,400))
        self.assertIsNone(balance_fraction(0,0))

    def test_filters_and_maintenance(self):
        data=snapshot(); data['regions'][0]['servers'][0]['inMaintenance']=True
        self.assertEqual(status_label(data['regions'][0]['servers'][0]),'メンテナンス')
        self.assertEqual(len(filtered_servers(data,'EU',status='online')),2)
        self.assertEqual(len(filtered_servers(data,'EU',status='issues')),1)
        self.assertEqual(len(filtered_servers(data,'NAW')),0)
        self.assertEqual(filtered_servers(data,'EU','SIEL')[0]['name'],'Siel')

    def test_ping_boundaries_and_unverified_profiles(self):
        self.assertEqual(latency_color(99.9),'#40ff68')
        self.assertEqual(latency_color(100),'#ff9b42')
        self.assertEqual(latency_color(199.9),'#ff9b42')
        self.assertEqual(latency_color(200),'#ff5252')
        self.assertEqual(latency_color(None),'#ff5252')
        profiles=build_default_profiles()
        for r in ('Japan','NA West','NA East','Central Europe','South America'):
            self.assertTrue(all('未検証' in s['endpoint_note'] for s in profiles[r]['servers']))

    def test_db_rate_limit_shared_without_tk(self):
        from ping_feature import PingFeatureMixin
        import queue,threading
        class FakeThread:
            targets=[]
            def __init__(self,target,args=(),daemon=False): self.target=target; self.targets.append(target)
            def start(self): pass
        app=PingFeatureMixin()
        app.stop_workers=threading.Event(); app.worker_queue=queue.Queue()
        app._background_disabled=False; app.scan_busy=False; app.next_scan=0
        app.fetch_busy=False; app.next_fetch=0; app.active_tab='events'; app.ping_generation=0
        app.profiles={}; app.ping_cfg={'selected':[]}
        with patch('ping_feature.threading.Thread',FakeThread),patch('ping_feature.time.monotonic') as clock:
            clock.return_value=100.; app.poll_network(); self.assertEqual(len(FakeThread.targets),1)
            app.fetch_busy=False
            for tab in ('events','status','balance','status'):
                app.active_tab=tab; clock.return_value=159.; app.poll_network()
            self.assertEqual(len(FakeThread.targets),1)
            clock.return_value=160.; app.poll_network(); self.assertEqual(len(FakeThread.targets),2)

if __name__=='__main__': unittest.main()
