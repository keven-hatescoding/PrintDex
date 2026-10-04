# Gera o SliceMind DEX em dist\:
#   SliceMindDex.exe             o programa (roda como usuário comum)
#   SliceMindDEX-Installer.exe   instala em C:\Program Files (x86)\SliceMind DEX
#                                e cria a pasta PRINTS com permissão de escrita
#
# Precisa de: Python com as dependências (pip install -r requirements.txt),
#             o PyInstaller (pip install pyinstaller) e, para o instalador,
#             o Inno Setup 6 (winget install JRSoftware.InnoSetup).
# Uso: clique duas vezes no build.bat, ou rode:  powershell -ExecutionPolicy Bypass -File build.ps1

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

# O dist\SliceMindDex.exe não pode ser substituído enquanto estiver aberto.
# O SliceMind DEX instalado (Program Files) é outro arquivo: pode ficar aberto.
$distExe = Join-Path $PSScriptRoot "dist\SliceMindDex.exe"
if (Get-Process -Name "SliceMindDex" -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $distExe }) {
    throw "Feche o dist\SliceMindDex.exe antes de gerar o executável."
}

# A versão vem do próprio app (sliceminddex\__init__.py): __version__ é a numérica
# (propriedades do .exe) e RELEASE é o nome do lançamento (instalador, Windows)
$versao = (Select-String -Path "sliceminddex\__init__.py" -Pattern '^__version__ = "(.+)"').Matches[0].Groups[1].Value
$release = (Select-String -Path "sliceminddex\__init__.py" -Pattern '^RELEASE = "(.+)"').Matches[0].Groups[1].Value
$partes = ($versao.Split(".") + @("0", "0", "0"))[0..3] -join ", "
Write-Host "Gerando o SliceMind DEX $release ($versao)..." -ForegroundColor Cyan

# 1. Informações que aparecem em Propriedades > Detalhes do .exe
New-Item -ItemType Directory -Force "build" | Out-Null
@"
VSVersionInfo(
  ffi=FixedFileInfo(filevers=($partes), prodvers=($partes)),
  kids=[
    StringFileInfo([StringTable('041604B0', [
      StringStruct('ProductName', 'SliceMind DEX'),
      StringStruct('FileDescription', 'SliceMind DEX - organizador de arquivos 3D'),
      StringStruct('FileVersion', '$versao'),
      StringStruct('ProductVersion', '$release'),
      StringStruct('OriginalFilename', 'SliceMindDex.exe')])]),
    VarFileInfo([VarStruct('Translation', [1046, 1200])])
  ]
)
"@ | Out-File -Encoding utf8 "build\versao_windows.txt"

# 2. O executável (um único arquivo)
python -m PyInstaller --noconfirm --clean SliceMindDex.spec
if ($LASTEXITCODE -ne 0) { throw "O PyInstaller falhou." }

# 3. Autodiagnóstico: o próprio .exe confere se nada ficou de fora
#    (bibliotecas, ícone, temas, certificados HTTPS, backends do Windows)
$relatorio = Join-Path $PSScriptRoot "build\autodiagnostico.txt"
$teste = Start-Process -FilePath "dist\SliceMindDex.exe" -ArgumentList "--self-test", "`"$relatorio`"" -Wait -PassThru
Get-Content $relatorio -Encoding UTF8 | Where-Object { $_ -notmatch "^\s{8}" } | ForEach-Object { Write-Host "  $_" }
if ($teste.ExitCode -ne 0) { throw "O autodiagnóstico do .exe falhou (detalhes em build\autodiagnostico.txt)." }

# 4. O instalador (Inno Setup), se estiver instalado
$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) {
    Write-Host "Pronto: dist\SliceMindDex.exe" -ForegroundColor Green
    Write-Host "Inno Setup 6 não encontrado, então o instalador não foi gerado." -ForegroundColor Yellow
    Write-Host "Instale com 'winget install JRSoftware.InnoSetup' e rode de novo, ou abra o setup.iss no Inno Setup e compile." -ForegroundColor Yellow
    exit 0
}
& $iscc "/DVersao=$versao" "/DRelease=$release" "setup.iss"
if ($LASTEXITCODE -ne 0) { throw "O Inno Setup falhou." }

Write-Host "Pronto: dist\SliceMindDex.exe e dist\SliceMindDEX-Installer.exe" -ForegroundColor Green
