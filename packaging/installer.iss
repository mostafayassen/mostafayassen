; Inno Setup script for the Task Organizer Windows installer.
;
; Built by CI (.github/workflows/build-windows-installer.yml) after PyInstaller
; produces dist/TaskOrganizer/. To build locally on Windows with Inno Setup 6
; installed, run from the repo root:
;   ISCC.exe packaging\installer.iss
; and the installer will be written to packaging\output\TaskOrganizer-Setup.exe

#define MyAppName "Task Organizer"
#define MyAppVersion "1.0.0"
#define MyAppExeName "TaskOrganizer.exe"

[Setup]
AppId={{B6F1B9A1-6D2E-4C8A-9E2F-6A6C1F6A0A11}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=output
OutputBaseFilename=TaskOrganizer-Setup
Compression=lzma
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"

[Files]
Source: "..\dist\TaskOrganizer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent
