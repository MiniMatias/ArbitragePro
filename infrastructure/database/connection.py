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
        
        # Pragmas de rendimiento y resiliencia ante cortes y contención concurrente
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode = WAL;")      # Concurrencia alta lectura/escritura
        cursor.execute("PRAGMA busy_timeout = 10000;")     # Esperar hasta 10s ante bloqueos concurrentes
        cursor.execute("PRAGMA synchronous = NORMAL;")     # Integridad con baja latencia I/O
        cursor.execute("PRAGMA foreign_keys = ON;")       # Restricción de integridad referencial
        cursor.close()
        
        return conn

def init_db():
    """Inicializa el esquema de base de datos y los índices B-Tree de rendimiento."""
    conn = DatabaseConnection.get_connection()
    c = conn.cursor()

    # 1. Tabla de Ratings de Equipos (Modelo Predictivo Bayesiano)
    c.execute("""
    CREATE TABLE IF NOT EXISTS team_ratings (
        team_name TEXT PRIMARY KEY,
        league TEXT,
        attack REAL DEFAULT 1.0,
        defense REAL DEFAULT 1.0,
        uncertainty REAL DEFAULT 1.0,
        consecutive_errors INTEGER DEFAULT 0,
        is_quarantined INTEGER DEFAULT 0,
        quarantine_until REAL DEFAULT 0,
        matches_played INTEGER DEFAULT 0,
        last_updated REAL
    )
    """)

    # 2. Historial de Señales (Surebets y Value Bets)
    c.execute("""
    CREATE TABLE IF NOT EXISTS signals_history (
        signal_id TEXT PRIMARY KEY,
        event_id TEXT,
        signal_type TEXT,
        market TEXT,
        details_json TEXT,
        stake_usd REAL,
        expected_roi REAL,
        status TEXT DEFAULT 'PENDING',
        actual_profit_usd REAL DEFAULT 0.0,
        was_correct INTEGER DEFAULT NULL,
        created_at REAL
    )
    """)

    # 3. Historial de Partidos y Liquidación
    c.execute("""
    CREATE TABLE IF NOT EXISTS settled_matches (
        event_id TEXT PRIMARY KEY,
        home_team TEXT,
        away_team TEXT,
        home_score INTEGER,
        away_score INTEGER,
        pred_home_prob REAL,
        pred_draw_prob REAL,
        pred_away_prob REAL,
        brier_score REAL,
        residuals_json TEXT,
        settled_at REAL
    )
    """)

    # 4. Métricas de Calibración Global y PnL
    c.execute("""
    CREATE TABLE IF NOT EXISTS calibration_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL,
        brier_score_avg REAL,
        win_rate REAL,
        total_signals INTEGER,
        total_pnl_usd REAL,
        bankroll_usd REAL
    )
    """)

    # 5. Índices B-Tree de Rendimiento
    c.execute("CREATE INDEX IF NOT EXISTS idx_settled_at ON settled_matches(settled_at DESC);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_team_quarantine ON team_ratings(is_quarantined);")
    c.execute("CREATE INDEX IF NOT EXISTS idx_signals_created ON signals_history(created_at DESC);")

    conn.commit()
    conn.close()

def seed_default_teams():
    """Inserta equipos base de referencia (UCL y LigaPro) si no existen."""
    import time
    conn = DatabaseConnection.get_connection()
    c = conn.cursor()
    default_teams = [
        ("Real Madrid", "UEFA Champions League", 1.45, 0.85, 0.80),
        ("Manchester City", "UEFA Champions League", 1.55, 0.80, 0.75),
        ("Bayern Munich", "UEFA Champions League", 1.40, 0.90, 0.85),
        ("Arsenal", "UEFA Champions League", 1.35, 0.82, 0.80),
        ("Barcelona", "UEFA Champions League", 1.38, 0.92, 0.85),
        ("Inter Milan", "UEFA Champions League", 1.25, 0.78, 0.80),
        ("Liga de Quito", "Ecuador LigaPro", 1.20, 0.95, 0.90),
        ("Independiente del Valle", "Ecuador LigaPro", 1.25, 0.90, 0.85),
        ("Barcelona SC", "Ecuador LigaPro", 1.18, 0.98, 0.90),
        ("Emelec", "Ecuador LigaPro", 1.05, 1.05, 0.95)
    ]
    now = time.time()
    for team, league, att, df, unc in default_teams:
        c.execute("""
        INSERT OR IGNORE INTO team_ratings (team_name, league, attack, defense, uncertainty, last_updated)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (team, league, att, df, unc, now))
    conn.commit()
    conn.close()
