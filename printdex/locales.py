"""Traduções da interface: inglês (padrão), português do Brasil e chinês.

Uso:
    t("nav.library")                    -> texto no idioma atual
    Msg("log.analyzing", name=arquivo)  -> texto traduzido só na hora de exibir

As threads de trabalho (Watchdog, IA) criam `Msg`, nunca texto pronto: assim
o log pode ser redesenhado inteiro quando o usuário troca o idioma.
"""

import sys

from printdex.config import DEFAULT_LANGUAGE, INSTALLER_APP_ID

# Código -> nome exibido no seletor (cada um no próprio idioma)
LANGUAGES = {
    "en": "English",
    "pt_BR": "Português (Brasil)",
    "zh_CN": "简体中文",
}

# Nome do idioma no setup.iss ([Languages]) -> código do app
_INSTALLER_LANGUAGES = {
    "english": "en",
    "portugues": "pt_BR",
    "chinesesimplified": "zh_CN",
}

STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "app.tagline": "AI-powered 3D print library",
        "nav.dashboard": "Dashboard",
        "nav.library": "Library",
        "nav.settings": "Settings",
        "status.stopped": "Stopped",
        "status.running": "Monitoring",
        "status.stopping": "Stopping…",
        "tray.open": "Open PrintDex",
        "tray.status": "Status: {status}",
        "tray.exit": "Exit",
        "tray.hint": "PrintDex is still running in the tray and keeps watching your downloads. Use Exit in the icon menu to quit.",
        "onb.window_title": "Initial setup",
        "onb.title": "Welcome to PrintDex",
        "onb.subtitle": "Before you start, choose where PrintDex watches for downloads and where it organizes your models.",
        "onb.source": "1. Downloads folder (source)",
        "onb.dest": "2. Library folder (PRINTS)",
        "onb.warning": "STRONGLY RECOMMENDED: KEEP THE APP'S DEFAULT FOLDER TO AVOID ERRORS",
        "onb.finish": "Finish",
        "onb.exit": "Exit PrintDex",
        "onb.must_finish": "Choose the folders and click Finish to continue.",
        "onb.error_source": "Choose a downloads folder that exists.",
        "onb.error_dest": "Destination folder not found: {path}",
        "onb.error_create": "Could not create {path}: {error}",
        "field.pasta_origem": "Source folder",
        "field.pasta_destino": "Destination folder",
        "field.api_key": "Gemini API key",
        "list.sep": ", ",

        "dash.title": "Dashboard",
        "dash.subtitle": "Watch your downloads and let the AI file every new 3D model automatically.",
        "dash.start": "Start Monitoring",
        "dash.stop": "Stop Monitoring",
        "dash.not_set": "Not set — configure it in Settings",
        "dash.stat.organized": "Organized",
        "dash.stat.queue": "In queue",
        "dash.stat.attention": "Unknown / errors",
        "dash.activity": "Activity",
        "dash.clear": "Clear",

        "lib.title": "Library",
        "lib.subtitle": "Browse the models organized in your PRINTS folder.",
        "lib.local_files": "Local Files",
        "lib.back": "Back",
        "lib.refresh": "Refresh",
        "lib.open_here": "Open in Explorer",
        "lib.empty_folder": "This folder is empty.",
        "lib.empty_root": "No models organized yet. Start monitoring on the Dashboard and new downloads will show up here.",
        "lib.no_dest": "The destination folder is not set or could not be found.",
        "lib.go_settings": "Open Settings",
        "lib.items.one": "{n} item",
        "lib.items.other": "{n} items",
        "lib.empty_count": "Empty",

        "nav.calculator": "Calculator",
        "calc.title": "3D Print Calculator",
        "calc.subtitle": "Estimate the cost and the price to charge — results update as you type.",
        "calc.mode.simple": "Simple mode",
        "calc.mode.advanced": "Advanced mode",
        "calc.sec.filament": "Filament",
        "calc.sec.slicer": "Slicer",
        "calc.sec.energy": "Energy",
        "calc.sec.profit": "Profit",
        "calc.sec.material": "Material & time",
        "calc.sec.operation": "Operation",
        "calc.sec.extras": "Extras",
        "calc.f.price_kg": "Filament price ({cur}/kg)",
        "calc.f.weight": "Material used (g)",
        "calc.f.hours": "Print time (h)",
        "calc.f.tariff": "Energy rate ({cur}/kWh)",
        "calc.f.power": "Printer power (W)",
        "calc.f.margin": "Profit margin (%)",
        "calc.f.machine": "Machine price ({cur})",
        "calc.f.lifetime": "Machine lifetime (h)",
        "calc.f.labor_rate": "Manual labor ({cur}/h)",
        "calc.f.labor_hours": "Manual hours spent (h)",
        "calc.f.quantity": "Quantity (units)",
        "calc.f.risk": "Failure risk (%)",
        "calc.r.suggested": "SUGGESTED PRICE",
        "calc.r.for_qty.one": "for {n} unit",
        "calc.r.for_qty.other": "for {n} units",
        "calc.r.material": "Material",
        "calc.r.energy": "Energy",
        "calc.r.total_cost": "Total cost",
        "calc.r.profit": "Profit",
        "calc.r.unit_cost": "Unit cost",
        "calc.r.unit_profit": "Unit profit",
        "calc.r.total_time": "Total time",
        "calc.r.filament_only": "Filament only",
        "calc.r.anatomy": "Cost breakdown (per unit)",
        "calc.r.filament": "Filament",
        "calc.r.machine": "Machine",
        "calc.r.labor": "Labor",
        "calc.r.failures": "Failures",
        "calc.duration": "{h} h {m:02d} min",

        "set.title": "Settings",
        "set.subtitle": "Changes are saved automatically.",
        "set.appearance": "Preferences",
        "set.currency": "Currency",
        "set.language": "Language",
        "set.theme": "Theme",
        "set.theme_hint": "System follows the Windows light/dark setting.",
        "theme.System": "System",
        "theme.Dark": "Dark",
        "theme.Light": "Light",
        "set.folders": "Folders",
        "set.source_hint": "Where your browser saves downloads (for example, Downloads).",
        "set.dest_hint": "The AI builds its folder tree inside a PRINTS subfolder of the folder you choose.",
        "set.browse": "Browse…",
        "set.locked": "Stop monitoring to change the folders.",
        "set.ai": "Artificial intelligence",
        "set.api_hint": "Used to classify file names. It is stored only on this computer.",
        "set.show": "Show",
        "set.hide": "Hide",
        "set.save": "Save",
        "set.about": "About",
        "set.version": "Version",
        "set.model": "AI model",
        "set.data_folder": "App data",

        "log.app_started": "Application started.",
        "log.db_open_error": "Error opening the database: {error}",
        "log.db_migrated": "Settings migrated from {old} to {new}",
        "log.settings_loaded": "Settings loaded.",
        "log.first_run": "First run. App data is stored in: {path}",
        "log.default_dest_error": "Could not create the default destination folder: {error}",
        "log.default_dest_changed": "Default destination folder changed to: {path}",
        "log.old_files_remain": "Files already organized remain in: {path}",
        "log.default_dest_created": "Default destination folder created: {path}",
        "log.dest_not_found": "Error: destination folder not found: {path}",
        "log.create_error": "Error creating {path}: {error}",
        "log.db_unavailable": "Database unavailable; nothing was saved.",
        "log.db_save_error": "Error saving to the database: {error}",
        "log.folder_not_found": "{field} not found: {path} (not saved)",
        "log.folder_saved": "{field} saved: {path}",
        "log.folder_removed": "{field} removed.",
        "log.api_key_unchanged": "The API key has not changed.",
        "log.api_key_saved": "API key saved.",
        "log.api_key_removed": "API key removed.",
        "log.start_missing": "Error: fill in {fields} before starting.",
        "log.source_not_found": "Error: source folder not found: {path}",
        "log.start_error": "Error starting monitoring: {error}",
        "log.monitor_started": "Monitoring started in folder: {path}",
        "log.monitor_stopped": "Monitoring stopped.",
        "log.queue_left.one": "{n} queued file remains in the source folder and will be processed in the next initial scan.",
        "log.queue_left.other": "{n} queued files remain in the source folder and will be processed in the next initial scan.",
        "log.scan_none": "Initial scan: no pending files found in the source folder.",
        "log.scan_found.one": "Initial scan: {n} pending file found in the source folder.",
        "log.scan_found.other": "Initial scan: {n} pending files found in the source folder.",
        "log.rate_hint": "To respect the API limit, up to {n} files will be analyzed per minute.",
        "log.file_detected": "3D file detected: {name}",
        "log.cancelled": "Cancelled: {name} remains in the source folder.",
        "log.analyzing": "Analyzing: {name}...",
        "log.file_vanished": "Error: {name} disappeared from the source folder before it could be moved.",
        "log.move_error": "Error moving {name}: {error}. The file remains in the source folder.",
        "log.unexpected_error": "Unexpected error processing {name}: {error}",
        "log.success": "Success! Moved to: {path}  ({files})",
        "log.duplicate_discarded": "Duplicate discarded: {name}  (identical to {existing})",
        "log.ai_error": "AI error. Moved to {folder}.  ({files} - reason: {reason})",
        "log.scan_error": "Initial scan error: {error}",
        "log.process_error": "Error processing {path}: {error}",
        "log.open_error": "Could not open {path}: {error}",

        "ai.api_error": "the Gemini API returned {code}: {message}",
        "ai.connection": "connection failure: {error}",
        "ai.unexpected": "unexpected error: {error}",
        "ai.empty": "empty response from the model",
        "ai.invalid_json": "invalid JSON: {text}",
        "ai.unexpected_json": "unexpected JSON: {text}",
        "ai.missing_fields": "categoria_principal/tipo_item missing from the JSON: {text}",
    },

    "pt_BR": {
        "app.tagline": "Biblioteca de impressão 3D com IA",
        "nav.dashboard": "Painel",
        "nav.library": "Biblioteca",
        "nav.settings": "Configurações",
        "status.stopped": "Parado",
        "status.running": "Monitorando",
        "status.stopping": "Parando…",
        "tray.open": "Abrir PrintDex",
        "tray.status": "Status: {status}",
        "tray.exit": "Sair",
        "tray.hint": "O PrintDex continua rodando na bandeja e monitorando seus downloads. Use Sair no menu do ícone para encerrar.",
        "onb.window_title": "Configuração inicial",
        "onb.title": "Bem-vindo ao PrintDex",
        "onb.subtitle": "Antes de começar, escolha onde o PrintDex procura os downloads e onde ele organiza os seus modelos.",
        "onb.source": "1. Pasta de downloads (origem)",
        "onb.dest": "2. Pasta da biblioteca (PRINTS)",
        "onb.warning": "ALTAMENTE RECOMENDADO DEIXAR O DIRETÓRIO PADRÃO DO APLICATIVO PARA EVITAR ERROS",
        "onb.finish": "Concluir",
        "onb.exit": "Sair do PrintDex",
        "onb.must_finish": "Escolha as pastas e clique em Concluir para continuar.",
        "onb.error_source": "Escolha uma pasta de downloads que exista.",
        "onb.error_dest": "Pasta de destino não encontrada: {path}",
        "onb.error_create": "Não foi possível criar {path}: {error}",
        "field.pasta_origem": "Pasta de origem",
        "field.pasta_destino": "Pasta de destino",
        "field.api_key": "API Key do Gemini",
        "list.sep": ", ",

        "dash.title": "Painel",
        "dash.subtitle": "Monitore seus downloads e deixe a IA arquivar cada novo modelo 3D automaticamente.",
        "dash.start": "Iniciar Monitoramento",
        "dash.stop": "Parar Monitoramento",
        "dash.not_set": "Não definida — configure em Configurações",
        "dash.stat.organized": "Organizados",
        "dash.stat.queue": "Na fila",
        "dash.stat.attention": "Desconhecidos / erros",
        "dash.activity": "Atividade",
        "dash.clear": "Limpar",

        "lib.title": "Biblioteca",
        "lib.subtitle": "Navegue pelos modelos organizados na sua pasta PRINTS.",
        "lib.local_files": "Arquivos Locais",
        "lib.back": "Voltar",
        "lib.refresh": "Atualizar",
        "lib.open_here": "Abrir no Explorer",
        "lib.empty_folder": "Esta pasta está vazia.",
        "lib.empty_root": "Nenhum modelo organizado ainda. Inicie o monitoramento no Painel e os novos downloads aparecerão aqui.",
        "lib.no_dest": "A pasta de destino não está definida ou não foi encontrada.",
        "lib.go_settings": "Abrir Configurações",
        "lib.items.one": "{n} item",
        "lib.items.other": "{n} itens",
        "lib.empty_count": "Vazia",

        "nav.calculator": "Calculadora",
        "calc.title": "Calculadora de Impressão 3D",
        "calc.subtitle": "Calcule o custo e o preço de venda — os resultados mudam enquanto você digita.",
        "calc.mode.simple": "Modo Simples",
        "calc.mode.advanced": "Modo Avançado",
        "calc.sec.filament": "Filamento",
        "calc.sec.slicer": "Fatiador",
        "calc.sec.energy": "Energia",
        "calc.sec.profit": "Lucro",
        "calc.sec.material": "Material e tempo",
        "calc.sec.operation": "Operação",
        "calc.sec.extras": "Extras",
        "calc.f.price_kg": "Preço do filamento ({cur}/kg)",
        "calc.f.weight": "Quantidade de material (g)",
        "calc.f.hours": "Duração da impressão (h)",
        "calc.f.tariff": "Tarifa de energia ({cur}/kWh)",
        "calc.f.power": "Consumo da impressora (W)",
        "calc.f.margin": "Margem de lucro (%)",
        "calc.f.machine": "Valor da máquina ({cur})",
        "calc.f.lifetime": "Vida útil da máquina (h)",
        "calc.f.labor_rate": "Hora de trabalho manual ({cur}/h)",
        "calc.f.labor_hours": "Horas manuais gastas (h)",
        "calc.f.quantity": "Quantidade (un)",
        "calc.f.risk": "Risco de falha (%)",
        "calc.r.suggested": "PREÇO SUGERIDO",
        "calc.r.for_qty.one": "para {n} unidade",
        "calc.r.for_qty.other": "para {n} unidades",
        "calc.r.material": "Material",
        "calc.r.energy": "Energia",
        "calc.r.total_cost": "Custo total",
        "calc.r.profit": "Lucro",
        "calc.r.unit_cost": "Custo unitário",
        "calc.r.unit_profit": "Lucro unitário",
        "calc.r.total_time": "Tempo total",
        "calc.r.filament_only": "Só filamento",
        "calc.r.anatomy": "Anatomia do custo (por unidade)",
        "calc.r.filament": "Filamento",
        "calc.r.machine": "Máquina",
        "calc.r.labor": "Trabalho",
        "calc.r.failures": "Falhas",
        "calc.duration": "{h} h {m:02d} min",

        "set.title": "Configurações",
        "set.subtitle": "As alterações são salvas automaticamente.",
        "set.appearance": "Preferências",
        "set.currency": "Moeda",
        "set.language": "Idioma",
        "set.theme": "Tema",
        "set.theme_hint": "Sistema segue o modo claro/escuro do Windows.",
        "theme.System": "Sistema",
        "theme.Dark": "Escuro",
        "theme.Light": "Claro",
        "set.folders": "Pastas",
        "set.source_hint": "Onde o navegador salva os downloads (por exemplo, Downloads).",
        "set.dest_hint": "A IA monta a árvore de pastas dentro de uma subpasta PRINTS da pasta escolhida.",
        "set.browse": "Procurar…",
        "set.locked": "Pare o monitoramento para trocar as pastas.",
        "set.ai": "Inteligência artificial",
        "set.api_hint": "Usada para classificar os nomes dos arquivos. Fica salva só neste computador.",
        "set.show": "Mostrar",
        "set.hide": "Ocultar",
        "set.save": "Salvar",
        "set.about": "Sobre",
        "set.version": "Versão",
        "set.model": "Modelo de IA",
        "set.data_folder": "Dados do app",

        "log.app_started": "Aplicativo iniciado.",
        "log.db_open_error": "Erro ao abrir o banco de dados: {error}",
        "log.db_migrated": "Configurações migradas de {old} para {new}",
        "log.settings_loaded": "Configurações carregadas.",
        "log.first_run": "Primeira execução. Dados do app em: {path}",
        "log.default_dest_error": "Não foi possível criar a pasta de destino padrão: {error}",
        "log.default_dest_changed": "Pasta de destino padrão alterada para: {path}",
        "log.old_files_remain": "Os arquivos já organizados continuam em: {path}",
        "log.default_dest_created": "Pasta de destino padrão criada: {path}",
        "log.dest_not_found": "Erro: pasta de destino não encontrada: {path}",
        "log.create_error": "Erro ao criar {path}: {error}",
        "log.db_unavailable": "Banco de dados indisponível; nada foi salvo.",
        "log.db_save_error": "Erro ao salvar no banco de dados: {error}",
        "log.folder_not_found": "{field} não encontrada: {path} (não foi salva)",
        "log.folder_saved": "{field} salva: {path}",
        "log.folder_removed": "{field} removida.",
        "log.api_key_unchanged": "A API Key não mudou.",
        "log.api_key_saved": "API Key salva.",
        "log.api_key_removed": "API Key removida.",
        "log.start_missing": "Erro: preencha {fields} antes de iniciar.",
        "log.source_not_found": "Erro: pasta de origem não encontrada: {path}",
        "log.start_error": "Erro ao iniciar o monitoramento: {error}",
        "log.monitor_started": "Monitoramento iniciado na pasta: {path}",
        "log.monitor_stopped": "Monitoramento parado.",
        "log.queue_left.one": "{n} arquivo da fila continua na pasta de origem e será processado na próxima varredura inicial.",
        "log.queue_left.other": "{n} arquivos da fila continuam na pasta de origem e serão processados na próxima varredura inicial.",
        "log.scan_none": "Varredura inicial: nenhum arquivo pendente encontrado na pasta de origem.",
        "log.scan_found.one": "Varredura inicial: {n} arquivo pendente encontrado na pasta de origem.",
        "log.scan_found.other": "Varredura inicial: {n} arquivos pendentes encontrados na pasta de origem.",
        "log.rate_hint": "Para respeitar o limite da API, serão analisados até {n} arquivos por minuto.",
        "log.file_detected": "Arquivo 3D detectado: {name}",
        "log.cancelled": "Cancelado: {name} continua na pasta de origem.",
        "log.analyzing": "Analisando: {name}...",
        "log.file_vanished": "Erro: {name} sumiu da pasta de origem antes de ser movido.",
        "log.move_error": "Erro ao mover {name}: {error}. O arquivo continua na pasta de origem.",
        "log.unexpected_error": "Erro inesperado ao processar {name}: {error}",
        "log.success": "Sucesso! Movido para: {path}  ({files})",
        "log.duplicate_discarded": "Duplicata descartada: {name}  (igual a {existing})",
        "log.ai_error": "Erro na IA. Movido para {folder}.  ({files} - motivo: {reason})",
        "log.scan_error": "Erro na varredura inicial: {error}",
        "log.process_error": "Erro ao processar {path}: {error}",
        "log.open_error": "Não foi possível abrir {path}: {error}",

        "ai.api_error": "a API do Gemini retornou {code}: {message}",
        "ai.connection": "falha de conexão: {error}",
        "ai.unexpected": "erro inesperado: {error}",
        "ai.empty": "resposta vazia do modelo",
        "ai.invalid_json": "JSON inválido: {text}",
        "ai.unexpected_json": "JSON inesperado: {text}",
        "ai.missing_fields": "categoria_principal/tipo_item ausente no JSON: {text}",
    },

    "zh_CN": {
        "app.tagline": "AI 驱动的 3D 打印模型库",
        "nav.dashboard": "仪表板",
        "nav.library": "模型库",
        "nav.settings": "设置",
        "status.stopped": "已停止",
        "status.running": "监控中",
        "status.stopping": "正在停止…",
        "tray.open": "打开 PrintDex",
        "tray.status": "状态：{status}",
        "tray.exit": "退出",
        "tray.hint": "PrintDex 仍在系统托盘中运行，并继续监控下载文件夹。要退出，请使用图标菜单中的“退出”。",
        "onb.window_title": "初始设置",
        "onb.title": "欢迎使用 PrintDex",
        "onb.subtitle": "开始之前，请选择 PrintDex 监控下载的位置，以及整理模型的位置。",
        "onb.source": "1. 下载文件夹（源）",
        "onb.dest": "2. 模型库文件夹（PRINTS）",
        "onb.warning": "强烈建议保留应用的默认目录，以避免出错",
        "onb.finish": "完成",
        "onb.exit": "退出 PrintDex",
        "onb.must_finish": "请选择文件夹并点击“完成”继续。",
        "onb.error_source": "请选择一个存在的下载文件夹。",
        "onb.error_dest": "找不到目标文件夹：{path}",
        "onb.error_create": "无法创建 {path}：{error}",
        "field.pasta_origem": "源文件夹",
        "field.pasta_destino": "目标文件夹",
        "field.api_key": "Gemini API 密钥",
        "list.sep": "、",

        "dash.title": "仪表板",
        "dash.subtitle": "监控下载文件夹，由 AI 自动归档每个新的 3D 模型。",
        "dash.start": "开始监控",
        "dash.stop": "停止监控",
        "dash.not_set": "未设置 — 请在设置中配置",
        "dash.stat.organized": "已整理",
        "dash.stat.queue": "队列中",
        "dash.stat.attention": "未识别 / 错误",
        "dash.activity": "活动",
        "dash.clear": "清除",

        "lib.title": "模型库",
        "lib.subtitle": "浏览 PRINTS 文件夹中已整理的模型。",
        "lib.local_files": "本地文件",
        "lib.back": "返回",
        "lib.refresh": "刷新",
        "lib.open_here": "在资源管理器中打开",
        "lib.empty_folder": "此文件夹为空。",
        "lib.empty_root": "还没有整理好的模型。在仪表板中开始监控后，新的下载会显示在这里。",
        "lib.no_dest": "目标文件夹未设置或找不到。",
        "lib.go_settings": "打开设置",
        "lib.items.one": "{n} 个项目",
        "lib.items.other": "{n} 个项目",
        "lib.empty_count": "空",

        "nav.calculator": "计算器",
        "calc.title": "3D 打印计算器",
        "calc.subtitle": "估算成本和售价，输入时结果实时更新。",
        "calc.mode.simple": "简单模式",
        "calc.mode.advanced": "高级模式",
        "calc.sec.filament": "耗材",
        "calc.sec.slicer": "切片",
        "calc.sec.energy": "电费",
        "calc.sec.profit": "利润",
        "calc.sec.material": "材料与时间",
        "calc.sec.operation": "运营",
        "calc.sec.extras": "其他",
        "calc.f.price_kg": "耗材价格（{cur}/kg）",
        "calc.f.weight": "材料用量（g）",
        "calc.f.hours": "打印时长（h）",
        "calc.f.tariff": "电价（{cur}/kWh）",
        "calc.f.power": "打印机功率（W）",
        "calc.f.margin": "利润率（%）",
        "calc.f.machine": "机器价格（{cur}）",
        "calc.f.lifetime": "机器寿命（h）",
        "calc.f.labor_rate": "人工费率（{cur}/h）",
        "calc.f.labor_hours": "人工时长（h）",
        "calc.f.quantity": "数量（件）",
        "calc.f.risk": "失败风险（%）",
        "calc.r.suggested": "建议售价",
        "calc.r.for_qty.one": "共 {n} 件",
        "calc.r.for_qty.other": "共 {n} 件",
        "calc.r.material": "材料",
        "calc.r.energy": "电费",
        "calc.r.total_cost": "总成本",
        "calc.r.profit": "利润",
        "calc.r.unit_cost": "单件成本",
        "calc.r.unit_profit": "单件利润",
        "calc.r.total_time": "总时长",
        "calc.r.filament_only": "仅耗材",
        "calc.r.anatomy": "成本构成（单件）",
        "calc.r.filament": "耗材",
        "calc.r.machine": "机器折旧",
        "calc.r.labor": "人工",
        "calc.r.failures": "失败损耗",
        "calc.duration": "{h} 小时 {m:02d} 分钟",

        "set.title": "设置",
        "set.subtitle": "更改会自动保存。",
        "set.appearance": "偏好设置",
        "set.currency": "货币",
        "set.language": "语言",
        "set.theme": "主题",
        "set.theme_hint": "“跟随系统”会使用 Windows 的浅色/深色设置。",
        "theme.System": "跟随系统",
        "theme.Dark": "深色",
        "theme.Light": "浅色",
        "set.folders": "文件夹",
        "set.source_hint": "浏览器保存下载文件的位置（例如“下载”文件夹）。",
        "set.dest_hint": "AI 会在所选文件夹下的 PRINTS 子文件夹中建立目录结构。",
        "set.browse": "浏览…",
        "set.locked": "请先停止监控，再更改文件夹。",
        "set.ai": "人工智能",
        "set.api_hint": "用于对文件名进行分类，仅保存在本机。",
        "set.show": "显示",
        "set.hide": "隐藏",
        "set.save": "保存",
        "set.about": "关于",
        "set.version": "版本",
        "set.model": "AI 模型",
        "set.data_folder": "应用数据",

        "log.app_started": "应用已启动。",
        "log.db_open_error": "打开数据库时出错：{error}",
        "log.db_migrated": "设置已从 {old} 迁移到 {new}",
        "log.settings_loaded": "已加载设置。",
        "log.first_run": "首次运行。应用数据位于：{path}",
        "log.default_dest_error": "无法创建默认目标文件夹：{error}",
        "log.default_dest_changed": "默认目标文件夹已更改为：{path}",
        "log.old_files_remain": "已整理的文件仍保留在：{path}",
        "log.default_dest_created": "已创建默认目标文件夹：{path}",
        "log.dest_not_found": "错误：找不到目标文件夹：{path}",
        "log.create_error": "创建 {path} 时出错：{error}",
        "log.db_unavailable": "数据库不可用，未保存任何内容。",
        "log.db_save_error": "保存到数据库时出错：{error}",
        "log.folder_not_found": "找不到{field}：{path}（未保存）",
        "log.folder_saved": "已保存{field}：{path}",
        "log.folder_removed": "已移除{field}。",
        "log.api_key_unchanged": "API 密钥没有变化。",
        "log.api_key_saved": "API 密钥已保存。",
        "log.api_key_removed": "API 密钥已移除。",
        "log.start_missing": "错误：开始之前请先填写{fields}。",
        "log.source_not_found": "错误：找不到源文件夹：{path}",
        "log.start_error": "启动监控时出错：{error}",
        "log.monitor_started": "已开始监控文件夹：{path}",
        "log.monitor_stopped": "监控已停止。",
        "log.queue_left.one": "队列中的 {n} 个文件仍留在源文件夹中，将在下次初始扫描时处理。",
        "log.queue_left.other": "队列中的 {n} 个文件仍留在源文件夹中，将在下次初始扫描时处理。",
        "log.scan_none": "初始扫描：源文件夹中没有待处理的文件。",
        "log.scan_found.one": "初始扫描：在源文件夹中发现 {n} 个待处理文件。",
        "log.scan_found.other": "初始扫描：在源文件夹中发现 {n} 个待处理文件。",
        "log.rate_hint": "为遵守 API 限制，每分钟最多分析 {n} 个文件。",
        "log.file_detected": "检测到 3D 文件：{name}",
        "log.cancelled": "已取消：{name} 仍留在源文件夹中。",
        "log.analyzing": "正在分析：{name}...",
        "log.file_vanished": "错误：{name} 在移动之前已从源文件夹中消失。",
        "log.move_error": "移动 {name} 时出错：{error}。文件仍留在源文件夹中。",
        "log.unexpected_error": "处理 {name} 时发生意外错误：{error}",
        "log.success": "成功！已移动到：{path}（{files}）",
        "log.duplicate_discarded": "已丢弃重复文件：{name}（与 {existing} 相同）",
        "log.ai_error": "AI 出错。已移动到 {folder}。（{files} - 原因：{reason}）",
        "log.scan_error": "初始扫描出错：{error}",
        "log.process_error": "处理 {path} 时出错：{error}",
        "log.open_error": "无法打开 {path}：{error}",

        "ai.api_error": "Gemini API 返回 {code}：{message}",
        "ai.connection": "连接失败：{error}",
        "ai.unexpected": "意外错误：{error}",
        "ai.empty": "模型返回了空响应",
        "ai.invalid_json": "无效的 JSON：{text}",
        "ai.unexpected_json": "意外的 JSON：{text}",
        "ai.missing_fields": "JSON 中缺少 categoria_principal/tipo_item：{text}",
    },
}

_language = DEFAULT_LANGUAGE


def set_language(code: str) -> None:
    global _language
    _language = code if code in STRINGS else DEFAULT_LANGUAGE


def get_language() -> str:
    return _language


def t(key: str, **params) -> str:
    """Texto da chave no idioma atual (cai para o inglês, e depois para a chave)."""
    text = STRINGS[_language].get(key) or STRINGS[DEFAULT_LANGUAGE].get(key, key)
    if not params:
        return text
    return text.format(**{name: _render(value) for name, value in params.items()})


def tn(key: str, n: int, **params) -> str:
    """Plural: usa "<chave>.one" para 1 e "<chave>.other" para o resto."""
    return t(f"{key}.{'one' if n == 1 else 'other'}", n=n, **params)


def _render(value):
    if isinstance(value, Msg):
        return value.render()
    if isinstance(value, (list, tuple)):  # ex.: lista de campos faltando
        return t("list.sep").join(str(_render(item)) for item in value)
    return value


class Msg:
    """Texto traduzível: chave + parâmetros, traduzido só ao ser exibido.

    `count` escolhe o plural (`tn`); parâmetros também podem ser `Msg`.
    """

    __slots__ = ("key", "count", "params")

    def __init__(self, key: str, count: int | None = None, **params) -> None:
        self.key = key
        self.count = count
        self.params = params

    def render(self) -> str:
        if self.count is not None:
            return tn(self.key, self.count, **self.params)
        return t(self.key, **self.params)

    def __str__(self) -> str:
        return self.render()

    def __repr__(self) -> str:
        return f"Msg({self.key!r}, count={self.count!r}, params={self.params!r})"


def installer_language() -> str | None:
    """Idioma escolhido no instalador, se o app foi instalado por ele.

    O Inno Setup grava a escolha em "Inno Setup: Language", na chave de
    desinstalação do app. Usado só na primeira execução.
    """
    if sys.platform != "win32":
        return None
    import winreg

    key_path = ("SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\"
                f"{INSTALLER_APP_ID}_is1")
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, key_path) as key:
                value, _ = winreg.QueryValueEx(key, "Inno Setup: Language")
        except OSError:
            continue
        return _INSTALLER_LANGUAGES.get(str(value).lower())
    return None
