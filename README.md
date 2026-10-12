# ArbitragePro 🚀
**Calculadora Cuantitativa de Arbitraje Deportivo & Surebets**

Software diseñado para calcular discrepancias matemáticas entre casas de apuestas (Ecuabet, Bet365, 1xBet, Betcris, Pinnacle) garantizando beneficio sin importar el resultado del evento.

---

## 🌟 Características Principales

1. **Modo 2 Vías y 3 Vías:**
   - **2 Vías:** Mercados binarios (Tenis, Baloncesto, Más/Menos de 2.5 goles, Ambos Marcan).
   - **3 Vías:** Mercados de Fútbol 1X2 (Local, Empate, Visitante).
2. **Redondeo Inteligente "Anti-Ban":**
   - Las casas de apuestas detectan y limitan cuentas que ingresan apuestas con centavos exactos (ej. `$23.47`).
   - El interruptor *Anti-Ban* ajusta las apuestas a números enteros (`$23` y `$77`) recalculando al milímetro el retorno de cada escenario.
3. **Desglose de Escenarios en Vivo:**
   - Muestra claramente la ganancia neta exacta en dólares si gana la Casa 1, la Casa 2 o el Empate.
4. **Historial de Operaciones:**
   - Almacena automáticamente tus operaciones en el navegador (`LocalStorage`).
   - Muestra la ganancia acumulada y el número de operaciones ejecutadas.
   - Botón de **Exportar a CSV** para llevar tu contabilidad en Excel o Google Sheets.
5. **Diseño Fintech SaaS:**
   - Interfaz en *Dark Mode* ultra rápida, moderna y responsiva (celular y PC).

---

## 💻 Cómo Ejecutar la Aplicación en tu Computadora

No necesitas instalar Node.js ni configurar bases de datos para usarla ahora mismo:

1. Dirígete a la carpeta:
   `C:\Users\pasante.desarrollo1\.gemini\antigravity-ide\scratch\surebet-calculator`
2. Haz doble clic en el archivo **`index.html`**. Se abrirá de inmediato en tu navegador (Chrome, Edge, etc.).

---

## 📈 Hoja de Ruta para Escalado Comercial (Venta / SaaS)

Para convertir esta herramienta en un producto de venta por suscripción ($10 a $25 USD/mes) o venta de licencia única:

### Fase 1 (Actual - Versión MVP / Core)
- [x] Motor matemático completo de 2 y 3 vías.
- [x] Redondeo anti-detección.
- [x] Historial y exportación CSV.

### Fase 2 (Monetización & Autenticación)
- [ ] Integrar autenticación de usuarios (Supabase o Firebase Auth gratuita).
- [ ] Pasarela de pagos para Ecuador e internacional:
  - Internacional: LemonSqueezy o Stripe.
  - Ecuador: Payphone o transferencias directas verificadas por bot.
- [ ] Planes: Plan Gratis (solo 2 vías) y Plan Pro ($10/mes para 3 vías, exportación y cálculo avanzado).

### Fase 3 (Automatización de Cuotas en Vivo)
- [ ] Conectar una API pública o scraper ligero (ej. *The Odds API*) para que el software busque automáticamente las cuotas de Ecuabet vs Bet365 y avise al usuario mediante una alerta o notificación de Telegram cuando surja una oportunidad.
