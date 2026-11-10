; Compiled by build_reelle.py with an explicit, pre-scanned StagePath.
#ifndef StagePath
  #error StagePath is required
#endif

[Setup]
AppId={{B3F9D40A-B6C1-4D8C-8A29-E21BB4AE43B3}
AppName=Jade - Demonstration
AppVersion=0.1.0
AppPublisher=Jade
DefaultDirName={localappdata}\Programs\Jade Demo
DefaultGroupName=Jade Demo
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
Compression=lzma2
SolidCompression=yes
UninstallDisplayIcon={app}\Jade.exe
OutputBaseFilename=Installer-Jade

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; Flags: unchecked

[Files]
Source: "{#StagePath}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Jade"; Filename: "{app}\Jade.exe"
Name: "{group}\Desinstaller Jade"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Jade"; Filename: "{app}\Jade.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Jade.exe"; Description: "Lancer Jade"; Flags: nowait postinstall skipifsilent
