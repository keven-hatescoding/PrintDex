; Receita do Inno Setup para o instalador do PrintDex.
; Gerado pelo build.ps1, que passa /DVersao=1.0.0 (numérica) e /DRelease=1.0BETA
; (nome do lançamento). Também pode ser compilado à mão no Inno Setup depois
; de gerar o dist\PrintDex.exe: nesse caso as duas são lidas do próprio .exe.

#ifndef Versao
  #define Versao GetVersionNumbersString(AddBackslash(SourcePath) + "dist\PrintDex.exe")
#endif
#ifndef Release
  #define Release GetStringFileInfo(AddBackslash(SourcePath) + "dist\PrintDex.exe", "ProductVersion")
#endif
#define Nome "PrintDex"
#define Executavel "PrintDex.exe"

[Setup]
; Identificador fixo do app: não mude, é o que faz uma versão nova substituir a anterior
AppId={{8C88A66D-4411-41A6-93BF-463A05AA3E69}
AppName={#Nome}
; Nome do lançamento em "Aplicativos instalados"; a versão numérica vai nas
; propriedades do instalador
AppVersion={#Release}
AppVerName={#Nome} {#Release}
AppPublisher={#Nome}
VersionInfoVersion={#Versao}
VersionInfoProductTextVersion={#Release}
; Administrador só durante a instalação (para gravar em Program Files e liberar
; a pasta PRINTS). Depois disso o PrintDex roda como usuário comum.
PrivilegesRequired=admin
; Caminho fixo: o app procura a PRINTS exatamente aqui (DEFAULT_DEST_DIR em printdex\config.py)
DefaultDirName={commonpf32}\{#Nome}
DisableDirPage=yes
DefaultGroupName={#Nome}
DisableProgramGroupPage=yes
; O Python 3.14 empacotado no .exe exige Windows 10 ou mais novo: em versões
; antigas o instalador avisa e não instala, em vez de deixar um app que não abre
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Ícone do instalador e do desinstalador
SetupIconFile=app_icon.ico
UninstallDisplayIcon={app}\{#Executavel}
UninstallDisplayName={#Nome}
OutputDir=dist
OutputBaseFilename=PrintDex-{#Release}-INSTALL
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Fecha o app aberto antes de atualizar
CloseApplications=yes

[Languages]
; Os mesmos idiomas do app (printdex\locales.py). Na primeira execução o app
; abre no idioma escolhido aqui (lido de "Inno Setup: Language" no registro).
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "portugues"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"
; O chinês simplificado é tradução oficial do Inno Setup, mas não vem em toda
; instalação do compilador: usa a dele ou a cópia em installer\
#if FileExists(AddBackslash(CompilerPath) + "Languages\ChineseSimplified.isl")
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
#elif FileExists(AddBackslash(SourcePath) + "installer\ChineseSimplified.isl")
Name: "chinesesimplified"; MessagesFile: "installer\ChineseSimplified.isl"
#else
  #pragma warning "ChineseSimplified.isl não encontrado: instalador gerado sem chinês. Coloque o arquivo em installer\ para incluí-lo."
#endif

[Tasks]
Name: "atalhodesktop"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Arquivo único do PyInstaller: o CustomTkinter (temas e fontes) já vai dentro dele
Source: "dist\{#Executavel}"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
; Onde o PrintDex organiza os modelos. users-modify libera criar, alterar e
; apagar arquivos nesta pasta e em todas as subpastas para os usuários do PC:
; o app, os fatiadores e o Explorer gravam ali sem administrador. Só a PRINTS
; fica liberada; o PrintDex.exe continua protegido contra alterações.
; Ao desinstalar, a PRINTS só é removida se estiver vazia: os modelos ficam.
Name: "{app}\PRINTS"; Permissions: users-modify

[Icons]
; Os atalhos usam o ícone embutido no PrintDex.exe (o app_icon.ico, posto lá
; pelo PyInstaller): um arquivo só, sempre igual ao do programa
Name: "{autoprograms}\{#Nome}"; Filename: "{app}\{#Executavel}"; IconFilename: "{app}\{#Executavel}"
Name: "{autodesktop}\{#Nome}"; Filename: "{app}\{#Executavel}"; IconFilename: "{app}\{#Executavel}"; Tasks: atalhodesktop

[Run]
; Abre como o usuário comum, não com o administrador da instalação
Filename: "{app}\{#Executavel}"; Description: "{cm:LaunchProgram,{#Nome}}"; Flags: nowait postinstall skipifsilent runasoriginaluser

; As configurações (pastas e API Key) ficam em %APPDATA%\PrintDex e NÃO são apagadas ao desinstalar.
