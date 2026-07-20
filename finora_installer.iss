#ifndef MyAppName
#define MyAppName "Finora"
#endif

#ifndef MyAppVersion
#define MyAppVersion "1.4.2"
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
UninstallDisplayIcon={app}\Finora.ico
UninstallDisplayName={#MyAppName} {#MyAppVersion}
OutputDir=dist_setup
OutputBaseFilename=Finora_Setup_v{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
CloseApplicationsFilter=Finora.exe
RestartApplications=no
ChangesAssociations=yes
VersionInfoVersion={#MyAppVersion}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\Finora\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "static\favicon.ico"; DestDir: "{app}"; DestName: "Finora.ico"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\Finora.exe"; WorkingDir: "{app}"; IconFilename: "{app}\Finora.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\Finora.exe"; WorkingDir: "{app}"; Tasks: desktopicon; IconFilename: "{app}\Finora.ico"

[Run]
Filename: "{app}\Finora.exe"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
procedure StopRunningFinora;
var
  ResultCode: Integer;
begin
  { Restart Manager does not always detect a windowless Waitress process. }
  Exec(
    ExpandConstant('{sys}\taskkill.exe'),
    '/F /T /IM Finora.exe',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopRunningFinora;
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    StopRunningFinora;

  if CurUninstallStep = usPostUninstall then
  begin
    { Remove files left behind by a process that was active when uninstall began. }
    DelTree(ExpandConstant('{app}'), True, True, True);

    if not UninstallSilent then
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
end;
