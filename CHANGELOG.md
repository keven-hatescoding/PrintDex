# Changelog

All notable changes to PrintDex are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

🇧🇷 Versão em português abaixo de cada versão.

## [1.2-BETA] — 2026-10-03 · Library thumbnails

### Added
- 🖼️ **Model thumbnails in the Library.** Files now show the same preview Windows Explorer shows (Windows Shell thumbnails, read through `ctypes` — no new dependencies). When Windows has none, PrintDex uses the image that slicers (Bambu Studio, PrusaSlicer, OrcaSlicer…) embed inside `.3mf` files; otherwise a generic 3D-file icon with the extension (STL / 3MF / OBJ).
- File cards show the thumbnail, the name (up to two lines, long names are shortened in the middle so the end — e.g. `(2).3mf` — stays visible) and the file size.

### Changed
- Thumbnails load in the background and are cached in memory, so the window never waits for them and going back to a folder is instant.
- Large folders open without freezing: cards are drawn in small timed batches and old cards are removed gradually. A 120-file folder used to freeze the window for about 4 seconds.
- The build self-test (`--self-test`) now also checks Windows thumbnail extraction inside the packaged `.exe`.

### Notes
- The 1.2-BETA installer installs over 1.1-BETA and keeps your settings and models.
- `.stl` and `.obj` files only get a real thumbnail if some program registered a Windows thumbnail handler for them (e.g. 3D Viewer or a slicer); otherwise they show the generic icon.

#### 🇧🇷 Em português
- **Novo:** miniaturas dos modelos na Biblioteca — a mesma pré-visualização do Explorer do Windows (via `ctypes`, sem dependências novas). Sem miniatura do Windows, o PrintDex usa a imagem que os fatiadores gravam dentro do `.3mf`; senão, um ícone genérico de arquivo 3D com a extensão. Os cards mostram a miniatura, o nome (até duas linhas, cortando o meio para manter o fim visível) e o tamanho.
- **Alterado:** as miniaturas carregam em segundo plano e ficam em cache; pastas grandes abrem sem congelar a janela (uma pasta com 120 arquivos travava a tela por cerca de 4 segundos). O autodiagnóstico do build também testa as miniaturas dentro do `.exe`.
- **Observação:** o instalador 1.2-BETA instala por cima da 1.1-BETA mantendo configurações e modelos. Arquivos `.stl` e `.obj` só têm miniatura real se algum programa (ex.: Visualizador 3D ou um fatiador) registrou um gerador de miniaturas no Windows; senão mostram o ícone genérico.

## [1.1-BETA] — 2026-10-02 · Hotfix

### Fixed
- **Folder names now follow the app language.** In 1.0BETA every folder created by the AI was in Portuguese for every user. Now:
  - **English** (default, also used when the app is in 简体中文): `Anime & Manga`, `Movies & TV Shows`, `Games`, `Utilities & Tools`, `Decoration`, `Automotive`, `Cosplay & Accessories`, `Others`.
  - **Português (Brasil)**: `Animes e Mangas`, `Filmes e Series`, `Jogos`, `Utilitarios e Ferramentas`, `Decoracao`, `Automotivo`, `Cosplay e Acessorios`, `Outros`.
- The other folders the app creates are localized too: `Unknown` / `Desconhecidos` (when the AI fails) and `General` / `Geral` (models without a franchise). Item types also follow the language (e.g. `Bust` / `Busto`).

### Changed
- The category list of the active language is injected into the Gemini prompt and into the response schema (enum) on every request.
- If the AI answers with a category in the other language (e.g. `Jogos` while the app is in English), it is translated (`Games`) instead of creating a new folder.

### Notes
- Models already organized by 1.0BETA stay in their folders; only new files use the new names.
- The 1.1-BETA installer installs over 1.0BETA and keeps your settings and models.

#### 🇧🇷 Em português
- **Corrigido:** as pastas criadas pela IA ficavam em português para todos os usuários. Agora seguem o idioma do app: inglês por padrão (também com o app em chinês) e português com o app em PT-BR. As pastas de falha (`Unknown`/`Desconhecidos`), de modelo sem franquia (`General`/`Geral`) e os tipos de item (`Bust`/`Busto`) também seguem o idioma.
- **Alterado:** a lista de categorias do idioma ativo vai no prompt e no schema (enum) de cada requisição; uma categoria que venha no outro idioma é traduzida em vez de virar pasta nova.
- **Observação:** os modelos já organizados pela 1.0BETA continuam onde estão. O instalador 1.1-BETA instala por cima da 1.0BETA mantendo configurações e modelos.

## [1.0BETA] — 2026-10-02 · First public beta

### Added
- 🤖 AI auto-organizer (Google Gemini) watching the Downloads folder in real time, with a catch-up scan of files downloaded while the app was closed.
- 🗂️ 8 fixed categories → `PRINTS / Category / Franchise / Item type / Clean name.ext`.
- 🧬 Byte-for-byte deduplication of identical downloads.
- 🧮 3D print calculator with Simple and Advanced modes.
- 📚 Visual library with themed icons and a **Local Files** shortcut.
- 🔔 System tray mode, single-instance protection and first-run setup.
- 🌍 Interface in English, Português (Brasil) and 简体中文; BRL, USD, EUR and CNY currency formatting; light, dark and system themes.
- 📦 Windows installer (Inno Setup) with an embedded self-test in every build.

#### 🇧🇷 Em português
Primeira versão beta pública: organizador automático com IA (Gemini) com varredura inicial, 8 categorias fixas, deduplicação byte a byte, calculadora de impressão 3D (modos Simples e Avançado), biblioteca visual, bandeja do sistema, configuração inicial, três idiomas, quatro moedas, temas e instalador para Windows.

[1.2-BETA]: https://github.com/keven-hatescoding/PrintDex/releases/tag/v1.2-BETA
[1.1-BETA]: https://github.com/keven-hatescoding/PrintDex/tree/v1.1-BETA
[1.0BETA]: https://github.com/keven-hatescoding/PrintDex/releases/tag/v1.0BETA
