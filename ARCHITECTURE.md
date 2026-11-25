# Feature modules

One Tk application owns every window, dialog and overlay surface. Features share the same settings/model instances and Tk main loop; modules do not launch independent applications or create extra hidden roots.

| Area | Python modules |
| --- | --- |
| Entry, application composition | `AION2_Event_Overlay_Ping.pyw`, `AION2_Event_Overlay.py` |
| Event rows, notifications, schedules | `event_view.py`, `event_feature.py`, `event_model.py`, `schedule_editor.py`, `schedule_edit_model.py` |
| Timer UI | `timer_view.py` |
| Main settings | `settings_feature.py` |
| Ping and server selection | `ping_feature.py`, `ping_service.py`, `ping_catalog.py` |
| Server status / faction charts | `server_charts.py`, `server_data.py` |
| IL / Daily / Weekly / Named Boss | `tracker_feature.py`, `tracker_model.py`, `boss_groups.py`, `boss_catalog.py` |
| Theme, portraits, gauges, switches | `visual_feature.py` |
| Auto-updates | `update_feature.py` (UI), `update_core.py` (download/verification), `update_install.py` (separate installer) |
| Audio | `app_audio.py` |
| Startup / window ownership / DPI | `startup_feature.py`, `window_group.py`, `window_placement.py`, `windows_tray.py` |
| Local data controls | `time_inputs.py`, `schedule_tables.py` |

The 1.4.0 refactor moved 724 lines of settings/event/timer UI out of the application shell without changing their behavior. Splitting files improves isolation and reviewability; it does not itself guarantee faster execution. Tab views are built on selection, images are cached, and JSON/Ping/download work stays on background threads. Workers communicate through queues; only the main thread touches Tk. The startup window stays hidden until geometry, style and clocks are ready.

Validation: unit tests plus source/frozen GUI checks cover all eight tabs, editors, settings, alerts, audio, minimal Ping, charts, themes, update progress and rollback. Startup tests compare ready time and window-map counts; a file split must not be presented as a speed gain without a repeatable measured improvement.
