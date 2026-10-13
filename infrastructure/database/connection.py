"""
ArbitragePro NextGen - Database Infrastructure Layer
Gestor de conexiones SQLite con modo WAL (Write-Ahead Logging) y mitigación de bloqueos.
"""

import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "arbitrage_pro.db")

class DatabaseConnection:
    """Proveedor de conexiones de base de datos thread-safe con pragmas de robustez."""

    @staticmethod
    def get_connection() -> sqlite3.Connection:
        conn = sqlite3.connect(DB_FILE, timeout=10.0)
        conn.row_factory = sqlite3.Row
        
        # Pragmas de rendimiento y resiliencia ante cortes
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode = WAL;")      # Concurrencia alta lectura/escritura
        cursor.execute("PRAGMA synchronous = NORMAL;")     # Integridad con baja latencia I/O
        cursor.execute("PRAGMA foreign_keys = ON;")       # Restricción de integridad referencial
        cursor.close()
        
        return conn
