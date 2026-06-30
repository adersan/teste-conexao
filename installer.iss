#define MyAppName "AS Tech - Diagnóstico de Conexão"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "AS Tech Solutions"
#define MyAppExeName "AS-Tech-Diagnostico.exe"

[Setup]
AppId={{8E537173-D523-46E8-9591-7831F68547D2}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\AS Tech Diagnostico
DefaultGroupName=AS Tech
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=release
OutputBaseFilename=AS-Tech-Diagnostico-Setup-{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion=1.0.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=Instalador do diagnóstico de conexão AS Tech

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"; Flags: unchecked

[Files]
Source: ".dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\AS Tech - Diagnóstico de Conexão"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\AS Tech - Diagnóstico de Conexão"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir o diagnóstico agora"; Flags: nowait postinstall skipifsilent
