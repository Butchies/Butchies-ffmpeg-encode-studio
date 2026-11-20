**ffmpeg_encode Studio 1.6.5** – MP3 + Bild → fertiges YouTube-Video (4K, 1440p, 1080p, Shorts 9:16, Shorts 4K).

**Installieren:** `ffmpeg_encode_Studio-Setup.exe` herunterladen und starten. Es werden keine Administratorrechte gebraucht.
FFmpeg mit allen Codecs ist dabei, WebView2 wird bei Bedarf automatisch eingerichtet.

- Drag & Drop für Song und Bild, echte Vorschau des fertigen Bildes
- 36 Übergänge für „Bild kommt“ / „Bild geht“ mit Sofort-Vorschau, Fades für den Ton
- Start/Ende frei wählbar, Shorts automatisch auf max. 3:00 begrenzt
- Audio-Visualizer (Wellenform/Spektrum) in Design- oder eigener Farbe
- Grafikkarte automatisch (NVIDIA NVENC, Intel Quick Sync, AMD AMF), sonst CPU – mit automatischem Rückfall
- Fortschritt in Prozent, Warteschlange, 7 Designs und Start-/Abschieds-Animation der Butchies-Webseite

**Neu in 1.6.5**
- Fehler behoben: Die Partikel-Menge (Staub, Schnee, Funken, Glitzer, Regen, Linien, Bokeh) hing von der Auflösung ab – im fertigen Video waren es je nach Format 3- bis 12-mal mehr Partikel als eingestellt und in der Vorschau gezeigt. Jetzt sieht das Video genau wie die Vorschau aus, und „Menge“ wirkt wie eingestellt.

**Neu in 1.6.4**
- Warteschlange neu: langer Dateiname wird sauber gekürzt, Status-Schild (Läuft/Wartet/Fertig/Fehler), große Prozentzahl, Restzeit und Tempo, Knöpfe in eigener Zeile; zählt flüssig hoch ohne Flackern

**Neu in 1.6.3**
- Fensterknöpfe (Minimieren, Monitor, Vollbild, Maximieren, Schließen) sitzen jetzt direkt in der Kopfzeile – gleich hoch und im gleichen Stil wie die anderen Knöpfe; bei kleinen Fenstern rutscht nichts mehr darunter (die Knöpfe zeigen dann nur ihre Symbole)

**Neu in 1.6.2**
- Fensterknöpfe oben rechts als passende, kompakte Leiste im Design (überdecken nichts mehr)
- Warteschlange zeigt beim Rendern alle übernommenen Effekt- und Kamera-Werte

**Neu in 1.6.1**
- Das Songtext-Modell (Whisper light, ca. 145 MB) ist jetzt **direkt im Installer** – nichts wird mehr nachgeladen, „Mit Songtext“ funktioniert sofort und komplett offline

**Neu in 1.6.0**
- **Shorts-Helfer** (bei „YouTube Shorts“ / „Shorts 4K“): Länge wählen (15 s – 3:00) und **✨ Beste Stelle finden** – die KI analysiert deinen Song offline (Takt, Energie, Drop, Wiederholung) und schlägt 3 Stellen vor: Refrain, Höhepunkt/Drop, Emotionaler Aufbau – mit ▶ Anhören und „Übernehmen“ (setzt Start/Ende, Schnitt auf dem Takt, kurz ein-/ausgeblendet)
- **Mit Songtext** (Whisper light, offline): erkennt die gesungenen Zeilen und findet Refrain (wiederholte Zeilen) und gefühlvolle Stellen genauer
- **Vollbild für 2 Monitore**: Knopf oben rechts oder F11 – füllt den ganzen Monitor, bleibt aber ein normales Fenster: Fenster und Dateien vom anderen Monitor kannst du weiter hin- und herziehen; Knopf „Anderer Monitor“ (oder Win + Umschalt + Pfeil) schiebt das Vollbild auf den anderen Bildschirm
- Start- und Abschiedsbildschirm: **Butchies Encode Studio AI** – „AI“ in den Farben des Designs mit Lichtschimmer
- KI-Video: statt der großen Karte nur noch eine kleine Kachel „🎬 KI-Video · bald“ bei den Bild-Effekten

**Neu in 1.5.0**
- Auch **Encoding & Ausgabe**, **Zeitleiste & Länge** und **Bild-Effekte & Kamera** sind einklappbar und beim Start zu (zugeklappt mit Zusammenfassung, bei der Zeitleiste mit „⚠ Hinweis“, falls es einen gibt)
- Die Leiste „Meine Vorlagen“ ist weg – stattdessen Knopf **„Vorlagen“** oben in der Kopfzeile (Speichern, Laden, letzte Vorlagen); dadurch mehr Platz für die Vorschau

**Neu in 1.4.0**
- Fenster **Zielformat, Bild-Anpassung, Audio-Visualizer, Fade-Effekte** und das Menü **Markieren** sind einklappbar und beim Start zu – zugeklappt steht rechts die aktuelle Wahl
- Markieren hat zwei getrennte Menüs: **✋ Von Hand** (Kasten, Fläche, Linie, Ring) und **✨ KI** (Motiv auswählen, Linie an Kante, Ring ums Motiv, Platzvorschlag)
- Was die KI markiert, wird immer als **Welle** dargestellt – 5 Wellenformen zur Auswahl (Neon, Welle, Linie, Punkte, Bündel); einen Stil im Visualizer wählen schaltet zurück auf „von Hand“
- Wellen auf einer Linie/einem Ring schwingen jetzt mittig um die Linie (vorher konnten sie doppelt erscheinen)
- Keine Punkte-Flut mehr: nach der KI-Linie werden keine Dutzende Anfasser mehr angezeigt

**Neu in 1.3.0**
- **Bild-Effekte** (10 Stück): Lichtlinien, Funken, Glitzern, Lichtkreise, Schwebeteilchen, Schnee, Regen, Nebel, Fließen – Farben automatisch aus dem Bild (oder eigene Farbe / Regenbogen), Menge, Tempo, Größe, Deckkraft, Winkel, **Im Takt** der Musik
- Effekte wirken auf dem ganzen Bild oder nur dort, wo du markierst: **Fläche** malen (auch mit ✨ KI-Auswahl), **Linie** oder **Ring** – Lichtlinien laufen genau an deiner Linie entlang
- **Kamera-Bewegung**: Sanfter Zoom, Langsamer Schwenk, **3D-Kamerafahrt** (eine KI erkennt Vorder- und Hintergrund – Depth Anything V2, offline)
- **Grafikkarten-Erkennung**: Name und Grafikspeicher stehen unten in der Statusleiste
- **KI-Video** (z. B. tanzende Person) als Vorschau-Karte „Demnächst“ – noch ohne Funktion, zeigt schon, ob deine Grafikkarte dafür reichen würde

**Neu in 1.2.0**
- Visualizer-Platz markieren (gilt nur für dieses Video, wird im Projekt gespeichert): **Fläche** malen (Pinsel, Radierer, Rechteck, Ellipse), **Linie** (Balken stehen entlang einer gezeichneten Linie), **Ring** (Balken rund um ein Motiv)
- KI-Helfer, komplett offline: **✨ KI-Auswahl** (auf ein Motiv klicken → Fläche wird automatisch erkannt, MobileSAM), **✨ KI verfeinern** (legt die Linie an die nächste Kante im Bild), **✨ Motiv antippen** (Ring passend ums Motiv), **✨ KI-Platzvorschlag** (findet ruhige Stellen, meidet Gesichter)
- Programm startet bildschirmfüllend, **F11** = echtes Vollbild (Esc zurück)
- Oberfläche für 1920 × 1080 optimiert (auch bei 125 % Windows-Skalierung): Spalten scrollen einzeln, Vorschau bleibt groß

**Neu in 1.1.0**
- Audio-Visualizer: 20 Stile, 5 Farbarten (Einfarbig, Verlauf, Regenbogen, Zufall, Nach Sound)
- Visualizer im Vorschaubild ziehen und skalieren, 9 Andockplätze + 3 Bänder mit magnetischem Einrasten
- Werkstatt: Stärke, Deckkraft, Leuchten, Dichte, Ruhe, Linienstärke, Spiegelungen, weiche Ränder
- Vorschau mit Ton (6-Sekunden-Clip), beim Anhören zeigt die Vorschau die echten Frequenzen
- Vorlagen speichern/laden und Projekte (.fesproj mit Song & Bild)
