"""Utilitarios de conexao com SQL Server via mssql-python."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from mssql_python import connect

from app.config import Settings


@contextmanager
def open_connection(settings: Settings) -> Iterator[object]:
    """Abre e fecha a conexao com o SQL Server."""

    connection = connect(settings.sql_connection_string)
    try:
        yield connection
    finally:
        connection.close()
