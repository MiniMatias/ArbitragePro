/**
 * ArbitragePro NextGen - Client-side Real-Time Engine & Dashboard
 */

document.addEventListener('DOMContentLoaded', () => {
  fetchDashboardData();
  // Polling continuo cada 1800ms para emular streaming de baja latencia
  setInterval(fetchDashboardData, 1800);
});

async function fetchDashboardData() {
  try {
    await Promise.all([
      loadLiveEvents(),
      loadSurebets(),
      loadValueBets(),
      loadCalibration()
    ]);
  } catch (err) {
    console.error("Error al sincronizar datos:", err);
  }
}

async function loadLiveEvents() {
  const res = await fetch('/api/live-events');
  const data = await res.json();
  const container = document.getElementById('events-container');
  const badgeCount = document.getElementById('live-badge-count');

  badgeCount.textContent = `${data.count} Activos`;
  container.innerHTML = '';

  data.events.forEach(ev => {
    const p_ecuabet = ev.odds?.['1X2']?.['ecuabet'] || {};
    const card = document.createElement('div');
    card.className = 'match-item';
    card.innerHTML = `
      <div class="match-item-top">
        <span class="match-league">${ev.league}</span>
        <span class="match-clock">${ev.status === 'LIVE' ? `${ev.minute}'` : 'FINAL'}</span>
      </div>
      <div class="match-teams">
        <span>${ev.home_team} vs ${ev.away_team}</span>
        <span class="match-score mono">${ev.score.home} - ${ev.score.away}</span>
      </div>
      <div class="match-odds-row">
        <div class="odd-pill">
          <span class="odd-label">1 (Local)</span>
          <span class="odd-val mono">${p_ecuabet['1'] || '--'}</span>
        </div>
        <div class="odd-pill">
          <span class="odd-label">X (Empate)</span>
          <span class="odd-val mono">${p_ecuabet['X'] || '--'}</span>
        </div>
        <div class="odd-pill">
          <span class="odd-label">2 (Visita)</span>
          <span class="odd-val mono">${p_ecuabet['2'] || '--'}</span>
        </div>
      </div>
    `;
    container.appendChild(card);
  });
}

async function loadSurebets() {
  const res = await fetch('/api/surebets');
  const data = await res.json();
  const container = document.getElementById('surebets-container');
  const kpiCount = document.getElementById('kpi-surebets-count');

  kpiCount.textContent = data.approved_surebets.length;

  if (data.approved_surebets.length === 0) {
    container.innerHTML = `
      <div style="padding: 16px; text-align: center; color: var(--text-muted); font-size: 0.85rem;">
        Escaneando discrepancias entre Ecuabet, Bet365 y Pinnacle...
      </div>
    `;
    return;
  }

  container.innerHTML = '';
  data.approved_surebets.forEach(arb => {
    const card = document.createElement('div');
    card.className = 'surebet-card';
    card.innerHTML = `
      <div class="surebet-top">
        <div>
          <span class="surebet-title">${arb.event_name}</span>
          <div style="font-size: 0.75rem; color: var(--text-secondary);">${arb.league}</div>
        </div>
        <span class="surebet-roi mono">+${arb.roi_percent}% ROI</span>
      </div>

      <div class="surebet-selections-grid">
        ${arb.selections.map(s => `
          <div class="selection-card">
            <span class="sel-tag">${s.selection}</span>
            <span class="sel-bookmaker">${s.bookmaker.toUpperCase()} @ ${s.odd}</span>
            <span class="sel-stake mono">$${s.stake} USD</span>
          </div>
        `).join('')}
      </div>

      <div style="display: flex; justify-content: space-between; font-size: 0.8rem; color: var(--text-secondary); border-top: 1px solid var(--border-subtle); padding-top: 8px;">
        <span>Inversión Total: <strong class="mono" style="color: var(--text-primary);">$${arb.total_investment} USD</strong></span>
        <span>Beneficio Garantizado: <strong class="mono" style="color: var(--accent-green);">+$${arb.min_guaranteed_profit} USD</strong></span>
      </div>
    `;
    container.appendChild(card);
  });
}

async function loadValueBets() {
  const res = await fetch('/api/value-bets');
  const data = await res.json();
  const container = document.getElementById('valuebets-container');
  const kpiCount = document.getElementById('kpi-valuebets-count');

  kpiCount.textContent = data.count;

  if (data.value_signals.length === 0) {
    container.innerHTML = `
      <div style="padding: 16px; text-align: center; color: var(--text-muted); font-size: 0.85rem;">
        Calculando probabilidades Dixon-Coles y filtrando márgenes sin valor...
      </div>
    `;
    return;
  }

  container.innerHTML = '';
  data.value_signals.forEach(vb => {
    const card = document.createElement('div');
    card.className = 'value-card';
    card.innerHTML = `
      <div class="value-info">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap;">
          <span class="value-match">${vb.match} (${vb.selection})</span>
          <span class="badge-model-ensemble mono">${vb.model_source || 'CatBoost Ensemble'}</span>
        </div>
        <span class="value-meta">Casa: <strong>${vb.bookmaker.toUpperCase()}</strong> | Cuota: <strong class="mono">${vb.market_odd}</strong> (Justa: ${vb.fair_model_odd} | Prob: ${vb.model_probability}%)</span>
      </div>
      <div class="value-stats">
        <div>
          <div style="font-size: 0.72rem; color: var(--text-muted);">Quarter-Kelly Stake</div>
          <div class="mono" style="font-weight: 700; color: var(--accent-green);">$${vb.recommended_stake_usd}</div>
        </div>
        <div class="edge-badge mono">+${vb.edge_percent}% Edge</div>
      </div>
    `;
    container.appendChild(card);
  });
}

async function loadCalibration() {
  const res = await fetch('/api/calibration');
  const data = await res.json();
  const metrics = data.metrics;
  const auditContainer = document.getElementById('audit-container');

  document.getElementById('kpi-brier-score').textContent = metrics.average_brier_score;
  document.getElementById('kpi-brier-status').textContent = `Estado: ${metrics.calibration_status}`;
  document.getElementById('kpi-quarantine-count').textContent = `${metrics.quarantined_teams_count} Equipos`;

  auditContainer.innerHTML = `
    <div class="audit-item">
      <span>Partidos Analizados & Calibrados:</span>
      <strong class="mono">${metrics.settled_matches_count} partidos</strong>
    </div>
    <div class="audit-item">
      <span>Calibración de Probabilidades (Brier Score):</span>
      <strong class="mono" style="color: var(--accent-green);">${metrics.average_brier_score}</strong>
    </div>
    <div class="audit-item">
      <span>Equipos con Penalización de Sesgo Activa:</span>
      <strong class="mono" style="color: var(--accent-amber);">${metrics.quarantined_teams_count} en cuarentena</strong>
    </div>
    <div class="audit-item">
      <span>Último Evento Liquidado:</span>
      <span style="color: var(--text-secondary);">${data.recent_settled_matches[0]?.home_team || 'En espera'} vs ${data.recent_settled_matches[0]?.away_team || ''} (${data.recent_settled_matches[0]?.home_score ?? '-'}:${data.recent_settled_matches[0]?.away_score ?? '-'})</span>
    </div>
  `;
}

async function triggerTestSettlement() {
  try {
    const res = await fetch('/api/settle', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        event_id: 'match_ucl_01',
        home_score: 2,
        away_score: 1
      })
    });
    const result = await res.json();
    alert(`¡Aprendizaje Bayesiano Ejecutado!\n\nResultado: ${result.settlement_result.final_score}\nBrier Score: ${result.settlement_result.brier_score}\n${result.settlement_result.learning_applied}`);
    fetchDashboardData();
  } catch (err) {
    alert("Error al simular liquidación: " + err);
  }
}

async function runHistoricalBacktest() {
  const container = document.getElementById('backtest-container');
  container.innerHTML = `<div style="padding: 10px; color: var(--accent-cyan); font-size: 0.85rem; text-align: center;">Ejecutando simulación cronológica walk-forward...</div>`;
  try {
    const res = await fetch('/api/backtest/run');
    const data = await res.json();
    container.innerHTML = `
      <div class="audit-item">
        <span>Partidos Evaluados:</span>
        <strong class="mono">${data.matches_evaluated}</strong>
      </div>
      <div class="audit-item">
        <span>Operaciones Ejecutadas (Filtros Institucionales):</span>
        <strong class="mono">${data.total_trades} (${data.win_trades} aciertos - ${data.win_rate_percent}%)</strong>
      </div>
      <div class="audit-item">
        <span>Capital Final (Inicio $1,000 USD):</span>
        <strong class="mono" style="color: var(--accent-green);">$${data.final_bankroll_usd} USD (+${data.roi_percent}% ROI)</strong>
      </div>
      <div class="audit-item">
        <span>Máximo Drawdown Controlado:</span>
        <strong class="mono" style="color: var(--accent-amber);">${data.max_drawdown_percent}%</strong>
      </div>
      <div class="audit-item">
        <span>Ratio de Sharpe Anualizado:</span>
        <strong class="mono" style="color: var(--accent-cyan);">${data.sharpe_ratio}</strong>
      </div>
      <div class="audit-item">
        <span>Evolución Brier Score:</span>
        <span class="mono">${data.brier_score_initial_half} &rarr; ${data.brier_score_learned_half}</span>
      </div>
    `;
  } catch (err) {
    container.innerHTML = `<div style="color: var(--accent-rose); padding: 10px;">Error al ejecutar backtest: ${err}</div>`;
  }
}
