**ffmpeg_encode Studio 1.11.0** – MP3 + Bild → fertiges YouTube-Video (4K, 1440p, 1080p, Shorts 9:16, Shorts 4K).

**Installieren:** `ffmpeg_encode_Studio-Setup.exe` herunterladen und starten. Es werden keine Administratorrechte gebraucht.
FFmpeg mit allen Codecs ist dabei, WebView2 wird bei Bedarf automatisch eingerichtet.

- Drag & Drop für Song und Bild, echte Vorschau des fertigen Bildes
- 36 Übergänge für „Bild kommt“ / „Bild geht“ mit Sofort-Vorschau, Fades für den Ton
- Start/Ende frei wählbar, Shorts automatisch auf max. 3:00 begrenzt
- Audio-Visualizer (Wellenform/Spektrum) in Design- oder eigener Farbe
- Grafikkarte automatisch (NVIDIA NVENC, Intel Quick Sync, AMD AMF), sonst CPU – mit automatischem Rückfall
- Fortschritt in Prozent, Warteschlange, 7 Designs und Start-/Abschieds-Animation der Butchies-Webseite

**Neu in 1.11.0 – stabiler, schneller, aufgeräumt**
- **Arbeitsspeicher-Prüfung vor der KI:** ist zu wenig frei, kommt vorher ein Hinweis mit „Aufräumen & starten“ (gibt eigenen Speicher frei, zeigt die größten anderen Programme – beenden nur per Klick). Stürzt die KI trotzdem ab, kommt eine klare Meldung statt Stille
- **Weniger Arbeitsspeicher:** die KI blendet ihre Modelldateien ein statt sie zu kopieren (ca. 3 GB weniger fester Speicher)
- **Neue Stufe „Sehr schnell (640 × 352)“** – danach macht der KI-Upscaler das Bild scharf
- **Live mitschauen:** jedes fertige Stück läuft sofort als Vorschau, während die KI am nächsten rechnet
- **Hauptfenster-Knopf repariert:** das Hauptfenster zeigt jetzt eine kleine Live-Anzeige (Fortschritt + Vorschau) des KI-Videos; Klick darauf holt das KI-Fenster zurück. Die Kurz-Anzeige war vorher versehentlich unsichtbar
- **24 Bilder/s:** Videos mit KI-Video laufen automatisch mit 24 Bildern/s – wie die KI selbst, keine doppelten Bilder, schneller
- **Kein doppeltes Rechnen:** läuft eine KI-Video-Rechnung, wartet die normale Umwandlung (und umgekehrt)
- **Aufgeräumt:** Schnelltest + Training zu einem „KI-Training“ zusammengelegt (misst alle Grafikkarten und Einstellungen), doppelte KI-Video-Kachel und doppelter Update-Kasten entfernt

**Neu in 1.10.0 – die KI optimiert sich selbst**
- **KI-Training** (⚙️ Einstellungen → 🧠 KI-Hardware): probiert alle Tempo-Einstellungen des KI-Motors (Flash-Attention, Direkt-Faltung, Text-Teil auf Karte/Prozessor, Auslagern) mit einem echten Stück auf deiner Grafikkarte aus und nimmt danach immer die schnellste, die sicher läuft
- **Gedächtnis:** jede KI-Rechnung misst mit – die KI wird mit der Zeit genauer, auch ohne Training
- **Weicht selbst aus:** reicht der Grafikspeicher nicht, merkt sich die KI das, rechnet das Stück automatisch mit einer sichereren Einstellung neu und macht es beim nächsten Mal gleich richtig
- **🤖 KI-Tipp bei den Varianten:** jede Variante bekommt eine Note (Schärfe, wenig Flackern, Bewegung, nah am Original); die beste wird vorgewählt. Aus deinen Sternen lernt die KI, was dir wichtig ist
- Vorwissen eingebaut: sinnvolle Startwerte je Grafikkarten-Hersteller, bevor auf deinem PC gemessen wurde
- Fehler behoben: Stürzte die KI wegen Grafikspeicher sofort ab, kam nur „Verbindung getrennt“ statt einer klaren Meldung

**Neu in 1.9.0 – KI-Hardware-Analyse, schnellere KI, Updater**
- **KI-Hardware-Analyse** (⚙️ Einstellungen → 🧠 KI-Hardware): erkennt Prozessor, Arbeitsspeicher und alle Grafikkarten und verteilt die Arbeit – KI-Bewegung auf der stärksten Karte, KI-Upscaler **gleichzeitig** auf der zweiten (z. B. RX 7600M XT + Radeon 760M). Auch von Hand wählbar
- **Schnelltest:** misst jede Grafikkarte mit einem kleinen KI-Stück und nimmt danach automatisch die wirklich schnellste
- **Schneller:** die KI bleibt während eines Auftrags geladen (vorher wurden die 8 GB für jedes Stück neu geladen); der Text-Teil der KI läuft im Arbeitsspeicher, damit der Grafikspeicher fürs Bild reicht; Upscaler rechnet parallel statt danach
- **Updater eingebaut** (⚙️ Einstellungen → ⬆️ Updates): neue Version mit einem Klick laden und installieren, das Programm startet danach von selbst neu; automatische Suche abschaltbar
- **Speicher aufräumen:** Größe des KI-Zwischenspeichers sehen und leeren, KI-Paket entfernen
- Aufgeräumt: ungenutzter Code und alte Stile entfernt; KI-Motor fest auf eine geprüfte Version gesetzt

**Neu in 1.8.0 – KI-Video: echte Bewegung aus deinem Bild**
- Neue Karte „🎬 KI-Video“: eine KI (Wan 2.2, offline auf deinem PC) erzeugt aus deinem Bild echte Bewegung – z. B. Haare wehen, Blinzeln, Tanzen, Wasser, Wolken, Licht
- 12 fertige Bewegungen + eigene Beschreibung (Deutsch geht)
- Nur die markierte Fläche bewegt sich, der Rest bleibt dein scharfes Original (Markieren → „🎬 KI-Video“)
- Erst 3 Varianten der ersten Sekunden zum Auswählen, dann die volle Länge: 10 s, 30 s, 1 Min, 2 Min oder ganzer Song
- Lange Videos: Stück für Stück aneinandergereiht, regelmäßig weich zurück zum Original (damit nichts „verläuft“), am Ende nahtlose Wiederholung
- Zeitschätzung vorher (lernt das Tempo deines PCs), fertige Stücke bleiben gespeichert – nach Abbruch geht es weiter
- Läuft über Vulkan auf AMD-, NVIDIA- und Intel-Grafikkarten; das KI-Paket (ca. 8 GB) wird nur auf Wunsch einmal geladen
- Projekte speichern jetzt auch die KI-Video-Fläche mit; Fehler behoben: gemalte Effekt-Flächen gingen beim Öffnen eines Projekts verloren
- **Eigenes KI-Video-Fenster für den 2. Monitor:** öffnet sich nur beim Klick auf „KI-Video“, großer Player rechts, alles andere bleibt im Hauptfenster wie gewohnt (bei Monitoren an verschiedenen Grafikkarten wie beim Video Converter gegen Ruckeln abgesichert)
- **Bewerten & ändern:** Sterne, Stichworte (z. B. „Bewegung zu stark“, „Gesicht verzerrt“) und eigener Änderungswunsch → „Ändern & 3 neue Varianten“; die KI lernt aus den Bewertungen und gibt häufige Wünsche künftig automatisch mit (sichtbar unter „KI lernt“)
- **KI-Upscaler auf Full HD:** eine zweite KI (Real-ESRGAN) rechnet das KI-Video scharf auf 1920 × 1080 hoch
- Farben des KI-Videos werden automatisch ans Original angeglichen (kein Farbsprung, kein Wegdriften bei langen Videos)
- **Neues Design „Blau-Weiß“** (klar & frisch)
- **Installer neu:** Funktionsseite mit Bildern, wechselnde Bilder während der Installation, Kopfleiste im Programm-Look

**Neu in 1.7.0 – die KI lernt mit**
- **Beste Stelle lernt dich kennen:** merkt sich, welchen Vorschlag du nimmst (Refrain, Drop oder Emotional), wie deine Lieblingsstellen klingen und ob du Start/Ende danach noch verschiebst – dein Favorit kommt nach vorne (★ Dein Favorit) und der Start passt sich an
- **Songtext lernt deine Wörter:** „✏️ Text korrigieren“ nach der Erkennung – korrigierte Wörter (z. B. Namen) bekommt Whisper bei den nächsten Songs als Hilfe mit; korrigierte Texte werden für den Song gespeichert
- **Dein Stil:** nach 3 Videos kennt die KI deine Lieblings-Effekte, Kamera und Regler-Werte und schlägt sie bei neuen Bildern vor („Übernehmen“)
- **Neues Fenster „KI lernt“** (Kopfzeile): zeigt, was gelernt wurde – jeden Teil oder alles kannst du mit „Vergessen“ zurücksetzen
- **Update-Hinweis:** das Programm meldet, wenn eine neue Version (z. B. mit besserer KI) da ist
- Alles bleibt offline auf deinem PC (Datei learn.json im Einstellungsordner)
- Kopfzeile wie beim Video Converter: „AI“-Logo im Titel und Schild mit Version + Grafikkarten; passt sich an kleinere Bildschirme an

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
