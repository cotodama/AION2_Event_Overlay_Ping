import copy
import datetime as dt
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'AION2-Event-Overlay'))
from event_model import JST, migrate_config, due_notifications, event_name, notification_text, occurrences

class EventTests(unittest.TestCase):
    def event(self,name='Shugo Festa',**kw):
        return dict(id='test',name_en=name,name_ja='テスト',type='interval',start='00:00',
                    interval_minutes=60,enabled=True,alert_enabled=True,schedule_confirmed=True,**kw)

    def test_hour_start_only_delayed_tick_and_midnight(self):
        e=self.event(notify_before_minutes=10,alert_timing='both')
        at=dt.datetime(2026,10,12,0,0,tzinfo=JST)
        self.assertEqual(due_notifications(e,at-dt.timedelta(minutes=11),at-dt.timedelta(minutes=4)),[])
        rows=due_notifications(e,at-dt.timedelta(seconds=12),at+dt.timedelta(seconds=3))
        self.assertEqual([r[2] for r in rows],[0])
        self.assertEqual(rows[0][1],at)
        self.assertEqual(due_notifications(e,at,at+dt.timedelta(seconds=1)),[])

    def test_dimensional_half_hour_and_zero_entry(self):
        e=self.event('Dimensional Invasion'); e['start']='00:30'
        at=dt.datetime(2026,10,12,0,30,tzinfo=JST)
        self.assertEqual(len(due_notifications(e,at-dt.timedelta(seconds=8),at)),1)
        self.assertEqual(due_notifications(e,at,at-dt.timedelta(minutes=1)),[])

    def test_artifact_all_three_boundaries_and_unknown_is_silent(self):
        e=self.event('Artifact Siege'); e.update(type='weekly',weekdays=[0],times=['00:00'])
        at=dt.datetime(2026,10,12,0,0,tzinfo=JST)
        for lead in (40,30,0):
            due=at-dt.timedelta(minutes=lead)
            rows=due_notifications(e,due-dt.timedelta(seconds=1),due)
            self.assertEqual([r[2] for r in rows],[lead])
        e['schedule_confirmed']=False
        self.assertEqual(due_notifications(e,at-dt.timedelta(seconds=1),at),[])

    def test_migration_preserves_off_custom_audio_and_one_time_addition(self):
        c={'events':[dict(name_en='Shugo Festa',name_ja='シューゴフェスタ',alert_enabled=False,
                         sound_enabled=False,sound_file='chosen.wav',sound_volume=22)],
           'alert_volume':17,'alert_sound_file':'global.mp3','timers':[{'name':'mine','duration':60}]}
        before=copy.deepcopy(c); updated=migrate_config(c)
        self.assertEqual(c,before)
        e=updated['events'][0]
        self.assertFalse(e['alert_enabled']); self.assertFalse(e['sound_enabled'])
        self.assertEqual((e['sound_file'],e['sound_volume']),('chosen.wav',22))
        self.assertEqual(updated['alert_volume'],17); self.assertEqual(updated['timers'],c['timers'])
        self.assertEqual(migrate_config(updated),updated)
        updated['events'].pop(); self.assertEqual(len(migrate_config(updated)['events']),1)

    def test_preset_schedule_not_promoted_and_custom_schedule_retained(self):
        c={'events':[dict(name_en='Spacetime Rift',start='02:00',interval_minutes=180),
                     dict(name_en='Artifact Siege',weekdays=[2,5],times=['21:00']),
                     dict(name_en='Battlefield',windows=[['10:00','12:00']]) ]}
        out=migrate_config(c)['events']
        self.assertTrue(out[0]['schedule_confirmed']); self.assertTrue(out[1]['schedule_confirmed']); self.assertEqual(out[1]['weekdays'],[3,5]); self.assertEqual(out[1]['times'],['21:00'])
        self.assertEqual(out[0]['schedule_reference'],'community')
        self.assertTrue(out[2]['schedule_confirmed']); self.assertEqual(out[2]['windows'],[['10:00','12:00']])

    def test_names_and_message_content(self):
        e=self.event(); e['name_ja']='シューゴフェスタ'
        self.assertTrue(event_name(e).startswith('🦊'))
        self.assertEqual(event_name(e,emoji=False),'シューゴフェスタ')
        text=notification_text(e,dt.datetime(2026,10,12,23,tzinfo=JST),0)
        for part in ('23:00 JST','23:03 JST','00:00 JST','🔔 開始予定時刻'): self.assertIn(part,text)

    def test_editable_emoji_is_text_and_not_readded_after_user_removes_it(self):
        c=migrate_config({'event_schema':2,'events':[self.event()]})
        e=c['events'][0]
        self.assertTrue(e['name_ja'].startswith('🦊'))
        e['name_ja']='カスタム'; self.assertEqual(event_name(e),'カスタム')
        self.assertEqual(migrate_config(c),c)
        e['name_ja']='✨ テスト 🦊'; self.assertEqual(event_name(e,emoji=False),'テスト')

    def test_window_order_and_offline_backlog(self):
        e=self.event('Battlefield'); e.update(type='windows',windows=[['19:00','21:00'],['11:00','14:00']])
        begin=dt.datetime(2026,10,12,tzinfo=JST)
        self.assertEqual([x.hour for x in occurrences(e,begin,begin+dt.timedelta(days=1))],[11,19])
        shugo=self.event()
        self.assertEqual(due_notifications(shugo,begin,begin+dt.timedelta(hours=3,minutes=10)),[])

if __name__=='__main__': unittest.main()
