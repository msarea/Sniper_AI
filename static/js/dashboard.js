document.addEventListener('DOMContentLoaded', () => {
    const socket = io();
    const buySound = new Audio('https://actions.google.com/sounds/v1/alarms/beep_short.ogg');
    let lastSignal = "HOLD"; 

    if (Notification.permission !== "granted") Notification.requestPermission();

    // --- 1. ELEMENT MAPPING ---
    const els = {
        symbolDisplay: document.getElementById('symbol-display'),
        signalDiv: document.getElementById('prediction-signal'),
        scoreBadge: document.getElementById('confluence-score'),
        cards: {
            Trend_MA_Cross:     { el: document.getElementById('card-trend'), txt: document.getElementById('status-trend') },
            VWAP_Pullback:      { el: document.getElementById('card-vwap'), txt: document.getElementById('status-vwap') },
            Bollinger_Breakout: { el: document.getElementById('card-bollinger'), txt: document.getElementById('status-bollinger') },
            MACD:               { el: document.getElementById('card-macd'), txt: document.getElementById('status-macd') }
        },
        metrics: {
            entry: document.getElementById('entry-price'),
            sl: document.getElementById('sl-price'),
            tp: document.getElementById('tp-price')
        },
        chartContainer: document.getElementById('chart-container'),
        inputs: { text: document.getElementById('symbol-input'), btn: document.getElementById('change-symbol-btn') },
        panicBtn: document.getElementById('panic-btn'),
        cfgModal: document.getElementById('settings-modal'),
        saveBtn: document.getElementById('save-settings-btn'),
        wipeBtn: document.getElementById('wipe-data-btn'),
        settingsBtn: document.getElementById('settings-btn')
    };

    // --- 2. CHART INITIALIZATION ---
    let chart = null;
    let candleSeries = null;

    function initChart() {
        if (!els.chartContainer) return;

        const chartOptions = {
            layout: { background: { color: '#1a1a2e' }, textColor: '#d1d4dc' },
            grid: { vertLines: { color: '#2b2b3b' }, horzLines: { color: '#2b2b3b' } },
            // FORCING NEW YORK TIME DISPLAY
            localization: {
                locale: 'en-US',
                timeFormatter: (timestamp) => {
                    return new Date(timestamp * 1000).toLocaleString('en-US', {
                        timeZone: 'America/New_York',
                        hour: '2-digit',
                        minute: '2-digit',
                        hour12: false
                    });
                },
            },
            timeScale: { 
                timeVisible: true, 
                secondsVisible: false, 
                borderColor: '#485c7b',
                rightOffset: 25, 
                shiftVisibleRangeOnNewBar: true,
                // Override the tick marks on the bottom axis to force New York time
                tickMarkFormatter: (time) => {
                    const date = new Date(time * 1000);
                    return date.toLocaleString('en-US', {
                        timeZone: 'America/New_York',
                        hour: '2-digit',
                        minute: '2-digit',
                        hour12: false
                    });
                },
            }
        };

        chart = LightweightCharts.createChart(els.chartContainer, chartOptions);
        candleSeries = chart.addCandlestickSeries({ 
            upColor: '#50fa7b', downColor: '#ff5555', 
            borderVisible: false, wickUpColor: '#50fa7b', wickDownColor: '#ff5555' 
        });

        candleSeries.applyOptions({
            priceLineVisible: true,
            priceLineWidth: 2,
            priceLineColor: '#50fa7b',
            priceLineStyle: 2, 
        });

        new ResizeObserver(entries => {
            if (entries.length === 0 || !chart) return;
            const { width, height } = entries[0].contentRect;
            chart.applyOptions({ width, height });
        }).observe(els.chartContainer);
    }
    initChart();

    // --- 3. SYMBOL & URL MANAGEMENT ---
    const changeSymbol = (s) => { 
        if (!s) return;
        s = s.trim().toUpperCase();
        const newUrl = window.location.protocol + "//" + window.location.host + window.location.pathname + `?symbol=${s}`;
        window.history.pushState({ path: newUrl }, s, newUrl);
        document.title = `Sniper AI - ${s}`;
        socket.emit('change_symbol', { symbol: s }); 
    };

    // --- 4. SOCKET LISTENERS ---
    socket.on('connect', () => {
        const urlParams = new URLSearchParams(window.location.search);
        const urlSymbol = urlParams.get('symbol') || 'BTC';
        changeSymbol(urlSymbol);
    });

    socket.on('symbol_changed', d => { 
        if(els.symbolDisplay) els.symbolDisplay.textContent = d.symbol; 
        if(els.inputs.text) els.inputs.text.value = d.symbol;
        if(chart) chart.timeScale().fitContent();
    });

    socket.on('chart_history', (data) => {
        if (candleSeries && data.candles) {
            candleSeries.setData(data.candles);
            chart.timeScale().fitContent();
        }
    });

    socket.on('chart_update', (candle) => {
        if (candleSeries && chart) {
            candleSeries.update(candle);
            chart.timeScale().scrollToPosition(0, true); 
        }
    });

    socket.on('analysis_update', d => {
        if(els.signalDiv) {
            els.signalDiv.textContent = d.signal;
            els.signalDiv.className = d.signal === 'BUY' ? 'signal-buy' : d.signal === 'SELL' ? 'signal-sell' : 'signal-hold';
        }
        if(els.metrics.entry) els.metrics.entry.textContent = d.entry_price || "--";
        if(els.metrics.sl) els.metrics.sl.textContent = d.sl_price || "--";
        if(els.metrics.tp) els.metrics.tp.textContent = d.tp_price || "--";
        if(els.scoreBadge) els.scoreBadge.textContent = "Confluence: " + (d.confluence_score || 0);

        if (d.dashboard) {
            Object.keys(d.dashboard).forEach(key => {
                const card = els.cards[key];
                if (card && card.el) {
                    const status = d.dashboard[key];
                    card.el.className = 'strategy-card ' + (status === 'BUY' ? 'status-buy' : status === 'SELL' ? 'status-sell' : 'status-neutral');
                    card.txt.textContent = status === 'BUY' ? 'BULLISH' : status === 'SELL' ? 'BEARISH' : 'NEUTRAL';
                }
            });
        }
        if (d.signal !== lastSignal && (d.signal === 'BUY' || d.signal === 'SELL')) {
            buySound.play().catch(()=>{});
        }
        lastSignal = d.signal;
    });

    // --- 5. INTERACTION EVENTS ---
    if(els.inputs.btn) els.inputs.btn.onclick = () => changeSymbol(els.inputs.text.value);
    if(els.inputs.text) {
        els.inputs.text.onkeypress = (e) => { if (e.key === 'Enter') changeSymbol(els.inputs.text.value); };
    }

    if (els.panicBtn) {
        els.panicBtn.onclick = () => {
            if(confirm("🚨 Execute Emergency Exit?")) {
                fetch('/panic', { method: 'POST' })
                .then(res => res.json())
                .then(res => alert(res.message));
            }
        };
    }

    // --- 6. SETTINGS MODAL ACTIONS ---
    if (els.settingsBtn) {
        els.settingsBtn.onclick = () => els.cfgModal.style.display = "block";
    }

    const closeBtn = document.querySelector(".close-modal");
    if (closeBtn) {
        closeBtn.onclick = () => els.cfgModal.style.display = "none";
    }

    if (els.saveBtn) {
        els.saveBtn.onclick = () => {
            const data = {
                alpaca_api_key: document.getElementById('cfg-api-key').value,
                alpaca_secret_key: document.getElementById('cfg-secret-key').value,
                broker: document.getElementById('cfg-broker').value,
                trading_enabled: document.getElementById('cfg-trading-enabled').checked,
                short_enabled: document.getElementById('cfg-short-enabled').checked,
                risk_per_trade: document.getElementById('cfg-risk').value,
                max_daily_loss: document.getElementById('cfg-max-loss').value,
                telegram_enabled: document.getElementById('cfg-tg-enabled').checked,
                telegram_bot_token: document.getElementById('cfg-tg-token').value,
                telegram_chat_id: document.getElementById('cfg-tg-chat').value
            };

            fetch('/save_config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            })
            .then(res => res.json())
            .then(res => {
                alert(res.message);
                if (res.status === 'success') {
                    els.cfgModal.style.display = "none";
                    window.location.reload(); 
                }
            })
            .catch(err => alert("Error saving: " + err));
        };
    }

    if (els.wipeBtn) {
        els.wipeBtn.onclick = () => {
            if (confirm("🚨 WIPE ALL DATA?")) {
                fetch('/wipe_config', { method: 'POST' })
                .then(res => res.json())
                .then(res => {
                    alert(res.message);
                    window.location.reload();
                });
            }
        };
    }
});