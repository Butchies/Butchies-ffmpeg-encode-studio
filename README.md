# ffmpeg_encode Studio – Rohdaten

Windows-Programm: Song (MP3 …) + Bild → fertiges YouTube-Video (4K, 1440p, 1080p, Shorts, Shorts 4K).
Look, Designs, Start- und Abschieds-Animation stammen von der Butchies-Webseite (V2).

## Aufbau

| Datei / Ordner | Inhalt |
|---|---|
| `ffmpeg_encode_studio.py` | Programm-Kern (Python-Standardbibliothek): lokaler Server, FFmpeg-Befehle, Übergänge, Fortschritt, Warteschlange, Grafikkarten-Erkennung, Fenster (pywebview/WebView2) |
| `ui/` | Oberfläche: `index.html`, `style.css` (7 Designs + Schriften), `app.js`, `fonts/` |
| `installer.iss` | Inno-Setup-Installer (bringt FFmpeg + WebView2 mit, ohne Adminrechte) |
| `tools/smoke.ps1` | Echter Test auf Windows (startet das Programm, rendert 2 Videos, prüft mit ffprobe) |
| `tools/make_icons.py` | Erzeugt `icon.ico` und die Installer-Bilder neu |
| `icon.ico`, `installer-*.bmp` | Programmsymbol, Installer-Grafiken |
| `LIESMICH.txt`, `RELEASE.md` | Anleitung (wird mit installiert), Text für das GitHub-Release |
| `.github/workflows/encoder-exe.yml` | Baut alles auf GitHub (Windows) und legt `ffmpeg_encode_Studio-Setup.exe` als Release ab |

## Neue Version bauen

1. Änderung machen, in `ffmpeg_encode_studio.py` die Zeile `VERSION = '…'` erhöhen.
2. Auf GitHub hochladen → der Workflow baut, testet und veröffentlicht automatisch das Release
   `encoder-v<Version>` mit der Setup-Datei.

## Lokal ausprobieren (ohne Installer)

```
pip install pywebview
python ffmpeg_encode_studio.py            # Programmfenster
python ffmpeg_encode_studio.py --no-window   # nur Server, Adresse steht in der Ausgabe
```
FFmpeg wird im Ordner `ffmpeg\bin` neben dem Programm, über `FFMPEG_DIR` oder im `PATH` gesucht.
