# Auftrag: Jahreszeiten- & Feiertags-Szenen für Start- und Beenden-Animation

Du bist ein erfahrener Motion-/UI-Designer und Frontend-Entwickler. **Entwirf und programmiere selbst, frei und kreativ,**
eigene jahreszeitliche und feiertägliche Animationen für die **Start-Animation** (Splash) und die **Beenden-Animation**
(Abschied) meines Windows-Programms **„Butchies Video Converter AI“**. Es gibt keine Vorlage für die Szenen – Ideen,
Bildsprache, Bewegung und Effekte kommen komplett von dir. Ziel: hochwertig, stimmungsvoll, überraschend – nicht kitschig.

## Dateien in diesem Paket
- `original-start-beenden.html` – die **aktuelle** Start- und Beenden-Animation des Programms (genau so im Programm).
  Unten links: Knöpfe zum Abspielen und Wechseln der 7 Designs.
- `fonts/` – die Schriften des Programms (woff2, offline).

## Was ich möchte
1. Für jede Szene eine **eigene, von dir erfundene Animation** samt passender Texte. Wie die Szene aussieht und sich
   bewegt, entscheidest du. Einzige Bedingung: Sie soll zum Stil von `original-start-beenden.html` passen
   (Schriften, Farben der 7 Designs, edle Anmutung), damit man das Programm wiedererkennt. Du darfst den Aufbau
   (Logo-Ringe, Titel, Untertitel) dafür auch umgestalten.
2. Szenen (automatisch nach Datum, Feiertage haben Vorrang vor Jahreszeiten):
   - Jahreszeiten: Frühling (März–Mai), Sommer (Juni–Aug.), Herbst (Sep.–Nov.), Winter (Dez.–Feb.)
   - Silvester/Neujahr (31.12.–1.1.), Fasching (Weiberfastnacht bis Aschermittwoch = Ostern −52 bis −46 Tage),
     Ostern (Karfreitag–Ostermontag, Ostersonntag per Gauß-Formel), Muttertag (2. Sonntag im Mai),
     Vatertag (Christi Himmelfahrt = Ostern +39), Halloween (31.10.), Advent (1.–4. Adventssonntag, Kranz mit
     1–4 brennenden Kerzen), Nikolaus (6.12.), Weihnachten (24.–26.12.), Geburtstag (Datum aus Einstellungen)
3. Beim Beenden ersetzt ein passender Gruß den großen Titel (z. B. „Frohe Weihnachten!“, „Guten Rutsch!“).

## Technische Vorgaben (wichtig!)
- Läuft **offline** in WebView2 (Chromium) – **keine CDNs, keine externen Bibliotheken, keine Bilder aus dem Netz**.
  Nur HTML/CSS/JS, SVG und Canvas. Emojis nur sparsam – lieber eigene SVG-Formen (sieht in allen Designs gleich aus).
- Farben ausschließlich über die vorhandenen CSS-Variablen der 7 Designs: `--a`, `--b`, `--bg`, `--bg2`,
  `--glow`, `--muted`, `--text` (Szenen dürfen eigene Akzentfarben ergänzen, müssen aber in **allen 7 Designs**,
  auch im hellen Design `light`, gut aussehen und lesbar bleiben).
- Dauer: Start ca. 3,4 s (Klick überspringt), Beenden ca. 3 s + 1,5 s Schließ-Welle (`.goodbye.closing`).
- Flüssig mit 60 fps, aber **sparsam** (der PC wandelt evtl. gerade Videos um): max. ~150 Partikel,
  `requestAnimationFrame` stoppen, wenn die Animation vorbei ist.
- `prefers-reduced-motion: reduce` beachten (dann nur statisches Bild).
- Keine geschützten Figuren/Marken (kein Disney, keine Coca-Cola-Weihnachtsmann-Optik usw.).
- Alle Texte auf Deutsch, kurz und herzlich.

## So soll das Ergebnis aussehen (damit ich es direkt einbauen kann)
Liefere **drei Dateien** als Code-Blöcke:
1. `seasons.css` – alle Styles der Szenen (Klassen mit Präfix `ssn-`).
2. `seasons.js` – ohne Abhängigkeiten, stellt bereit:
   - `Seasons.pick(date, {birthday:'MM-TT'|null})` → Szenen-Schlüssel (z. B. `'advent'`), inkl. Datumslogik oben
   - `Seasons.info(key, date)` → `{name, kicker, tag, bye, icon}` (Texte + Symbol als SVG-String)
   - `Seasons.mount(containerEl, key, mode)` → startet die Animation im Container (`mode` = `'start'` oder `'bye'`),
     gibt ein Objekt mit `stop()` zurück
3. `demo.html` – bindet beide Dateien ein und zeigt alle Szenen zum Durchschalten (Start/Beenden, 7 Designs),
   aufgebaut wie `original-start-beenden.html`.

Erkläre zum Schluss in 2–3 Sätzen pro Szene deine Idee.
