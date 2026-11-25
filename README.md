# AION2 Event Overlay + Ping

A lightweight Windows overlay for AION2 schedules, reminders and TCP latency.

**[Download latest](https://github.com/cotodama/AION2_Event_Overlay_Ping/releases/latest)** · [All versions](https://github.com/cotodama/AION2_Event_Overlay_Ping/releases)

## Features

- Event and boss countdowns, editable maintenance anchors, hour/minute cycle selectors and MAP links.
- Daily/weekly checklists, individual alert switches, lead times and sound previews.
- A draggable minimal Ping overlay, local boss portraits, countdown bars and six dark themes.
- Server load, faction/pair balance, hourly trends and Steam history from [AION2 Gaming Tools](https://aion2.gaming.tools/ja/server-status).
- Optional GitHub auto-updates with download progress, verification, backup and failed-start rollback.

This app runs independently. It **does not modify the game client, read game memory or packets, inject code, or optimize game traffic**. Ping measures independent TCP connection time. Boss times follow saved schedules; adjust their anchors after maintenance.

## Install

Download the versioned ZIP, extract it to a writable folder and run `AION2_Event_Overlay_Ping.exe`. No Python required.

To migrate manually, close the old app and copy its `data/` folder into the new version. Auto-update is optional in **Settings → Info** and preserves settings. Earlier releases and ZIPs remain available.

Server tabs share public JSON only: once at startup, then **:00 / :15 / :30 / :45**. **Manual refresh** restarts a 15-minute cadence for that session. Missing values stay unknown; load percentages are not player counts.

## Source and Windows build

Python 3.10+ with Tkinter:

```powershell
py -3 -m pip install -r requirements.txt
py -3 AION2_Event_Overlay_Ping.pyw
```

Run `build_exe.bat` to install build dependencies, test and build. The executable goes to `.build/dist/`; the versioned ZIP and checksum go to `release/`.

Maintainers: bump `VERSION`, update the release notes and push to `main`. GitHub Actions adds a new release without replacing older downloads.

## Credits

Based on [hosigumolayla/AION2-Event-Overlay](https://github.com/hosigumolayla/AION2-Event-Overlay) (MIT). Game portraits remain NCSOFT property: [asset credits](assets/THIRD_PARTY.md).

[Changes and verification](CHANGES.md) · [Feature modules and build details](ARCHITECTURE.md)
