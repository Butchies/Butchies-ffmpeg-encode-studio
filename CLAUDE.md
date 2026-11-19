# Notizen für Claude – ffmpeg_encode Studio
Windows-Programm: Song + Bild → YouTube-Video (4K/1440p/1080p, Shorts 9:16, Shorts 4K). Nutzer schreibt Deutsch, technisch unerfahren – einfach erklären.

## Aufbau
- `ffmpeg_encode_studio.py`: Python-stdlib-Server auf 127.0.0.1 (Token im URL-Hash, Header `X-Studio`), pywebview/WebView2-Fenster (rahmenlos, `WinFrame`), Fallback Edge/Chrome-App-Fenster.
- Bild wird einmal per `still_command` auf Zielgröße gebracht (Fit: blur/cover/contain), dann im Video per `loop`-Filter wiederholt (schneller als `-loop 1`).
- Übergänge: `TRANSITIONS` (36, FFmpeg `xfade`) über `transition_graph` – Farbe→Bild (Bild kommt) und Bild→Farbe (Bild geht); Ton-Fades per `afade`. Vorschau-Clip `/api/trans-preview`.
- Encoder: `auto` = erste funktionierende Grafikkarte (`GPU_ORDER` nvenc, qsv, amf; Test in `hw_check`), sonst x264; scheitert die GPU, automatischer Rückfall auf x264 (`run_job`).
- Oberfläche `ui/`: 7 Designs + Schriften + Start-Animation (`#splash`) + Abschied (`#goodbye`, Beenden-Knopf) von der Webseite Butchies/butchies-raucherstube (V2).
- Einstellungen: `%APPDATA%\ffmpeg_encode Studio\config.json`; Videos standardmäßig in `Videos\ffmpeg_encode Studio`.

## Build / Release
- Push auf `main` → Workflow `encoder-exe.yml` (windows-latest): PyInstaller onedir, FFmpeg GPL-shared von BtbN, WebView2-Bootstrapper, Echttest `tools/smoke.ps1` (2 Videos), Inno Setup → Release `encoder-v<VERSION>` mit `ffmpeg_encode_Studio-Setup.exe`.
- Neue Version: `VERSION` in `ffmpeg_encode_studio.py` erhöhen (gleiche Version = Datei im Release wird ersetzt).
- Lokal testen: `python3 ffmpeg_encode_studio.py --no-window` + Playwright (`/usr/bin/google-chrome`).
- Nutzerwunsch: bei Releases Fortschritt in Prozent (ca. alle 5 %) angeben.
