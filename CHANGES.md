# Changes

## 1.4.0

- Added optional GitHub startup updates and manual app updating, progress, strict download/manifest checks, retained backups and failed-start rollback. Personal data and unmanaged files are preserved. Automatic updating is off by default.
- Added six dark themes and accent choices, local pictogram icons, bundled boss portraits, custom image selection and optional countdown gauges. Existing compact/simple Ping modes remain available.
- Added a notification dashboard with switches, lead selectors and sound previews. Existing bell shortcuts and Shugo notification content are retained.
- Rebuilt server load/history and faction/pair charts using current public JSON. Missing metrics are not converted to zero; player counts are not inferred from load. Updated published matching pairs, including same-faction pairs, checked November 11/26.
- Added hourly graph hover values, regional history, peak windows and Steam 24-hour/7-day/30-day charts. Responsive native drawing follows the source page's data/color meanings; it does not embed the website.
- Public JSON refresh: once at startup, then :00/:15/:30/:45. Manual refresh restarts a 15-minute cadence for the current session. In-flight requests are shared; no HTML fallback or automatic retry storm.
- Added clean, versioned public packaging and GitHub release automation. Older releases and assets are preserved.
- Replaced the public README with concise English install/build/use instructions.

## Existing behavior retained

Eight main tabs; Shugo/Rift/invasion/siege schedules and editable event names; daily/weekly checkmarks; boss faction MAP links; hour/minute/second and maintenance-anchor editing; Gartua's 11-hour cycle from the saved anchor; TCP endpoint editing; transparent minimal Ping; audio/session controls; saved window/dialog placement and monitor ownership.

## Verification scope

Unit tests cover schedules and notification boundaries, data decoding, quarter-hour/manual scheduling, missing history, update paths/checksums, cancellation, partial replacement and rollback. Source/frozen GUI checks exercise tabs, settings, selectors, theme/icon/image loading, gauges, switches, sound generation, startup and window positioning. A separate installation check stages the built release and validates the restarted program's startup marker.

Physical speaker listening, actual Windows mixer/tray rendering and physical mixed-DPI/virtual-desktop transitions are not guaranteed by automated checks. No claim is made that saved boss schedules match live game spawns.
