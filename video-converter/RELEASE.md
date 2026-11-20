**Butchies Video Converter AI 1.0.0**: Videos mit KI-Hilfe in H.264 / H.265 umwandeln. Dazu gibt es einen Player für alle Codecs, einen Vorher/Nachher-Vergleich und einen Ordner-Abgleich.

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
