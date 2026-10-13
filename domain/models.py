"""
ArbitragePro NextGen - Domain Models
Entidades de dominio y Value Objects inmutables con tipado estricto.
Capa de Dominio: Cero dependencias externas, cero I/O.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import time

@dataclass(frozen=True)
class OutcomeOdds:
    """Cuotas de mercado por resultado (1, X, 2)."""
    home: float
    draw: float
    away: float
    updated_at: float = field(default_factory=time.time)

@dataclass
class TeamRating:
    """Métricas cuantitativas y ratings adaptativos por equipo."""
    team_name: str
    league: str
    attack: float = 1.0
    defense: float = 1.0
    uncertainty: float = 1.0
    consecutive_errors: int = 0
    is_quarantined: bool = False
    matches_played: int = 0
    last_updated: float = field(default_factory=time.time)

@dataclass(frozen=True)
class SurebetSelection:
    """Pata individual de una Surebet calculada."""
    selection: str
    bookmaker: str
    odd: float
    stake: float
    raw_stake: float

@dataclass
class SurebetOpportunity:
    """Oportunidad de arbitraje verificada."""
    event_id: str
    event_name: str
    league: str
    selections: List[SurebetSelection]
    roi_percent: float
    sum_inverse_l: float
    total_investment: float
    min_guaranteed_profit: float
    is_safe: bool = True
    audit_message: str = "Aprobado"
    risk_score: float = 0.0

@dataclass
class ValueBetSignal:
    """Señal predictiva de Machine Learning con ventaja cuantificada."""
    event_id: str
    match: str
    league: str
    minute: int
    score: str
    selection: str
    bookmaker: str
    market_odd: float
    fair_model_odd: float
    model_probability: float
    edge_percent: float
    recommended_stake_usd: float
    brier_confidence: float

@dataclass
class MatchEvent:
    """Evento deportivo en vivo o histórico."""
    event_id: str
    sport: str
    league: str
    home_team: str
    away_team: str
    status: str
    minute: int
    home_score: int
    away_score: int
    odds: Dict[str, Dict[str, float]]
    timestamp: float = field(default_factory=time.time)
