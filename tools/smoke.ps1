# Echter Test auf Windows (GitHub Actions): startet das fertige Programm, legt Song + Bild ein,
# konvertiert ein kurzes 1080p-Video und ein Shorts-Video und prüft das Ergebnis mit ffprobe.
param([string]$Exe, [string]$Out)
$ErrorActionPreference = 'Stop'
$work = Join-Path $env:RUNNER_TEMP 'fes-smoke'
New-Item -ItemType Directory -Force -Path $work | Out-Null
$ff = Join-Path (Split-Path $Exe) 'ffmpeg\bin\ffmpeg.exe'
$fp = Join-Path (Split-Path $Exe) 'ffmpeg\bin\ffprobe.exe'
& $ff -v error -y -f lavfi -i "sine=frequency=330:duration=8" -ac 2 -c:a libmp3lame -b:a 192k "$work\song.mp3"
& $ff -v error -y -f lavfi -i "testsrc2=s=1600x1200" -frames:v 1 "$work\bild.png"

$p = Start-Process -FilePath $Exe -ArgumentList '--no-window' -PassThru -RedirectStandardOutput "$work\out.txt" -RedirectStandardError "$work\err.txt"
$url = $null
for ($i = 0; $i -lt 40 -and -not $url; $i++) {
  Start-Sleep -Milliseconds 500
  if (Test-Path "$work\out.txt") { $m = Select-String -Path "$work\out.txt" -Pattern 'http://127\.0\.0\.1:\d+/#\S+'; if ($m) { $url = $m.Matches[0].Value } }
}
if (-not $url) { Get-Content "$work\out.txt", "$work\err.txt" -ErrorAction SilentlyContinue; throw 'Programm hat nicht gestartet' }
$base = $url.Split('#')[0].TrimEnd('/'); $tok = $url.Split('#')[1]
$h = @{ 'X-Studio' = $tok }
"Programm läuft: $base" | Tee-Object -FilePath $Out
$info = Invoke-RestMethod "$base/api/info" -Headers $h
"FFmpeg gefunden: $($info.ffmpeg)  Pfad: $($info.ffmpeg_path)" | Tee-Object -FilePath $Out -Append
if (-not $info.ffmpeg) { throw 'FFmpeg nicht gefunden' }
$ui = Invoke-WebRequest -UseBasicParsing "$base/" -Headers $h
"Oberfläche: $($ui.StatusCode) $($ui.Content.Length) Bytes" | Tee-Object -FilePath $Out -Append

function Stage($file, $kind) {
  $r = Invoke-RestMethod -Method Post -Uri "$base/api/stage?name=$([uri]::EscapeDataString((Split-Path $file -Leaf)))&kind=$kind" -Headers $h -InFile $file -ContentType 'application/octet-stream'
  return $r.token
}
$a = Stage "$work\song.mp3" 'audio'
$b = Stage "$work\bild.png" 'image'
$outdir = Join-Path $work 'videos'
$cases = @(
  @{ fmt = 'yt1080'; fps = 30; viz = $false; fit = 'blur'; w = 1920; h = 1080 },
  @{ fmt = 'sh1080'; fps = 25; viz = $true; fit = 'cover'; w = 1080; h = 1920; style = 'leddots'; mode = 'sound' },
  @{ fmt = 'yt1080'; fps = 30; viz = $true; fit = 'contain'; w = 1920; h = 1080; style = 'neon'; mode = 'random' }
)
foreach ($c in $cases) {
  $st = @{ fmt = $c.fmt; fps = $c.fps; viz = $c.viz; fit = $c.fit; fadeIn = 1; fadeOut = 1; transIn = 'circleopen'; transOut = 'zoomin' }
  if ($c.style) { $st.vizStyle = $c.style; $st.vizMode = $c.mode; $st.vizGlow = 45; $st.vizDock = 'bc' }
  $body = @{ audio = $a; image = $b; outdir = $outdir; settings = $st } | ConvertTo-Json -Depth 4
  $job = Invoke-RestMethod -Method Post -Uri "$base/api/encode" -Headers $h -Body $body -ContentType 'application/json'
  for ($i = 0; $i -lt 240; $i++) {
    Start-Sleep -Seconds 1
    $j = Invoke-RestMethod "$base/api/job/$($job.id)" -Headers $h
    if (@('fertig', 'fehler', 'abgebrochen') -contains $j.state) { break }
  }
  "[$($c.fmt)] Status: $($j.state) $($j.percent) % – $($j.out)" | Tee-Object -FilePath $Out -Append
  if ($j.state -ne 'fertig') { $j.error | Tee-Object -FilePath $Out -Append; throw "Konvertierung $($c.fmt) fehlgeschlagen" }
  $probe = & $fp -v error -select_streams v:0 -show_entries stream=width,height,codec_name -of csv=p=0 $j.out
  "[$($c.fmt)] ffprobe: $probe" | Tee-Object -FilePath $Out -Append
  if ($probe -notmatch "$($c.w),$($c.h)") { throw "Falsche Auflösung bei $($c.fmt)" }
}
# Vorschau-Clip mit Ton (Visualizer "Nach Sound")
$vp = Invoke-RestMethod -Method Post -Uri "$base/api/viz-preview" -Headers $h -ContentType 'application/json' -Body (@{ audio = $a; image = $b; settings = @{ fmt = 'yt1080'; viz = $true; vizStyle = 'mirror'; vizMode = 'sound' } } | ConvertTo-Json -Depth 4)
"Visualizer-Vorschau: $($vp.url)" | Tee-Object -FilePath $Out -Append
if (-not $vp.url) { throw 'Visualizer-Vorschau fehlgeschlagen' }
# Projekt speichern + laden, Vorlage speichern
$pr = Invoke-RestMethod -Method Post -Uri "$base/api/project/save" -Headers $h -ContentType 'application/json' -Body (@{ name = 'Smoke Projekt'; audio = $a; image = $b; settings = @{ fmt = 'sh1080'; viz = $true; vizStyle = 'led' } } | ConvertTo-Json -Depth 4)
$ld = Invoke-RestMethod -Method Post -Uri "$base/api/project/load" -Headers $h -ContentType 'application/json' -Body (@{ path = $pr.path } | ConvertTo-Json)
"Projekt: $($pr.path) -> geladen: $($ld.settings.vizStyle) / $($ld.audio.name)" | Tee-Object -FilePath $Out -Append
if ($ld.settings.vizStyle -ne 'led') { throw 'Projekt laden fehlgeschlagen' }
$ps = Invoke-RestMethod -Method Post -Uri "$base/api/presets/save" -Headers $h -ContentType 'application/json' -Body (@{ name = 'Smoke Vorlage'; settings = @{ fmt = 'yt4k' } } | ConvertTo-Json -Depth 4)
"Vorlagen: $($ps.presets.Count)" | Tee-Object -FilePath $Out -Append
# ---- 1.2.0: Markieren + KI (MobileSAM) ----
"KI: $($info.ai.text)  (Werkzeuge: $($info.ai.tools), Modell: $($info.ai.model))" | Tee-Object -FilePath $Out -Append
if (-not $info.ai.tools) { throw 'KI-Werkzeuge (OpenCV) fehlen im Programm' }
if (-not $info.ai.model) { throw 'KI-Modell (MobileSAM) nicht mitgeliefert' }
& $ff -v error -y -f lavfi -i "color=c=0x1c2a3a:s=1600x900,drawbox=x=600:y=250:w=400:h=400:color=0xf2c94c:t=fill" -frames:v 1 "$work\motiv.png"
$m = Stage "$work\motiv.png" 'image'
$seg = Invoke-RestMethod -Method Post -Uri "$base/api/mark/segment" -Headers $h -ContentType 'application/json' -Body (@{ image = $m; settings = @{ fmt = 'yt1080'; fit = 'contain' }; points = @(, @(0.5, 0.5, 1)) } | ConvertTo-Json -Depth 5)
"KI-Auswahl: Methode $($seg.method), Rahmen $($seg.bbox -join ' / '), $($seg.seconds) s $($seg.note)" | Tee-Object -FilePath $Out -Append
if ($seg.method -ne 'ki') { throw "KI-Auswahl lief nicht mit MobileSAM: $($seg.note)" }
$bx = $seg.bbox
if ([math]::Abs($bx[0] - 37.5) -gt 4 -or [math]::Abs($bx[2] - 25) -gt 5 -or [math]::Abs($bx[3] - 44.4) -gt 6) { throw 'KI-Auswahl hat das Motiv nicht richtig erkannt' }
$ref = Invoke-RestMethod -Method Post -Uri "$base/api/mark/refine" -Headers $h -ContentType 'application/json' -Body (@{ image = $m; settings = @{ fmt = 'yt1080'; fit = 'contain' }; points = @(@(0.30, 0.25), @(0.5, 0.30), @(0.70, 0.25)); closed = $false } | ConvertTo-Json -Depth 5)
"Linie verfeinert: $($ref.points.Count) Punkte" | Tee-Object -FilePath $Out -Append
$sug = Invoke-RestMethod -Method Post -Uri "$base/api/mark/suggest" -Headers $h -ContentType 'application/json' -Body (@{ image = $m; settings = @{ fmt = 'yt1080'; fit = 'contain' } } | ConvertTo-Json -Depth 5)
"Platzvorschläge: $(($sug.suggestions | ForEach-Object { $_.name }) -join ', ')" | Tee-Object -FilePath $Out -Append
if ($sug.suggestions.Count -lt 1) { throw 'Keine Platzvorschläge' }
& $ff -v error -y -f lavfi -i "color=c=black:s=960x540,drawbox=x=100:y=300:w=500:h=200:color=white:t=fill,format=gray" -frames:v 1 "$work\maske.png"
$mk = Invoke-RestMethod -Method Post -Uri "$base/api/mark/mask" -Headers $h -InFile "$work\maske.png" -ContentType 'image/png'
$ring = @(); for ($i = 0; $i -lt 48; $i++) { $t = $i / 48 * 2 * [math]::PI; $ring += , @([math]::Round(0.5 + 0.15 * [math]::Cos($t), 4), [math]::Round(0.5 + 0.2667 * [math]::Sin($t), 4)) }
$marks = @(
  @{ name = 'Maske'; s = @{ vizShape = 'mask'; vizMask = $mk.token; vizX = $mk.bbox[0]; vizY = $mk.bbox[1]; vizW = $mk.bbox[2]; vizH = $mk.bbox[3]; vizStyle = 'mirror' } },
  @{ name = 'Ring'; s = @{ vizShape = 'path'; vizClosed = $true; vizPath = $ring; vizStyle = 'bars'; vizBoth = $false } },
  @{ name = 'Linie'; s = @{ vizShape = 'path'; vizClosed = $false; vizPath = @(@(0.1, 0.7), @(0.5, 0.6), @(0.9, 0.7)); vizStyle = 'wave' } },
  @{ name = 'KI-Welle Ring'; s = @{ vizShape = 'path'; vizClosed = $true; vizPath = $ring; vizStyle = 'bars'; vizAi = $true; vizAiWave = 'neon' } }
)
foreach ($c in $marks) {
  $st = @{ fmt = 'yt1080'; fps = 25; viz = $true; fit = 'contain'; vizMode = 'rainbow' }
  foreach ($k in $c.s.Keys) { $st[$k] = $c.s[$k] }
  $body = @{ audio = $a; image = $m; outdir = $outdir; settings = $st } | ConvertTo-Json -Depth 6
  $job = Invoke-RestMethod -Method Post -Uri "$base/api/encode" -Headers $h -Body $body -ContentType 'application/json'
  for ($i = 0; $i -lt 240; $i++) {
    Start-Sleep -Seconds 1
    $j = Invoke-RestMethod "$base/api/job/$($job.id)" -Headers $h
    if (@('fertig', 'fehler', 'abgebrochen') -contains $j.state) { break }
  }
  "[Markierung $($c.name)] Status: $($j.state) – $($j.out)" | Tee-Object -FilePath $Out -Append
  if ($j.state -ne 'fertig') { $j.error | Tee-Object -FilePath $Out -Append; throw "Video mit Markierung $($c.name) fehlgeschlagen" }
}
# ---- 1.3.0: Bild-Effekte, Kamera, Grafikkarte ----
$info = Invoke-RestMethod "$base/api/info" -Headers $h
"Grafikkarte: $($info.gpu.text) | KI-Video: $($info.gpu.video_ai) – $($info.gpu.video_text)" | Tee-Object -FilePath $Out -Append
"Effekte: $($info.fx.effects.Count) · Kameras: $($info.fx.cams.Count) · Tiefen-KI: $($info.fx.depth)" | Tee-Object -FilePath $Out -Append
if ($info.fx.effects.Count -ne 10) { throw 'Effekt-Liste unvollständig' }
if (-not $info.fx.depth) { throw 'Tiefen-KI (Depth Anything) nicht mitgeliefert' }
& $ff -v error -y -f lavfi -i "color=c=0x23304a:s=1600x900,drawbox=x=0:y=600:w=1600:h=300:color=0x3a2a20:t=fill,drawbox=x=700:y=380:w=180:h=400:color=0x151515:t=fill" -frames:v 1 "$work\landschaft.png"
$l = Stage "$work\landschaft.png" 'image'
$fxcases = @(
  @{ name = 'Schnee + 3D-Kamerafahrt'; s = @{ fx = 'snow'; cam = 'depth'; fxBeat = $true } },
  @{ name = 'Funken + Zoom + Visualizer'; s = @{ fx = 'sparks'; cam = 'zoom'; viz = $true; vizMode = 'sound' } },
  @{ name = 'Lichtlinien entlang Ring'; s = @{ fx = 'streaks'; fxArea = 'path'; fxClosed = $true; fxPath = $ring } },
  @{ name = 'Fließen in Fläche + Schwenk'; s = @{ fx = 'flow'; fxArea = 'mask'; fxMask = $mk.token; fxX = $mk.bbox[0]; fxY = $mk.bbox[1]; fxW = $mk.bbox[2]; fxH = $mk.bbox[3]; cam = 'pan' } },
  @{ name = 'Nebel 4K'; s = @{ fx = 'fog'; fmt = 'yt4k' } }
)
foreach ($c in $fxcases) {
  $st = @{ fmt = 'yt1080'; fps = 25; fit = 'contain'; end = '0:06' }
  foreach ($k in $c.s.Keys) { $st[$k] = $c.s[$k] }
  $body = @{ audio = $a; image = $l; outdir = $outdir; settings = $st } | ConvertTo-Json -Depth 6
  $job = Invoke-RestMethod -Method Post -Uri "$base/api/encode" -Headers $h -Body $body -ContentType 'application/json'
  $t0 = Get-Date
  for ($i = 0; $i -lt 400; $i++) {
    Start-Sleep -Seconds 1
    $j = Invoke-RestMethod "$base/api/job/$($job.id)" -Headers $h
    if (@('fertig', 'fehler', 'abgebrochen') -contains $j.state) { break }
  }
  $sec = [math]::Round(((Get-Date) - $t0).TotalSeconds)
  "[Effekt $($c.name)] Status: $($j.state) – $sec s – $($j.meta.notes -join ' ')" | Tee-Object -FilePath $Out -Append
  if ($j.state -ne 'fertig') { $j.error | Tee-Object -FilePath $Out -Append; throw "Video mit Effekt $($c.name) fehlgeschlagen" }
  if (($j.meta.notes -join ' ') -match 'einfache Tiefensch') { throw 'Tiefen-KI lief nicht (einfache Schätzung benutzt)' }
}
Stop-Process -Id $p.Id -Force
'SMOKE OK' | Tee-Object -FilePath $Out -Append
