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

## 🚀 Cómo Ejecutar la Plataforma en Producción

ArbitragePro NextGen opera como un servidor HTTP asíncrono con arquitectura blindada en 4 capas y terminal web en tiempo real:

1. **Iniciar el Servidor Cuantitativo:**
   ```bash
   py server.py
   ```
2. **Acceder a la Terminal Web:**
   Abrir en cualquier navegador: `http://127.0.0.1:8080`

3. **Ejecutar Suite de Pruebas Unitarias y de Seguridad:**
   ```bash
   py test_engine.py
   ```

4. **Verificar Endpoints REST y Encabezados OWASP:**
   ```bash
   py verify_server.py
   ```

5. **Simulación de Backtesting Histórico:**
   ```bash
   py backtesting/backtest_engine.py
   ```

---

## 🏛️ Arquitectura Limpia en 4 Capas (Clean Architecture)

- **`domain/`**: Entidades inmutables, reglas deterministas de Surebet, Poisson Dixon-Coles y Guardrails anti-catástrofe (Cero I/O, cero dependencias).
- **`services/`**: Casos de uso (`TradingService` y `LearningService`) para escaneo de cuotas, bucle bayesiano y ensamble CatBoost.
- **`infrastructure/`**: Conexión SQLite WAL thread-safe, Repositorios SQL parametrizados, notificador Telegram y adaptador de inferencia ML.
- **`presentation/`**: Middleware de seguridad OWASP (Anti-Path Traversal, límite DoS 64 KB, Rate Limiting con hash SHA-256 de IPs) y controladores REST desacoplados.
- **`static/`**: Dashboard Fintech Dark Mode con streaming en tiempo real.

