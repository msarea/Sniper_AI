document.addEventListener('DOMContentLoaded', () => {
    const socket = io();
    const buySound = new Audio('/static/sounds/sniper_target.mp3');
    const sellSound = new Audio('/static/sounds/sell_alert.mp3'); 
    let lastSignal = "HOLD";

    // --- 1. ELEMENT MAPPING ---
    const els = {
        totalProfit: document.getElementById('total-profit'),
        symbolDisplay: document.getElementById('symbol-display'),
        signalDiv: document.getElementById('prediction-signal'),
        scoreBadge: document.getElementById('confluence-score'),
        regimeStatus: document.getElementById('regime-status'),
        loadBtn: document.getElementById('change-symbol-btn'), 
        symbolInput: document.getElementById('symbol-input'),
        settingsBtn: document.getElementById('settings-btn'),
        settingsModal: document.getElementById('settings-modal'),
        closeModal: document.querySelector('.close-modal'),
        downloadBtn: document.getElementById('download-log-btn'),
        panicBtn: document.getElementById('panic-btn'),
        saveBtn: document.getElementById('save-settings-btn'),
        metrics: {
            adx: document.getElementById('val-adx'),
            rsi: document.getElementById('val-rsi'),
            atr: document.getElementById('val-atr'),
            entry: document.getElementById('entry-price'),
            sl: document.getElementById('sl-price'),
            tp: document.getElementById('tp-price')
        },
        cards: {
            Trend: document.getElementById('card-trend'),
            VWAP: document.getElementById('card-vwap'),
            Bollinger: document.getElementById('card-bollinger'),
            MACD: document.getElementById('card-macd')
        },
        cardTexts: {
            Trend: document.getElementById('status-trend'),
            VWAP: document.getElementById('status-vwap'),
            Bollinger: document.getElementById('status-bollinger'),
            MACD: document.getElementById('status-macd')
        },
        chartContainer: document.getElementById('chart-container')
    };

    // --- 2. CHART INITIALIZATION ---
    let chart = null, candleSeries = null, emaSeries = null;

    function initChart() {
        if (!els.chartContainer) return;
        chart = LightweightCharts.createChart(els.chartContainer, {
            layout: { background: { color: '#1a1a2e' }, textColor: '#d1d4dc' },
            grid: { vertLines: { color: 'rgba(43, 43, 59, 0.08)' }, horzLines: { color: 'rgba(43, 43, 59, 0.08)' } },
            timeScale: { timeVisible: true, fixRightEdge: false, rightOffset: 15 },
            rightPriceScale: { borderColor: '#485c7b' }
        });
        emaSeries = chart.addLineSeries({ color: '#2962FF', lineWidth: 2, title: '9 EMA' });
        candleSeries = chart.addCandlestickSeries({ upColor: '#50fa7b', downColor: '#ff5555', borderVisible: false });
        
        const tooltip = document.createElement('div');
        tooltip.style = `position: absolute; display: none; padding: 12px; z-index: 1000; top: 15px; left: 15px; border-radius: 6px; background: rgba(26, 26, 46, 0.9); color: #f8f8f2; font-family: monospace; font-size: 13px; border: 1px solid #6272a4; pointer-events: none;`;
        els.chartContainer.appendChild(tooltip);

        chart.subscribeCrosshairMove(param => {
            if (param.time && param.point && param.seriesData.get(candleSeries)) {
                const data = param.seriesData.get(candleSeries);
                const emaVal = param.seriesData.get(emaSeries);
        
                // --- ADDED: Date Formatting ---
                // Multiply by 1000 because your backend sends seconds, but JS needs milliseconds
                const dateObj = new Date(param.time * 1000);
                const timeStr = dateObj.toLocaleString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    hour: '2-digit',
                    minute: '2-digit',
                    hour12: false
                });
        
                tooltip.style.display = 'block';
                tooltip.innerHTML = `
                    <div style="color: #8be9fd; font-weight: bold; border-bottom: 1px solid #444; margin-bottom: 5px;">MARKET DATA</div>
                    <div style="color: #6272a4; font-size: 0.85rem; margin-bottom: 5px; font-family: 'Courier New', monospace;">
                        ${timeStr}
                    </div>
                    O: <span style="color: #f1fa8c">${data.open.toFixed(2)}</span> H: <span style="color: #50fa7b">${data.high.toFixed(2)}</span><br>
                    L: <span style="color: #ff5555">${data.low.toFixed(2)}</span> C: <span style="color: #bd93f9">${data.close.toFixed(2)}</span><br>
                    ${emaVal ? `9 EMA: <span style="color: #2962FF">${emaVal.value.toFixed(2)}</span>` : ''}`;
            } else {
                tooltip.style.display = 'none';
            }
        });

        new ResizeObserver(() => chart.resize(els.chartContainer.clientWidth, els.chartContainer.clientHeight)).observe(els.chartContainer);
    }
    initChart();

    // --- 3. BUTTON INTERACTIONS ---
    
    // Settings Modal
    if (els.settingsBtn) {
        els.settingsBtn.onclick = () => els.settingsModal.style.display = "block";
        els.closeModal.onclick = () => els.settingsModal.style.display = "none";
        window.onclick = (e) => { if (e.target == els.settingsModal) els.settingsModal.style.display = "none"; };
    }

    // Download Log
    if (els.downloadBtn) {
        els.downloadBtn.onclick = () => window.location.href = '/download_log';
    }

    // Emergency Panic (Cleaned up duplicate)
    if (els.panicBtn) {
        els.panicBtn.onclick = () => {
            if (confirm("🚨 EMERGENCY EXIT: Close all positions and stop the bot?")) {
                fetch('/panic_exit', { method: 'POST' }).then(r => r.json()).then(d => alert(d.message));
            }
        };
    }

    // Save Settings
    if (els.saveBtn) {
        els.saveBtn.addEventListener('click', () => {
            const newConfig = {
                alpaca_api_key: document.getElementById('cfg-api-key').value,
                alpaca_secret_key: document.getElementById('cfg-secret-key').value,
                trading_enabled: document.getElementById('cfg-trading-enabled').checked,
                short_enabled: document.getElementById('cfg-short-enabled').checked,
                daily_profit_goal: document.getElementById('cfg-profit-goal').value,
                risk_per_trade: document.getElementById('cfg-risk').value,
                max_daily_loss: document.getElementById('cfg-max-loss').value,
                telegram_enabled: document.getElementById('cfg-tg-enabled').checked,
                telegram_bot_token: document.getElementById('cfg-tg-token').value,
                telegram_chat_id: document.getElementById('cfg-tg-chat').value
            };
            fetch('/save_settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newConfig)
            }).then(() => {
                alert("✅ Settings Saved! System Restarting...");
                window.location.reload(); 
            });
        });
    }

    // Load Symbol
    if (els.loadBtn) {
        els.loadBtn.onclick = () => {
            let symbol = els.symbolInput.value.trim().toUpperCase();
            if (symbol) {
                els.signalDiv.innerText = "LOADING...";
                els.signalDiv.className = "signal-box signal-hold";
                els.scoreBadge.innerText = "Confluence: --%";
                Object.values(els.metrics).forEach(el => el.innerText = "--");
                // Keep Hyphen formatting for URL consistency
                window.history.pushState({ symbol }, '', `/${symbol.replace('/', '-')}`);
                fetch('/change_symbol', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ symbol })
                });
            }
        };
    }

    // --- 4. SOCKET UPDATES ---
    socket.on('chart_history', (data) => {
        candleSeries.setData(data.candles);
        const emaData = data.candles.map((c, i, a) => {
            if (i < 9) return { time: c.time };
            const avg = a.slice(i-8, i+1).reduce((s, x) => s + x.close, 0) / 9;
            return { time: c.time, value: avg };
        });
        emaSeries.setData(emaData);
        chart.timeScale().fitContent();
    });

    socket.on('chart_update', (candle) => {
        candleSeries.update(candle);
        const data = candleSeries.data() || []; // Added fallback to empty array
        if (data.length >= 9) {
            const recentCloseSum = data.slice(-9).reduce((s, c) => s + (c.close || 0), 0);
            const avg = recentCloseSum / 9;
            emaSeries.update({ time: candle.time, value: avg });
        }
    });

    socket.on('analysis_update', (data) => {
        if (data.signal !== lastSignal && data.confluence >= 80) {
            if (data.signal === 'BUY') buySound.play().catch(() => {});
            if (data.signal === 'SELL') sellSound.play().catch(() => {});
        }
        lastSignal = data.signal;
        if (els.symbolDisplay) els.symbolDisplay.innerText = data.symbol || '--';
        if (els.totalProfit) els.totalProfit.innerText = `$${data.total_profit.toFixed(2)}`;
        
        ['adx', 'rsi', 'atr', 'entry', 'sl', 'tp'].forEach(k => {
            if (els.metrics[k]) els.metrics[k].innerText = data[k] || (data[`${k}_price`] ? data[`${k}_price`] : '--');
        });

        if (els.signalDiv) {
            els.signalDiv.innerText = data.signal;
            els.signalDiv.className = `signal-box signal-${data.signal.toLowerCase()}`;
        }
        if (els.regimeStatus) els.regimeStatus.innerText = data.regime || 'STABILIZING';
        if (els.scoreBadge) els.scoreBadge.innerText = `Confluence: ${data.confluence}%`;
        if (data.dashboard) {
            Object.keys(data.dashboard).forEach(key => {
                if (els.cards[key]) {
                    els.cardTexts[key].innerText = data.dashboard[key];
                    els.cards[key].className = `strategy-card status-${data.dashboard[key].toLowerCase()}`;
                }
            });
        }
    });
});