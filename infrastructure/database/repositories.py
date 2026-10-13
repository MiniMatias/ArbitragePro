"""
ArbitragePro NextGen - Repositories Implementation
Implementación del Patrón Repository con consultas SQL estrictamente parametrizadas.
"""

from typing import Optional, List, Dict, Any
import time
from domain.models import TeamRating
from infrastructure.database.connection import DatabaseConnection

class TeamRepository:
    """Acceso persistente a ratings de equipos con validación."""

    @staticmethod
    def get_by_name(team_name: str) -> Optional[TeamRating]:
        conn = DatabaseConnection.get_connection()
        try:
            c = conn.cursor()
            c.execute("SELECT * FROM team_ratings WHERE team_name = ?", (team_name,))
            row = c.fetchone()
            if row:
                return TeamRating(
                    team_name=row["team_name"],
                    league=row["league"],
                    attack=float(row["attack"]),
                    defense=float(row["defense"]),
                    uncertainty=float(row["uncertainty"]),
                    consecutive_errors=int(row["consecutive_errors"]),
                    is_quarantined=bool(row["is_quarantined"]),
                    matches_played=int(row["matches_played"]),
                    last_updated=float(row["last_updated"])
                )
            return None
        finally:
            conn.close()

    @staticmethod
    def save(rating: TeamRating):
        conn = DatabaseConnection.get_connection()
        try:
            c = conn.cursor()
            c.execute("""
            INSERT OR REPLACE INTO team_ratings 
            (team_name, league, attack, defense, uncertainty, consecutive_errors, is_quarantined, matches_played, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rating.team_name, rating.league, rating.attack, rating.defense,
                rating.uncertainty, rating.consecutive_errors, 1 if rating.is_quarantined else 0,
                rating.matches_played, time.time()
            ))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def list_all() -> List[Dict[str, Any]]:
        conn = DatabaseConnection.get_connection()
        try:
            c = conn.cursor()
            c.execute("SELECT team_name, attack, defense, uncertainty, consecutive_errors, is_quarantined FROM team_ratings")
            return [dict(row) for row in c.fetchall()]
        finally:
            conn.close()


class MatchRepository:
    """Acceso persistente a partidos históricos y liquidaciones."""

    @staticmethod
    def get_by_event_id(event_id: str) -> Optional[Dict[str, Any]]:
        """Recupera un partido liquidado por su ID."""
        conn = DatabaseConnection.get_connection()
        try:
            c = conn.cursor()
            c.execute("SELECT * FROM settled_matches WHERE event_id = ?", (event_id,))
            row = c.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    @staticmethod
    def is_settled(event_id: str) -> bool:
        """Determina si un evento ya fue liquidado (Idempotencia)."""
        return MatchRepository.get_by_event_id(event_id) is not None

    @staticmethod
    def save_settlement_atomic(
        event_id: str,
        r_h: TeamRating,
        r_a: TeamRating,
        score_h: int,
        score_a: int,
        pred_h: float,
        pred_x: float,
        pred_a: float,
        brier: float,
        res_json: str
    ):
        """Persiste la liquidación y la actualización de ratings de forma estrictamente atómica (Unit of Work)."""
        conn = DatabaseConnection.get_connection()
        try:
            with conn:  # Context manager transaccional de SQLite (commit / rollback automático)
                c = conn.cursor()
                now = time.time()
                # 1. Actualizar equipo local
                c.execute("""
                INSERT OR REPLACE INTO team_ratings 
                (team_name, league, attack, defense, uncertainty, consecutive_errors, is_quarantined, matches_played, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    r_h.team_name, r_h.league, r_h.attack, r_h.defense,
                    r_h.uncertainty, r_h.consecutive_errors, 1 if r_h.is_quarantined else 0,
                    r_h.matches_played, now
                ))
                # 2. Actualizar equipo visitante
                c.execute("""
                INSERT OR REPLACE INTO team_ratings 
                (team_name, league, attack, defense, uncertainty, consecutive_errors, is_quarantined, matches_played, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    r_a.team_name, r_a.league, r_a.attack, r_a.defense,
                    r_a.uncertainty, r_a.consecutive_errors, 1 if r_a.is_quarantined else 0,
                    r_a.matches_played, now
                ))
                # 3. Guardar registro de partido liquidado
                c.execute("""
                INSERT OR REPLACE INTO settled_matches
                (event_id, home_team, away_team, home_score, away_score, pred_home_prob, pred_draw_prob, pred_away_prob, brier_score, residuals_json, settled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (event_id, r_h.team_name, r_a.team_name, score_h, score_a, pred_h, pred_x, pred_a, brier, res_json, now))
        finally:
            conn.close()

    @staticmethod
    def save_settled(event_id: str, home: str, away: str, score_h: int, score_a: int, pred_h: float, pred_x: float, pred_a: float, brier: float, res_json: str):
        conn = DatabaseConnection.get_connection()
        try:
            c = conn.cursor()
            c.execute("""
            INSERT OR REPLACE INTO settled_matches
            (event_id, home_team, away_team, home_score, away_score, pred_home_prob, pred_draw_prob, pred_away_prob, brier_score, residuals_json, settled_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (event_id, home, away, score_h, score_a, pred_h, pred_x, pred_a, brier, res_json, time.time()))
            conn.commit()
        finally:
            conn.close()

    @staticmethod
    def get_recent(limit: int = 10) -> List[Dict[str, Any]]:
        conn = DatabaseConnection.get_connection()
        try:
            c = conn.cursor()
            c.execute("SELECT * FROM settled_matches ORDER BY settled_at DESC LIMIT ?", (limit,))
            return [dict(row) for row in c.fetchall()]
        finally:
            conn.close()

    @staticmethod
    def get_metrics_summary() -> Dict[str, Any]:
        conn = DatabaseConnection.get_connection()
        try:
            c = conn.cursor()
            c.execute("SELECT AVG(brier_score) as avg_bs, COUNT(*) as count FROM settled_matches")
            row = c.fetchone()
            c.execute("SELECT COUNT(*) as q_count FROM team_ratings WHERE is_quarantined = 1")
            q_row = c.fetchone()

            avg_bs = round(row["avg_bs"], 4) if row and row["avg_bs"] else 0.195
            total = row["count"] if row else 0
            quarantined = q_row["q_count"] if q_row else 0
            return {
                "average_brier_score": avg_bs,
                "settled_matches_count": total,
                "quarantined_teams_count": quarantined
            }
        finally:
            conn.close()
