#ifndef MyAppName
#define MyAppName "Finora"
#endif

#ifndef MyAppVersion
#define MyAppVersion "1.4.0"
#endif

[Setup]
; NOTE: The value of AppId uniquely identifies this application.
; Do not use the same AppId value in installers for other applications.
; (To generate a new GUID, click Tools | Generate GUID inside the IDE.)

AppId={{D15F6784-A122-4809-BFF8-C7B9F1DE3408}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=INformigados
AppPublisherURL=https://github.com/informigados/finora/
AppSupportURL=https://github.com/informigados/finora/issues
AppUpdatesURL=https://github.com/informigados/finora/releases
DefaultDirName={autopf}\Finora
DisableProgramGroupPage=yes
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog commandline
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=static\favicon.ico
UninstallDisplayIcon={app}\Finora.exe
UninstallDisplayName={#MyAppName} {#MyAppVersion}
OutputDir=dist_setup
OutputBaseFilename=Finora_Setup_v{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=yes
VersionInfoVersion={#MyAppVersion}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\Finora\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\Finora.exe"; IconFilename: "{app}\Finora.exe"; IconIndex: 0
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\Finora.exe"; Tasks: desktopicon; IconFilename: "{app}\Finora.exe"; IconIndex: 0

[Run]
Filename: "{app}\Finora.exe"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) then
  begin
    if MsgBox(
      'Deseja remover também todos os dados locais do Finora, incluindo banco de dados, perfis e backups?' + #13#10 + #13#10 +
      'Escolha Não para preservar seus dados para uma futura reinstalação.',
      mbConfirmation,
      MB_YESNO
    ) = IDYES then
      DelTree(ExpandConstant('{localappdata}\Finora'), True, True, True);
  end;
end;
