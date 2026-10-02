# -*- mode: python ; coding: utf-8 -*-
# Receita do PyInstaller para gerar dist/PrintDex.exe (um único arquivo).
# Use o build.bat (ou build.ps1), que também gera as informações de versão.
# Os temas do CustomTkinter são incluídos pelo hook dele no PyInstaller.

a = Analysis(
    ["main.py"],
    # A janela e o ícone da bandeja carregam o ícone em tempo de execução
    # (config.APP_ICON)
    datas=[("app_icon.ico", ".")],
    # O pystray escolhe o backend do sistema em tempo de execução (importlib):
    # o do Windows precisa ser declarado (o hook do pystray também o inclui)
    hiddenimports=["pystray._win32"],
    # O app não usa estas bibliotecas; excluir deixa o .exe bem menor
    excludes=["numpy", "pandas", "matplotlib", "pytest", "setuptools", "pip"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="PrintDex",
    console=False,  # app de janela: não abre o terminal preto junto
    icon="app_icon.ico",  # ícone do .exe (Explorer, barra de tarefas, atalhos)
    version="build/versao_windows.txt",  # criado pelo build.ps1 com a versão do app
    upx=False,
)
