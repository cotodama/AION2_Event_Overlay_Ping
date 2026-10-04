# AION2 Event Overlay

A compact, unofficial Windows overlay for checking AION2 event schedules, timers, and alerts while playing.

**Version 1.0.0 — Initial Release**

## Features

- Event countdowns with configurable pre-event and start alerts
- Active/entry-time highlighting for supported events
- Custom timers with independent alerts
- WAV / MP3 custom alert sounds and volume controls
- Japanese / English UI
- JST, Pacific (PST/PDT), and Central European (CET/CEST) display time zones
- Adjustable HUD background opacity
- Frameless movable HUD with remembered screen position
- Per-event enable/disable and alert controls
- User settings stored separately under `%LOCALAPPDATA%\AION2 Event Overlay`

## Requirements

- Windows 10 or Windows 11
- The packaged `.exe` does not require a separate Python installation.
- Running from source requires Python 3 with Tkinter available.

## Installation

For a packaged release, extract the release archive to a normal folder and run `AION2_Event_Overlay.exe`.

The bundled `aion2_overlay.json` is only the first-run template. On first launch it is copied to:

```text
%LOCALAPPDATA%\AION2 Event Overlay
```

Later changes are saved there, so replacing the application with a newer release does not normally overwrite user preferences.

## Basic use

The HUD shows the current display-zone time, daily reset countdown, enabled events, and visible timers. Use the top HUD buttons to open timer settings, move the frameless overlay, and open Settings. Bell buttons control alerts for individual events or timers.

Settings contains event management, display/language options, event and timer alert configuration, and version information.

## Alert sounds

Event and timer alerts can use the built-in sound or a user-selected `.wav` / `.mp3` file. Custom file paths are stored in the user's local configuration; the audio files themselves are not copied into the application folder.

## Run from source

Run `run_overlay.bat`, or execute:

```text
python AION2_Event_Overlay.py
```

## Build the Windows executable

Run `build_exe.bat`. The script installs/updates PyInstaller and creates a one-file, windowed executable with the application icon and bundled first-run configuration.

Successful builds are staged in `dist\` with:

```text
AION2_Event_Overlay.exe
aion2_overlay.json
README.md
LICENSE
```

## Data and troubleshooting

Live user settings and the remembered HUD position are stored under:

```text
%LOCALAPPDATA%\AION2 Event Overlay
```

If a configuration problem needs to be diagnosed, back up that folder before changing or deleting its contents.

## Disclaimer

AION2 Event Overlay is an unofficial community tool. It is not affiliated with, endorsed by, or sponsored by NCSOFT or the AION/AION2 development and publishing teams. Game names and related trademarks belong to their respective owners.

AION2 Event Overlay does not access the game's internal clock. Displayed times may therefore differ from the in-game time by a few seconds.

Event schedules can change after game updates. Verify important schedule information against current official game information when necessary.

## License

Released under the MIT License. See `LICENSE`.

