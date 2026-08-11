; ---------------------------------------------------------------------------
; PyFileShare - Inno Setup 6 script for a standard Windows installer (.exe)
;
; Prerequisites:
;   1. Build the single-file app first:  pyinstaller app.spec
;      -> produces  dist\PyFileShare.exe   (cloudflared embedded inside it)
;   2. Install Inno Setup 6 (https://jrsoftware.org/isinfo.php)
;   3. Compile this script:
;        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
;
; Output:  Output\PyFileShare-Setup-1.0.0.exe
; ---------------------------------------------------------------------------

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif

#define MyAppName "PyFileShare"
#define MyAppPublisher "PyFileShare"
#define MyAppExeName "PyFileShare.exe"
#define MyAppId "{{8F3B1C2E-4D6A-4A1B-9C5E-0A1B2C3D4E5F}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=Output
OutputBaseFilename={#MyAppName}-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequired=lowest
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
; The self-contained app (cloudflared is embedded inside the exe).
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Optional: also drop cloudflared.exe next to the app so it can be updated /
; overridden independently of the main exe. Remove this section if you do
; not ship a standalone cloudflared.exe alongside the installer.
#ifexist "cloudflared.exe"
Source: "cloudflared.exe"; DestDir: "{app}"; Flags: ignoreversion
#endif

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove any config/log the app may have left in the install directory.
Type: files; Name: "{app}\config.json"
Type: files; Name: "{app}\app.log"
