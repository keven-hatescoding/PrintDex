"""Persistência de configurações (pastas, API key, idioma, tema) em SQLite.

O banco fica no diretório de dados do SO (ex.: %APPDATA%\\PrintDex). A tabela
`configuracoes` tem sempre uma única linha (id = 1).
"""

import shutil
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from printdex.config import DB_PATH, DEFAULT_THEME, LEGACY_DB_PATH
from printdex.core.calculator import DEFAULT_CURRENCY

# Coluna -> valor padrão. "idioma" vazio significa "ainda não escolhido": na
# primeira execução o app usa o idioma do instalador (ou inglês) e grava.
_COLUMNS = {
    "pasta_origem": "",
    "pasta_destino": "",
    "api_key": "",
    "idioma": "",
    "tema": DEFAULT_THEME,
    "moeda": DEFAULT_CURRENCY,
    # Calculadora: valores que quase não mudam entre um orçamento e outro
    # (guardados como o usuário digitou)
    "calc_preco_kg": "",
    "calc_potencia": "",
    "calc_tarifa": "",
    "calc_valor_maquina": "",
    "calc_vida_util": "",
    "calc_hora_trabalho": "",
}
FIELDS = tuple(_COLUMNS)


class SettingsDB:
    def __init__(self, db_path: Path = DB_PATH,
                 legacy_path: Path | None = LEGACY_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        # Preenchido quando o banco antigo de "data/" foi copiado para cá
        self.migrated_from: Path | None = None
        self._migrate_legacy(legacy_path)
        self._create_table()

    def _migrate_legacy(self, legacy_path: Path | None) -> None:
        """Copia o banco da versão anterior, se ainda não existir um novo.

        Copia em vez de mover: o arquivo antigo fica como backup.
        """
        if legacy_path is None or self.db_path.exists():
            return
        legacy_path = Path(legacy_path)
        if legacy_path.is_file() and legacy_path.resolve() != self.db_path.resolve():
            shutil.copy2(legacy_path, self.db_path)
            self.migrated_from = legacy_path

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """Abre uma conexão por operação (seguro entre threads), faz commit
        em caso de sucesso, rollback em caso de erro e sempre fecha."""
        conn = sqlite3.connect(self.db_path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _create_table(self) -> None:
        # Nomes e padrões vêm de _COLUMNS (constantes), nunca do usuário
        definitions = [f"{name} TEXT NOT NULL DEFAULT '{default}'"
                       for name, default in _COLUMNS.items()]
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS configuracoes ("
                "id INTEGER PRIMARY KEY CHECK (id = 1), "
                + ", ".join(definitions) + ")"
            )
            # Bancos de versões anteriores não têm as colunas novas
            existing = {row[1] for row in conn.execute("PRAGMA table_info(configuracoes)")}
            for name, definition in zip(_COLUMNS, definitions):
                if name not in existing:
                    conn.execute(f"ALTER TABLE configuracoes ADD COLUMN {definition}")
            conn.execute("INSERT OR IGNORE INTO configuracoes (id) VALUES (1)")

    def load(self) -> dict[str, str]:
        """Retorna as configurações salvas (strings vazias se não houver)."""
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT {', '.join(FIELDS)} FROM configuracoes WHERE id = 1"
            ).fetchone()
        return dict(zip(FIELDS, row)) if row else dict.fromkeys(FIELDS, "")

    def save(self, **values: str) -> None:
        """Atualiza um ou mais campos, ex.: save(api_key="...")."""
        invalid = set(values) - set(FIELDS)
        if invalid:
            raise ValueError(f"Campos inválidos: {', '.join(sorted(invalid))}")
        if not values:
            return

        # Os nomes de coluna vêm da whitelist FIELDS; os valores vão como parâmetros
        assignments = ", ".join(f"{field} = ?" for field in values)
        with self._connect() as conn:
            conn.execute(
                f"UPDATE configuracoes SET {assignments} WHERE id = 1",
                tuple(values.values()),
            )
