; Butchies Video Converter AI – Windows-Installer (Inno Setup 6)
; Bringt alles mit: Programm (inkl. Python), FFmpeg + FFprobe mit allen Codecs (x264, x265, AAC, NVENC, Quick Sync, AMF,
; libvmaf für die Qualitäts-Messung, zimg für HDR) und installiert bei Bedarf die Microsoft WebView2-Laufzeit.
; Sucht das Laufwerk mit dem meisten freien Speicher und schlägt dort Programm- und Video-Ordner vor.
; Installation nur für den aktuellen Benutzer – keine Administratorrechte nötig.
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6E2B9A41-3C7D-4F58-9B1E-7A4D2C8F5E13}
AppName=Butchies Video Converter
AppVersion={#AppVersion}
AppVerName=Butchies Video Converter {#AppVersion}
AppPublisher=Butchies
AppPublisherURL=https://butchies-groove.duckdns.org
DefaultDirName={code:BestInstallDir}
DefaultGroupName=Butchies Video Converter
DisableProgramGroupPage=yes
DisableDirPage=no
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=Butchies_Video_Converter-Setup
SetupIconFile=converter.ico
UninstallDisplayIcon={app}\Butchies_Video_Converter.exe
UninstallDisplayName=Butchies Video Converter
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
Source: "dist\Butchies_Video_Converter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "ffmpeg\bin\*"; DestDir: "{app}\ffmpeg\bin"; Flags: ignoreversion recursesubdirs
Source: "ffmpeg\LICENSE.txt"; DestDir: "{app}\ffmpeg"; Flags: ignoreversion skipifsourcedoesntexist
Source: "LIESMICH.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: NeedsWebView2

[Icons]
Name: "{autoprograms}\Butchies Video Converter"; Filename: "{app}\Butchies_Video_Converter.exe"; Comment: "Videos mit KI in H.264 / H.265 umwandeln"
Name: "{autodesktop}\Butchies Video Converter"; Filename: "{app}\Butchies_Video_Converter.exe"; Comment: "Videos mit KI in H.264 / H.265 umwandeln"; Tasks: desktopicon

[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Microsoft WebView2 wird eingerichtet …"; Flags: waituntilterminated; Check: NeedsWebView2
Filename: "{app}\Butchies_Video_Converter.exe"; Description: "Butchies Video Converter jetzt starten"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/c taskkill /f /im Butchies_Video_Converter.exe"; Flags: runhidden; RunOnceId: "StopConverter"

[UninstallDelete]
Type: files; Name: "{app}\install.json"

[Code]
const
  WV2 = '{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  GB = 1073741824;

var
  BestDrive: String;
  BestFree: Int64;
  OutPage: TInputDirWizardPage;
  DriveInfo: TNewStaticText;

function GetDriveTypeW(lpRootPathName: String): Cardinal;
  external 'GetDriveTypeW@kernel32.dll stdcall';

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

{ Alle festen Laufwerke durchgehen und das mit dem meisten freien Speicher merken }
procedure FindBestDrive;
var
  I: Integer;
  Root: String;
  Free, Total: Int64;
begin
  BestDrive := ExtractFileDrive(ExpandConstant('{sd}'));
  BestFree := -1;
  for I := Ord('C') to Ord('Z') do
  begin
    Root := Chr(I) + ':\';
    if GetDriveTypeW(Root) = 3 then
      if GetSpaceOnDisk64(Root, Free, Total) then
        if Free > BestFree then
        begin
          BestFree := Free;
          BestDrive := Chr(I) + ':';
        end;
  end;
end;

function IsSystemDrive: Boolean;
begin
  Result := CompareText(BestDrive, ExtractFileDrive(ExpandConstant('{sd}'))) = 0;
end;

function FreeText: String;
begin
  if BestFree < 0 then
    Result := BestDrive
  else
    Result := BestDrive + ' (' + IntToStr(BestFree div GB) + ' GB frei)';
end;

function BestInstallDir(Param: String): String;
begin
  if IsSystemDrive then
    Result := ExpandConstant('{localappdata}\Programs\Butchies Video Converter')
  else
    Result := BestDrive + '\Programme\Butchies Video Converter';
end;

function BestVideoDir: String;
begin
  if IsSystemDrive then
    Result := ExpandConstant('{%USERPROFILE}\Videos\Butchies Converter')
  else
    Result := BestDrive + '\Butchies Converter\Videos';
end;

function InitializeSetup: Boolean;
begin
  FindBestDrive;
  Result := True;
end;

procedure InitializeWizard;
begin
  DriveInfo := TNewStaticText.Create(WizardForm);
  DriveInfo.Parent := WizardForm.SelectDirPage;
  DriveInfo.Left := WizardForm.DirEdit.Left;
  DriveInfo.Top := WizardForm.DirEdit.Top + WizardForm.DirEdit.Height + ScaleY(16);
  DriveInfo.Width := WizardForm.DirEdit.Width;
  DriveInfo.AutoSize := False;
  DriveInfo.WordWrap := True;
  DriveInfo.Height := ScaleY(48);
  DriveInfo.Caption := 'Vorschlag: Laufwerk mit dem meisten freien Speicher – ' + FreeText + '.';
  DriveInfo.Font.Style := [fsBold];

  OutPage := CreateInputDirPage(wpSelectDir, 'Ordner für fertige Videos',
    'Wohin sollen die umgewandelten Videos gespeichert werden?',
    'Videos brauchen viel Platz – darum schlägt der Installer das Laufwerk mit dem meisten freien Speicher vor: ' +
    FreeText + '.' + #13#10 + 'Du kannst den Ordner später im Programm jederzeit ändern.',
    False, '');
  OutPage.Add('Fertige Videos:');
  OutPage.Values[0] := BestVideoDir;
end;

function JsonEsc(S: String): String;
begin
  Result := S;
  StringChangeEx(Result, '\', '\\', True);
  StringChangeEx(Result, '"', '\"', True);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    ForceDirectories(OutPage.Values[0]);
    SaveStringToFile(ExpandConstant('{app}\install.json'),
      '{"outdir": "' + JsonEsc(OutPage.Values[0]) + '", "drive": "' + BestDrive + '"}', False);
  end;
end;
