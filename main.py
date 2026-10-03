"""Ponto de entrada do SliceMind DEX."""

import sys

from sliceminddex import single_instance


def main() -> None:
    # Autodiagnóstico do .exe (usado pelo build.ps1); não abre janela
    if len(sys.argv) >= 3 and sys.argv[1] == "--self-test":
        from sliceminddex import selftest
        sys.exit(selftest.run(sys.argv[2]))

    instance = single_instance.acquire()
    if instance is None:
        return  # já estava aberto (talvez na bandeja): a janela dele foi mostrada

    # Importado só aqui: uma segunda instância sai sem carregar a interface
    from sliceminddex.ui.app import SliceMindDexApp

    app = SliceMindDexApp()
    if app.cancelled:
        return  # saiu pelo assistente de primeira execução
    instance.on_activate(app.request_show)
    app.mainloop()


if __name__ == "__main__":
    main()
