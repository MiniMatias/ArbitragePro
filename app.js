/**
 * ArbitragePro - Quantitative Arbitrage & Surebet Engine
 * Core Logic & State Management
 */

// Available bookmaker list (Focused on Ecuador & Global Liquidity)
const BOOKMAKERS = [
  { id: 'ecuabet', name: 'Ecuabet (Ecuador)' },
  { id: 'bet365', name: 'Bet365 (Global)' },
  { id: '1xbet', name: '1xBet' },
  { id: 'betcris', name: 'Betcris' },
  { id: 'pinnacle', name: 'Pinnacle (Sharp)' },
  { id: 'otro', name: 'Otra Casa' }
];

// Default configurations
const DEFAULT_CONFIGS = {
  2: [
    { label: 'Opción 1 (ej. Más 2.5 / Local)', odd: 2.15, bookmaker: 'ecuabet' },
    { label: 'Opción 2 (ej. Menos 2.5 / Visitante)', odd: 2.05, bookmaker: 'bet365' }
  ],
  3: [
    { label: 'Local (1)', odd: 3.10, bookmaker: 'ecuabet' },
    { label: 'Empate (X)', odd: 3.40, bookmaker: 'bet365' },
    { label: 'Visitante (2)', odd: 2.85, bookmaker: '1xbet' }
  ]
};

// Application State
let currentMode = 2; // 2 or 3 ways
let currentOutcomes = JSON.parse(JSON.stringify(DEFAULT_CONFIGS[2]));
let historyRecords = [];

// Initialize App
document.addEventListener('DOMContentLoaded', () => {
  cargarHistorialLocal();
  renderOutcomesUI();
  calcular();
});

/**
 * Change market mode between 2-ways and 3-ways
 */
function setMarketMode(mode) {
  if (currentMode === mode) return;
  currentMode = mode;

  // Toggle Tab active classes
  document.getElementById('tab-2ways').classList.toggle('active', mode === 2);
  document.getElementById('tab-3ways').classList.toggle('active', mode === 3);

  // Load default template for chosen mode
  currentOutcomes = JSON.parse(JSON.stringify(DEFAULT_CONFIGS[mode]));
  renderOutcomesUI();
  calcular();
}

/**
 * Render input cards for odds dynamically
 */
function renderOutcomesUI() {
  const container = document.getElementById('odds-container');
  container.innerHTML = '';

  currentOutcomes.forEach((outcome, idx) => {
    const card = document.createElement('div');
    card.className = 'odd-card';
    card.id = `odd-card-${idx}`;

    const bookmakerOptions = BOOKMAKERS.map(b => 
      `<option value="${b.id}" ${b.id === outcome.bookmaker ? 'selected' : ''}>${b.name}</option>`
    ).join('');

    card.innerHTML = `
      <div class="odd-card-header">
        <span class="outcome-tag">${outcome.label}</span>
        <select class="bookmaker-select" id="bm-${idx}" onchange="actualizarBookmaker(${idx}, this.value)">
          ${bookmakerOptions}
        </select>
      </div>

      <div class="odd-inputs-row">
        <div class="input-box">
          <label for="odd-${idx}">Cuota Decimal</label>
          <input 
            type="number" 
            id="odd-${idx}" 
            value="${outcome.odd}" 
            step="0.01" 
            min="1.01" 
            oninput="actualizarCuota(${idx}, this.value)"
          >
        </div>
        <div class="input-box">
          <label>Prob. Implícita</label>
          <input 
            type="text" 
            id="prob-${idx}" 
            value="0.0%" 
            readonly 
            style="color: var(--text-dim);"
          >
        </div>
      </div>

      <div class="stake-output-box">
        <span class="stake-label">Apuesta Sugerida:</span>
        <span class="stake-amount mono" id="stake-display-${idx}">$0.00</span>
      </div>
    `;
    container.appendChild(card);
  });
}

function actualizarCuota(idx, val) {
  const num = parseFloat(val);
  currentOutcomes[idx].odd = isNaN(num) || num <= 1 ? 1.01 : num;
  calcular();
}

function actualizarBookmaker(idx, val) {
  currentOutcomes[idx].bookmaker = val;
}

/**
 * Main calculation engine
 */
function calcular() {
  const totalInvestmentInput = document.getElementById('total-investment');
  const totalInvestment = Math.max(1, parseFloat(totalInvestmentInput.value) || 0);
  const isRoundingActive = document.getElementById('rounding-toggle').checked;

  const odds = currentOutcomes.map(o => o.odd);

  // 1. Calculate Sum of Inverse Odds (Market Margin L)
  let sumInverseOdds = 0;
  odds.forEach((odd, idx) => {
    const prob = (1 / odd);
    sumInverseOdds += prob;
    // Update individual implied probability display
    const probEl = document.getElementById(`prob-${idx}`);
    if (probEl) probEl.value = (prob * 100).toFixed(1) + '%';
  });

  const isSurebet = sumInverseOdds < 1.0;
  const netMarginPercent = isSurebet 
    ? ((1 / sumInverseOdds) - 1) * 100 
    : -((sumInverseOdds - 1) * 100);

  // 2. Update Status Indicators
  const indicatorBadge = document.getElementById('indicator-badge');
  const marketSumEl = document.getElementById('market-sum');
  const profitPercentageEl = document.getElementById('profit-percentage');

  marketSumEl.textContent = sumInverseOdds.toFixed(4);

  if (isSurebet) {
    indicatorBadge.className = 'badge-success';
    indicatorBadge.textContent = `¡SUREBET ENCONTRADA!`;
    profitPercentageEl.className = 'val-number mono highlight';
    profitPercentageEl.textContent = `+${netMarginPercent.toFixed(2)}%`;
  } else {
    indicatorBadge.className = 'badge-danger';
    indicatorBadge.textContent = 'Margen de la Casa';
    profitPercentageEl.className = 'val-number mono negative';
    profitPercentageEl.textContent = `${netMarginPercent.toFixed(2)}%`;
  }

  // 3. Compute Stakes (Raw or Rounded)
  let rawStakes = odds.map(odd => totalInvestment / (sumInverseOdds * odd));
  let finalStakes = [];

  if (isRoundingActive) {
    // Smart Anti-Ban Rounding: Round to integers while preserving the total investment
    finalStakes = rawStakes.map(s => Math.round(s));
    const currentSum = finalStakes.reduce((a, b) => a + b, 0);
    const diff = totalInvestment - currentSum;
    
    // Distribute remaining difference to the largest stake
    if (diff !== 0 && finalStakes.length > 0) {
      let maxIdx = 0;
      for (let i = 1; i < finalStakes.length; i++) {
        if (finalStakes[i] > finalStakes[maxIdx]) maxIdx = i;
      }
      finalStakes[maxIdx] += diff;
    }
  } else {
    finalStakes = rawStakes;
  }

  // Update Stake Displays
  finalStakes.forEach((stake, idx) => {
    const el = document.getElementById(`stake-display-${idx}`);
    if (el) el.textContent = `$${stake.toFixed(isRoundingActive ? 0 : 2)}`;
  });

  // 4. Compute Scenarios Breakdown
  renderScenarios(finalStakes, odds, totalInvestment);
}

/**
 * Render Scenarios Breakdown Grid
 */
function renderScenarios(stakes, odds, totalInvestment) {
  const container = document.getElementById('scenarios-container');
  container.innerHTML = '';

  currentOutcomes.forEach((outcome, idx) => {
    const stake = stakes[idx];
    const odd = odds[idx];
    const payout = stake * odd;
    const netProfit = payout - totalInvestment;
    const isProfit = netProfit >= 0;

    const bookmakerObj = BOOKMAKERS.find(b => b.id === outcome.bookmaker) || { name: 'Casa' };

    const card = document.createElement('div');
    card.className = `scenario-card ${isProfit ? 'profitable' : 'loss'}`;

    card.innerHTML = `
      <div class="scenario-title">Si gana: <strong>${outcome.label}</strong> (${bookmakerObj.name})</div>
      <div class="scenario-payout">
        <span class="payout-total mono">$${payout.toFixed(2)}</span>
        <span class="payout-net mono ${isProfit ? 'positive' : 'negative'}">
          ${isProfit ? '+' : ''}$${netProfit.toFixed(2)}
        </span>
      </div>
    `;
    container.appendChild(card);
  });
}

/**
 * Reset inputs
 */
function limpiarCampos() {
  document.getElementById('total-investment').value = 100;
  document.getElementById('rounding-toggle').checked = false;
  currentOutcomes = JSON.parse(JSON.stringify(DEFAULT_CONFIGS[currentMode]));
  renderOutcomesUI();
  calcular();
}

/**
 * History & Operations Persistence
 */
function guardarOperacion() {
  const totalInv = parseFloat(document.getElementById('total-investment').value) || 100;
  const sumInverseOdds = currentOutcomes.reduce((acc, curr) => acc + (1 / curr.odd), 0);
  const isSurebet = sumInverseOdds < 1.0;
  const profitPercent = isSurebet ? ((1 / sumInverseOdds) - 1) * 100 : 0;
  const estimatedProfit = totalInv * (profitPercent / 100);

  const operacion = {
    id: Date.now(),
    fecha: new Date().toLocaleDateString('es-EC', { hour: '2-digit', minute: '2-digit' }),
    modo: `${currentMode} Vías`,
    inversion: totalInv,
    rentabilidad: profitPercent.toFixed(2),
    gananciaEstimada: estimatedProfit.toFixed(2),
    cuotas: currentOutcomes.map(o => o.odd).join(' / ')
  };

  historyRecords.unshift(operacion);
  localStorage.setItem('arbitragepro_history', JSON.stringify(historyRecords));
  renderHistorialUI();
}

function cargarHistorialLocal() {
  try {
    const data = localStorage.getItem('arbitragepro_history');
    if (data) {
      historyRecords = JSON.parse(data);
      renderHistorialUI();
    }
  } catch (e) {
    console.error("Error al cargar historial local:", e);
  }
}

function renderHistorialUI() {
  const container = document.getElementById('history-container');
  const countEl = document.getElementById('metric-count');
  const profitEl = document.getElementById('metric-profit');

  countEl.textContent = historyRecords.length;

  const totalBeneficio = historyRecords.reduce((acc, cur) => acc + parseFloat(cur.gananciaEstimada || 0), 0);
  profitEl.textContent = `$${totalBeneficio.toFixed(2)}`;

  if (historyRecords.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
        <p>No hay operaciones guardadas aún</p>
        <span>Calcula una Surebet positiva y presiona "Guardar".</span>
      </div>
    `;
    return;
  }

  container.innerHTML = '';
  historyRecords.forEach(item => {
    const el = document.createElement('div');
    el.className = 'history-item';
    el.innerHTML = `
      <div class="history-item-top">
        <span class="history-tag">${item.modo} (${item.cuotas})</span>
        <span class="history-date">${item.fecha}</span>
      </div>
      <div class="history-details">
        <span class="history-stake">Inv: $${item.inversion}</span>
        <span class="history-profit mono">+${item.rentabilidad}% (+$${item.gananciaEstimada})</span>
      </div>
    `;
    container.appendChild(el);
  });
}

/**
 * Export history as CSV
 */
function exportarCSV() {
  if (historyRecords.length === 0) {
    alert("No hay registros para exportar aún.");
    return;
  }

  let csvContent = "data:text/csv;charset=utf-8,ID,Fecha,Modo,Cuotas,Inversion_USD,Rentabilidad_Porc,Ganancia_Estimada_USD\n";
  historyRecords.forEach(r => {
    csvContent += `${r.id},"${r.fecha}","${r.modo}","${r.cuotas}",${r.inversion},${r.rentabilidad},${r.gananciaEstimada}\n`;
  });

  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", `arbitragepro_historial_${new Date().toISOString().slice(0, 10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}
