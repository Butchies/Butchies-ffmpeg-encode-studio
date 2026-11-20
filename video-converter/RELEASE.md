**Butchies Video Converter AI 1.1.4**: Videos mit KI-Hilfe in H.264 / H.265 umwandeln. Dazu gibt es einen Player für alle Codecs, einen Vorher/Nachher-Vergleich und einen Ordner-Abgleich.

**Installieren:** `Butchies_Video_Converter-Setup.exe` herunterladen und starten. Du brauchst dafür keine Administratorrechte.
Der Installer sucht das **Laufwerk mit dem meisten freien Speicher** und schlägt dort Programm- und Video-Ordner vor.
FFmpeg mit allen Codecs ist dabei (inklusive VMAF-Messung und HDR). WebView2 wird bei Bedarf automatisch eingerichtet.

- **KI-Autopilot:** Alles steht auf Auto. Auf „Manuell“ fahren die Einstellungen aus (Codec, Qualität, Auflösung, Inhalt, HDR, Ton/Untertitel/Kapitel, Ausgabe/Zeitplan)
- **Zielgröße von–bis:** Die KI wählt Bitrate und Auflösung selbst und begrenzt sinnlos hohe Bitraten
- **Echte Qualitätsmessung:** VMAF an 3 Probestücken, echtes Vorher/Nachher mit Schieberegler und Lupe
- **Erkennung:** HDR (behalten oder in SDR umrechnen), Filmkorn und Zeichentrick, defekte Dateien
- **Ton und Untertitel:** Deutsch und Englisch bleiben, Kommentarspuren fliegen raus, Kapitel werden übernommen
- **Player:** spielt alle Formate ab (live über FFmpeg), mit KI-Schärfe beim Anschauen
- **Ordner-Abgleich:** erkennt gleiche Filme am Namen, am Bild und an der Prüfsumme
  - Platz-Bilanz zeigt, wie viel du sparen kannst
  - Einheitlich umbenennen geht mit einem Klick
  - Bei geschützten Ordnern (NAS) wird nichts endgültig gelöscht, sondern nur in einen Ordner „_Papierkorb“ verschoben
- **Nachtmodus:** Start zu einer festen Uhrzeit, danach den PC herunterfahren oder in den Ruhezustand schicken, Nachricht aufs Handy (ntfy)
- 7 Designs, Start- und Abschieds-Animation wie im ffmpeg_encode Studio

**Neu in 1.1.0: zwei Grafikkarten und paralleles Umwandeln**
- Das Programm erkennt Prozessor-Grafik (z. B. Radeon 760M) und eigene Grafikkarte (z. B. Radeon RX 7000) getrennt
- FFmpeg wird bei Windows fest auf die **eigene Grafikkarte** eingestellt. Eine zweite FFmpeg-Kopie nutzt die Prozessor-Grafik
- **⚡ Prozessor & Grafikkarten** (Auto/Manuell): Die KI verteilt mehrere Videos gleichzeitig auf Prozessor (x265, beste Qualität), eigene Karte und Prozessor-Grafik. Dabei bleibt die Qualität mindestens „Gut“
- Im KI-Monitor siehst du, welcher Film gerade wo läuft, dazu die geschätzte Zeitersparnis

**Neu in 1.1.1**
- Ordner einlesen mit **Ladebalken in Prozent** und Anzahl gefundener Dateien, dazu deutlich schneller bei NAS- und Netzwerk-Ordnern
- Ladebalken auch beim Bild-Abgleich und bei den Prüfsummen
- Neuer Knopf oben rechts: Fenster **auf den anderen Bildschirm** schieben (erscheint bei 2 Monitoren)

**Neu in 1.1.2**
- Liegt ein Ordner im anderen (z. B. B = „FULL HD CINEMA\x265“ in A = „FULL HD CINEMA“), wird er beim äußeren Ordner **automatisch ausgelassen**. Es wird also keine Datei mehr mit sich selbst verglichen. Dazu kommt ein Hinweis
- Neuer Schalter in den Abgleich-Regeln: „Unterordner mitlesen“ (an/aus)

**Neu in 1.1.3**
- Das Programm **merkt sich jetzt alles** bis zum nächsten Start: Design, Start-Animation an/aus, Auto/Manuell-Schalter, eigene Einstellungen (Codec, Zielgröße, Zeitplan …) und eigene Vorlagen. Bisher ging das beim Neustart verloren

**Neu in 1.1.4**
- Steht ein alter Codec im Dateinamen (x264, H.264, AVC …), **fragt die KI vor dem Start**, ob sie ihn passend ändern soll, z. B. `…BluRay.x264-DETAiLS` zu `…BluRay.x265-DETAiLS`. Wird das Bild verkleinert, passt sie auch die Auflösung an (1080p → 720p). Der restliche Name bleibt wie im Original
- „Antwort merken“ oder unter „Ausgabe & Zeitplan“: immer fragen, immer anpassen oder nie
