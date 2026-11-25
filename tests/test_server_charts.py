import sys,unittest,queue,threading
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'AION2-Event-Overlay'))
from server_data import next_fetch_deadline,FETCH_INTERVAL_SECONDS
from server_charts import live_load,paired_series,aggregate,peak_window,MATCHES
from ping_feature import PingFeatureMixin

class ChartTests(unittest.TestCase):
    def test_quarter_hours_and_manual_cadence(self):
        self.assertEqual(FETCH_INTERVAL_SECONDS,900)
        for wall,delay in ((0,900),(899,1),(900,900),(901,899),(3599,1),(3600,900)):
            self.assertEqual(next_fetch_deadline(100,wall),100+delay)
            self.assertEqual(next_fetch_deadline(100,wall,True),1000)

    def test_manual_refresh_restarts_schedule_and_rejects_duplicate(self):
        app=PingFeatureMixin();app.fetch_busy=False;app.active_tab='events';app.next_fetch=150
        with patch('ping_feature.time.monotonic',return_value=200),patch('ping_feature.time.time',return_value=3601),patch('ping_feature.threading.Thread') as thread:
            self.assertTrue(app.request_db_refresh(manual=True));self.assertEqual(app.next_fetch,1100)
            self.assertFalse(app.request_db_refresh(manual=True));thread.return_value.start.assert_called_once()
            app.fetch_busy=False
            self.assertTrue(app.request_db_refresh());self.assertEqual(app.next_fetch,1100)

    def test_unknown_and_maintenance_are_not_zero(self):
        s=dict(state='live',isRunning=True,inMaintenance=False,load=.14)
        self.assertEqual(live_load(s),.14);self.assertEqual(live_load(dict(s,load=0)),0)
        self.assertIsNone(live_load(dict(s,inMaintenance=True)));self.assertIsNone(live_load(dict(s,load=float('nan'))))
        self.assertIsNone(live_load(dict(s,state='stale')))

    def test_history_aligns_timestamps_and_keeps_missing_gap(self):
        a=dict(spark=[dict(t=0,value=.1),dict(t=3600000,value=None)])
        b=dict(spark=[dict(t=3600000,value=.2),dict(t=7200000,value=.3)])
        self.assertEqual(paired_series(a,b),[dict(t=0,first=.1,second=None),dict(t=3600000,first=None,second=.2),dict(t=7200000,first=None,second=.3)])

    def test_peak_window_does_not_bridge_missing_hours(self):
        regional=[dict(t=i*3600000,value=v) for i,v in enumerate([.1,.2,None,.9,.8,.7,.6])]
        points=[dict(t=p['t'],first=.3,second=.2) for p in regional]
        self.assertEqual(peak_window(points,regional),(.3,.2,3*3600000))
        self.assertIn(['Siel','Ariel'],MATCHES['AS']);self.assertIn(['Israphel','Lumiel'],MATCHES['AS'])

if __name__=='__main__':unittest.main()
