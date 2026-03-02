[Setup]
; NOTE: The value of AppId uniquely identifies this application.
; Do not use the same AppId value in installers for other applications.
; (To generate a new GUID, click Tools | Generate GUID inside the IDE.)
AppId={{D15F6784-A122-4809-BFF8-C7B9F1DE3408}
AppName=Finora
AppVersion=1.0.0
AppPublisher=Finora
AppPublisherURL=https://finora.com
AppSupportURL=https://finora.com
AppUpdatesURL=https://finora.com
DefaultDirName={pf}\Finora
DisableProgramGroupPage=yes
; Uncomment the following line to run in non administrative install mode (install for current user only.)
;PrivilegesRequired=lowest
OutputDir=dist_setup
OutputBaseFilename=Finora_Setup_v1.0.0
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\Finora\Finora.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\Finora\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Finora"; Filename: "{app}\Finora.exe"; IconFilename: "{app}\Finora.exe"
Name: "{autodesktop}\Finora"; Filename: "{app}\Finora.exe"; Tasks: desktopicon; IconFilename: "{app}\Finora.exe"

[Run]
Filename: "{app}\Finora.exe"; Description: "{cm:LaunchProgram,Finora}"; Flags: nowait postinstall skipifsilent
