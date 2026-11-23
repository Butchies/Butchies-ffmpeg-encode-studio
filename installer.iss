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
WizardSizePercent=120
DisableWelcomePage=no
WizardImageFile=installer-side-100.bmp,installer-side-150.bmp,installer-side.bmp
WizardSmallImageFile=installer-small-100.bmp,installer-small-150.bmp,installer-small.bmp
Compression=lzma2/ultra64
SolidCompression=yes
CloseApplications=force
RestartApplications=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0

[Languages]
Name: "de"; MessagesFile: "compiler:Languages\German.isl"

[Messages]
de.WelcomeLabel1=Willkommen beim ffmpeg_encode Studio AI
de.WelcomeLabel2=Aus deinem Song und einem Bild werden fertige YouTube-Videos und Shorts – mit Visualizer, Bild-Effekten und neu: KI-Video, das dein Bild wirklich bewegt.%n%nAlles läuft offline auf deinem PC.%n%nVersion {#AppVersion}
de.FinishedHeadingLabel=Fertig – viel Spaß beim Erstellen!
de.FinishedLabel=ffmpeg_encode Studio AI ist installiert.%n%nTipp: Die Kachel „KI-Video“ öffnet ein eigenes Fenster – ideal für den 2. Monitor. Das KI-Video-Paket (ca. 8 GB) lädst du dort einmalig auf Wunsch.
de.ReadyLabel1=Alles bereit – gleich geht's los.

[Tasks]
Name: "desktopicon"; Description: "Verknüpfung auf dem Desktop anlegen"; GroupDescription: "Zusätzlich:"

[Files]
Source: "dist\ffmpeg_encode_Studio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "ffmpeg\bin\*"; DestDir: "{app}\ffmpeg\bin"; Flags: ignoreversion recursesubdirs
Source: "ffmpeg\LICENSE.txt"; DestDir: "{app}\ffmpeg"; Flags: ignoreversion skipifsourcedoesntexist
Source: "LIESMICH.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: NeedsWebView2
Source: "installer-head.bmp"; Flags: dontcopy
Source: "installer-features.bmp"; Flags: dontcopy
Source: "installer-slide1.bmp"; Flags: dontcopy
Source: "installer-slide2.bmp"; Flags: dontcopy
Source: "installer-slide3.bmp"; Flags: dontcopy
Source: "installer-slide4.bmp"; Flags: dontcopy

[Icons]
Name: "{autoprograms}\ffmpeg_encode Studio"; Filename: "{app}\ffmpeg_encode_Studio.exe"; Comment: "MP3 + Bild zu YouTube-Videos machen"
Name: "{autodesktop}\ffmpeg_encode Studio"; Filename: "{app}\ffmpeg_encode_Studio.exe"; Comment: "MP3 + Bild zu YouTube-Videos machen"; Tasks: desktopicon

[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Microsoft WebView2 wird eingerichtet …"; Flags: waituntilterminated; Check: NeedsWebView2
Filename: "{app}\ffmpeg_encode_Studio.exe"; Description: "ffmpeg_encode Studio jetzt starten"; Flags: nowait postinstall skipifsilent
Filename: "{app}\ffmpeg_encode_Studio.exe"; Flags: nowait; Check: WizardSilent

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

var
  FeatPage: TWizardPage;
  Slide: TBitmapImage;
  SlideNo: Integer;

procedure ShowSlide(N: Integer);
begin
  if (N < 1) or (N > 4) or (N = SlideNo) then
    exit;
  SlideNo := N;
  Slide.Bitmap.LoadFromFile(ExpandConstant('{tmp}\installer-slide' + IntToStr(N) + '.bmp'));
end;

procedure InitializeWizard;
var
  Head, Img: TBitmapImage;
  I: Integer;
begin
  ExtractTemporaryFile('installer-head.bmp');
  ExtractTemporaryFile('installer-features.bmp');
  for I := 1 to 4 do
    ExtractTemporaryFile('installer-slide' + IntToStr(I) + '.bmp');

  { Kopfleiste im Gold-Look des Programms }
  WizardForm.MainPanel.Color := $050A0D;
  Head := TBitmapImage.Create(WizardForm);
  Head.Parent := WizardForm.MainPanel;
  Head.Left := 0;
  Head.Top := 0;
  Head.Width := WizardForm.MainPanel.Width;
  Head.Height := WizardForm.MainPanel.Height;
  Head.Stretch := True;
  Head.Bitmap.LoadFromFile(ExpandConstant('{tmp}\installer-head.bmp'));
  WizardForm.PageNameLabel.Font.Color := $8ADFFF;
  WizardForm.PageNameLabel.Font.Size := WizardForm.PageNameLabel.Font.Size + 2;
  WizardForm.PageDescriptionLabel.Font.Color := $91B9C9;
  WizardForm.WizardSmallBitmapImage.BringToFront;
  WizardForm.PageNameLabel.BringToFront;
  WizardForm.PageDescriptionLabel.BringToFront;
  WizardForm.WelcomeLabel1.Font.Color := $0E7AB5;
  WizardForm.WelcomeLabel1.Font.Size := WizardForm.WelcomeLabel1.Font.Size + 4;
  WizardForm.FinishedHeadingLabel.Font.Color := $0E7AB5;
  WizardForm.FinishedHeadingLabel.Font.Size := WizardForm.FinishedHeadingLabel.Font.Size + 2;

  { Seite „Das kann dein Studio“ mit Bildern der Funktionen }
  FeatPage := CreateCustomPage(wpWelcome, 'Das kann dein Studio', 'Song + Bild → YouTube – jetzt mit KI-Video, KI-Upscaler und mehr');
  Img := TBitmapImage.Create(FeatPage);
  Img.Parent := FeatPage.Surface;
  Img.Left := 0;
  Img.Top := 0;
  Img.Width := FeatPage.SurfaceWidth;
  Img.Height := FeatPage.SurfaceHeight;
  Img.Stretch := True;
  Img.Bitmap.LoadFromFile(ExpandConstant('{tmp}\installer-features.bmp'));

  { Wechselnde Bilder während der Installation }
  Slide := TBitmapImage.Create(WizardForm);
  Slide.Parent := WizardForm.InstallingPage;
  Slide.Left := 0;
  Slide.Width := WizardForm.InstallingPage.Width;
  Slide.Height := Slide.Width * 33 div 100;
  Slide.Top := WizardForm.InstallingPage.Height - Slide.Height;
  Slide.Stretch := True;
  SlideNo := 0;
  ShowSlide(1);
end;

procedure CurInstallProgressChanged(CurProgress, MaxProgress: Integer);
begin
  if MaxProgress > 0 then
    ShowSlide(1 + (CurProgress * 4) div (MaxProgress + 1));
end;
