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
Stop-Process -Id $p.Id -Force
'SMOKE OK' | Tee-Object -FilePath $Out -Append
