; ffmpeg_encode Studio – Windows-Installer (Inno Setup 6)
; Bringt alles mit: Programm (inkl. Python), FFmpeg + FFprobe mit allen Codecs (x264, x265, AAC, NVENC, Quick Sync, AMF)
; und installiert bei Bedarf die Microsoft WebView2-Laufzeit (für das Programmfenster).
; Installation nur für den aktuellen Benutzer – keine Administratorrechte nötig.
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{9C3E7B21-5D4A-4F8E-A6B2-E10C5F7D3A84}
AppName=ffmpeg_encode Studio
AppVersion={#AppVersion}
AppVerName=ffmpeg_encode Studio {#AppVersion}
AppPublisher=Butchies
AppPublisherURL=https://butchies-groove.duckdns.org
DefaultDirName={localappdata}\Programs\ffmpeg_encode Studio
DefaultGroupName=ffmpeg_encode Studio
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=ffmpeg_encode_Studio-Setup
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\ffmpeg_encode_Studio.exe
UninstallDisplayName=ffmpeg_encode Studio
WizardStyle=modern
WizardImageFile=installer-side.bmp
WizardSmallImageFile=installer-small.bmp
Compression=lzma2/ultra64
SolidCompression=yes
CloseApplications=force
RestartApplications=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"

[Tasks]
Name: "desktopicon"; Description: "Verknüpfung auf dem Desktop anlegen"; GroupDescription: "Zusätzlich:"

[Files]
Source: "dist\ffmpeg_encode_Studio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "ffmpeg\bin\*"; DestDir: "{app}\ffmpeg\bin"; Flags: ignoreversion recursesubdirs
Source: "ffmpeg\LICENSE.txt"; DestDir: "{app}\ffmpeg"; Flags: ignoreversion skipifsourcedoesntexist
Source: "LIESMICH.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: NeedsWebView2

[Icons]
Name: "{autoprograms}\ffmpeg_encode Studio"; Filename: "{app}\ffmpeg_encode_Studio.exe"; Comment: "MP3 + Bild zu YouTube-Videos machen"
Name: "{autodesktop}\ffmpeg_encode Studio"; Filename: "{app}\ffmpeg_encode_Studio.exe"; Comment: "MP3 + Bild zu YouTube-Videos machen"; Tasks: desktopicon

[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Microsoft WebView2 wird eingerichtet …"; Flags: waituntilterminated; Check: NeedsWebView2
Filename: "{app}\ffmpeg_encode_Studio.exe"; Description: "ffmpeg_encode Studio jetzt starten"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/c taskkill /f /im ffmpeg_encode_Studio.exe"; Flags: runhidden; RunOnceId: "StopStudio"

[Code]
const
  WV2 = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';

function HasWV2(Root: Integer; Key: String): Boolean;
var
  V: String;
begin
  Result := RegQueryStringValue(Root, Key, 'pv', V) and (V <> '') and (V <> '0.0.0.0');
end;

function NeedsWebView2: Boolean;
begin
  Result := not (HasWV2(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\' + WV2) or
                 HasWV2(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\' + WV2) or
                 HasWV2(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\' + WV2));
end;
