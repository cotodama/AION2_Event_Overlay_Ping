import copy,datetime as dt,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'AION2-Event-Overlay'))
from schedule_edit_model import JST,event_edit,boss_schedule,edited_event_status
from event_model import occurrences,next_start,due_notifications,notification_text,migrate_config
from tracker_model import defaults,Tracker,next_occurrence,validate_schedule
from boss_groups import boss_display_items,boss_map_links,members

class EditTests(unittest.TestCase):
    def event(self):return migrate_config({'events':[dict(name_ja='亀裂',name_en='Spacetime Rift',type='interval',start='02:00',interval_minutes=180,alert_enabled=True,schedule_confirmed=True)]})['events'][0]

    def test_name_only_keeps_every_schedule_and_notification_field(self):
        row=self.event();row.update(sound_file='my.wav',sound_enabled=False,alert_enabled=False)
        result=event_edit(row,'🌙 名称変更','keep','','',[],'','0','0')
        for key,value in row.items():
            if key not in ('name_ja','emoji_in_name'):self.assertEqual(result[key],value)
        self.assertEqual(row['name_ja'],'🌌 亀裂')

    def test_maintenance_anchor_crosses_midnight_every_twelve_hours(self):
        e=event_edit(self.event(),'NM','interval','2026-10-21 21:00:30',720,[],'',0,0)
        now=dt.datetime(2026,10,21,20,59,tzinfo=JST)
        self.assertEqual(next_start(e,now).strftime('%H:%M:%S'),'21:00:30')
        self.assertEqual(occurrences(e,now-dt.timedelta(days=8),now),[])
        at=next_start(e,now)
        self.assertEqual(next_start(e,at),dt.datetime(2026,10,22,9,0,30,tzinfo=JST))
        self.assertEqual(edited_event_status(e,at-dt.timedelta(seconds=30)),('next',30,None))
        self.assertEqual(len(due_notifications(e,at-dt.timedelta(seconds=1),at)),1)
        self.assertEqual(due_notifications(e,at,at+dt.timedelta(seconds=1)),[])

    def test_thirty_second_interval_and_second_precision_daily_weekly(self):
        row=event_edit(self.event(),'NM','interval','2026-10-21 21:00:30',.5,[],'',0,0)
        at=dt.datetime(2026,10,21,21,0,30,tzinfo=JST)
        self.assertEqual(next_start(row,at),at+dt.timedelta(seconds=30))
        for mode in ('daily','weekly'):
            value=event_edit(self.event(),'NM',mode,'2026-10-21 21:00:30',720,[2],'',0,0)
            self.assertEqual(next_start(value,at-dt.timedelta(seconds=1)),at)
            self.assertEqual(next_start(value,at),at+dt.timedelta(days=1 if mode=='daily' else 7))

    def test_once_expires_and_does_not_repeat_or_break_tracker(self):
        at=dt.datetime(2026,10,21,21,0,30,tzinfo=JST)
        schedule=boss_schedule('once',at.isoformat(),720,[]);validate_schedule(schedule)
        self.assertIsNone(next_occurrence(schedule,at))
        catalog=defaults();row=catalog['bosses'][0];row['schedule']=schedule
        tracker=Tracker(catalog,{'bells':{row['id']:True},'leads':{row['id']:0}})
        tracker.tick(at-dt.timedelta(seconds=1));self.assertEqual(len(tracker.tick(at)[1]),1)
        self.assertEqual(tracker.tick(at+dt.timedelta(seconds=1))[1],[])
        event=event_edit(self.event(),'一回のみ','once',at.isoformat(),0,[],'',0,0)
        self.assertEqual(edited_event_status(event,at+dt.timedelta(seconds=1)),('finished',0,None))
        self.assertIsNone(next_start(event,at))

    def test_windows_overnight_and_precise_end(self):
        event=event_edit(self.event(),'夜間','windows','2026-10-21 23:00',0,[], '23:00:30-01:00:30',0,0)
        now=dt.datetime(2026,10,22,0,59,30,tzinfo=JST)
        self.assertEqual(edited_event_status(event,now),('active',0,60))

    def test_invalid_values_rejected_before_write(self):
        for value in ('nan','inf',-.5,.1):
            with self.assertRaises(ValueError):boss_schedule('interval','2026-10-21 21:00:00',value,[])
        with self.assertRaises(ValueError):boss_schedule('weekly','2026-10-21 21:00:00',720,[])
        with self.assertRaises(ValueError):event_edit(self.event(),'','keep','','',[],'',0,0)

    def test_all_matching_faction_names_group_without_mutating_ids(self):
        for name in ('精霊王アグロ','執行者カイラ','守護神将ナフマ'):
            rows=[dict(id='e',name=name+'（天族）',faction='天族',map_url='https://aion2.gaming.tools/ja/map?q=e'),
                  dict(id='a',name=name+'（魔族）',faction='魔族',map_url='https://aion2.gaming.tools/ja/map?q=a')]
            before=copy.deepcopy(rows);group=boss_display_items(rows)
            self.assertEqual(len(group),1);self.assertEqual(len(members(group[0])),2)
            self.assertEqual(group[0]['name'],name)
            self.assertEqual([v['label'] for v in boss_map_links(group[0])],['魔族MAP','天族MAP'])
            self.assertEqual(rows,before)

    def test_shared_abyss_map_has_both_buttons_without_inventing_locations(self):
        row=dict(id='argo',name='精霊王アグロ',faction='天族・魔族',map_url='https://aion2.gaming.tools/ja/map?map=20')
        links=boss_map_links(row);self.assertEqual(len(links),2)
        self.assertEqual(links[0]['url'],links[1]['url'])

    def test_same_named_faction_notifications_share_one_message(self):
        at=dt.datetime(2026,10,21,21,0,30,tzinfo=JST)
        catalog=defaults();state={'bells':{},'leads':{}}
        for row in catalog['bosses']:
            row.update(name='共通名',schedule=boss_schedule('once',at.isoformat(),720,[]))
            state['bells'][row['id']]=True;state['leads'][row['id']]=0
        tracker=Tracker(catalog,state);tracker.tick(at-dt.timedelta(seconds=1))
        self.assertEqual(tracker.tick(at)[1],['共通名'])
        self.assertEqual(len(tracker.state['fired']),2)
