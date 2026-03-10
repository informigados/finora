#ifndef MyAppName
#define MyAppName "Finora"
#endif

#ifndef MyAppVersion
#define MyAppVersion "1.1.0"
#endif

[Setup]
; NOTE: The value of AppId uniquely identifies this application.
; Do not use the same AppId value in installers for other applications.
; (To generate a new GUID, click Tools | Generate GUID inside the IDE.)

AppId={{D15F6784-A122-4809-BFF8-C7B9F1DE3408}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Finora
AppPublisherURL=https://github.com/informigados/finora/
AppSupportURL=https://github.com/informigados/finora/issues
AppUpdatesURL=https://github.com/informigados/finora/releases
DefaultDirName={autopf}\Finora
DisableProgramGroupPage=yes
SetupIconFile=static\favicon.ico
UninstallDisplayIcon={app}\Finora.exe
; Uncomment the following line to run in non administrative install mode (install for current user only.)
;PrivilegesRequired=lowest
OutputDir=dist_setup
OutputBaseFilename=Finora_Setup_v{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
VersionInfoVersion={#MyAppVersion}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\Finora\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\Finora.exe"; IconFilename: "{app}\Finora.exe"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\Finora.exe"; Tasks: desktopicon; IconFilename: "{app}\Finora.exe"

[Run]
Filename: "{app}\Finora.exe"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
