const byId = id => document.getElementById(id);

function formatTimestamp(value) {
    if (!value) {
        return "--";
    }
    const date = new Date(value);
    if (isNaN(date.getTime())) {
        return value;
    }
    return date.toLocaleString();
}

function toNumber(value, fallback = 0) {
    const number = Number(value);
    return Number.isFinite(number) ? number : fallback;
}

function formatMeasurement(value, decimals = 1, unit = "") {
    return `${toNumber(value).toFixed(decimals)}${unit}`;
}

function getZonePosition(value, safeRange, warningRange, higherRange) {
    const zones = [
        { name: "Safe", range: safeRange, start: 0, end: 33 },
        { name: "Medium", range: warningRange, start: 33, end: 66 },
        { name: "Higher", range: higherRange, start: 66, end: 100 },
    ];

    for (const zone of zones) {
        const [min, max] = zone.range;
        if (value >= min && value <= max) {
            const normalized = max === min ? 0.5 : (value - min) / (max - min);
            return {
                zone: zone.name,
                position: zone.start + normalized * (zone.end - zone.start),
            };
        }
    }

    const minLimit = Math.min(safeRange[0], warningRange[0], higherRange[0]);
    const maxLimit = Math.max(safeRange[1], warningRange[1], higherRange[1]);
    if (value <= minLimit) {
        return { zone: "Higher", position: 0 };
    }
    if (value >= maxLimit) {
        return { zone: "Higher", position: 100 };
    }

    return { zone: "Medium", position: 50 };
}

function updateStatusBar(idPrefix, value, thresholds, unit) {
    const bar = byId(`${idPrefix}Bar`);
    const indicator = byId(`${idPrefix}Indicator`);
    const statusValue = byId(`${idPrefix}StatusValue`);
    const zoneText = byId(`${idPrefix}ZoneText`);

    if (!bar || !indicator || !statusValue || !zoneText) {
        return;
    }

    const safe = thresholds.safe || [0, 0];
    const warning = thresholds.warning || [0, 0];
    const higher = thresholds.danger || [0, 0];
    const zoneState = getZonePosition(toNumber(value), safe, warning, higher);

    indicator.style.left = `${Math.min(Math.max(zoneState.position, 0), 100)}%`;
    statusValue.textContent = unit ? `${formatMeasurement(value, unit === "°C" ? 1 : 0, unit)}` : `${toNumber(value).toFixed(1)}`;
    zoneText.textContent = `Status: ${zoneState.zone}`;
}

function updateStatusBars(latest, thresholds) {
    if (!latest) {
        return;
    }
    
    // Default thresholds if not loaded
    if (!thresholds) {
        thresholds = {
            temperature: { safe: [20, 25], warning: [26, 30], danger: [31, 999] },
            humidity: { safe: [40, 60], warning: [30, 40], danger: [0, 29] },
            static_charge: { safe: [0, 50], warning: [50, 100], danger: [101, 999] }
        };
    }

    updateStatusBar("temperature", latest.temperature, thresholds.temperature, " °C");
    updateStatusBar("pressure", latest.humidity ?? latest.pressure, thresholds.humidity, " %");
    updateStatusBar("static", latest.static_charge, thresholds.static_charge, " V");
}

function showAlertNotification(title, body) {
    if ('Notification' in window && Notification.permission === 'granted') {
        new Notification(title, { body, icon: '/static/favicon.ico' });
    } else if ('Notification' in window && Notification.permission !== 'denied') {
        Notification.requestPermission().then(permission => {
            if (permission === 'granted') {
                new Notification(title, { body, icon: '/static/favicon.ico' });
            }
        });
    }
    // Fallback: show alert
    alert(`${title}: ${body}`);
}

function updateAlertBanner(risk, score) {
    const banner = byId("dashboardAlert");
    const title = byId("dashboardAlertTitle");
    const text = byId("dashboardAlertText");

    if (!banner || !title || !text) {
        return;
    }

    if (risk && /critical/i.test(risk)) {
        banner.className = "alert-banner danger";
        title.textContent = "Critical ESD risk detected";
        text.textContent = `Risk score ${score.toFixed(2)} indicates immediate attention.`;
    } else if (risk && /high/i.test(risk)) {
        banner.className = "alert-banner warning";
        title.textContent = "High ESD risk active";
        text.textContent = `Risk score ${score.toFixed(2)} remains above safe thresholds.`;
    } else if (risk && /medium/i.test(risk)) {
        banner.className = "alert-banner warning";
        title.textContent = "Medium ESD risk";
        text.textContent = `Risk score ${score.toFixed(2)} requires monitoring.`;
    } else {
        banner.className = "alert-banner safe";
        title.textContent = "System stable";
        text.textContent = "No active ESD fault conditions detected.";
    }
}

function updateDashboardCards(latest) {
    if (!latest) {
        return;
    }

    byId("tempValue").textContent = formatMeasurement(latest.temperature, 1, " °C");
    byId("humidityValue").textContent = formatMeasurement(latest.humidity, 1, " %");
    byId("staticValue").textContent = formatMeasurement(latest.static_charge, 1, " V");

    const riskLabel = latest.fault_status || "Safe";
    const riskScore = toNumber(latest.risk_score, 0);
    byId("riskLevel").textContent = riskLabel;
    byId("predictionStatus").textContent = riskLabel;
    byId("lastUpdated").textContent = formatTimestamp(latest.timestamp);
    byId("timestampMeta").textContent = latest.timestamp ? "Latest ThingSpeak timestamp" : "Awaiting live data";

    updateAlertBanner(riskLabel, riskScore);
}

function renderRecentRows(entries) {
    const table = byId("dashboardRecentTable");
    if (!table) {
        return;
    }

    const rows = entries.slice(-6).reverse();
    const existingRows = Array.from(table.querySelectorAll(".table-row.dynamic-row"));
    existingRows.forEach(row => row.remove());

    rows.forEach(entry => {
        const row = document.createElement("div");
        row.className = "table-row dynamic-row";
        row.innerHTML = `
            <div>${formatTimestamp(entry.timestamp)}</div>
            <div>${formatMeasurement(entry.temperature, 1, " °C")}</div>
            <div>${formatMeasurement(entry.humidity, 1, " %")}</div>
            <div>${formatMeasurement(entry.static_charge, 1, " V")}</div>
            <div>${toNumber(entry.risk_score, 0).toFixed(2)}</div>
            <div>${entry.fault_status || "Safe"}</div>
        `;
        table.appendChild(row);
    });

    const countLabel = byId("recentCount");
    if (countLabel) {
        countLabel.textContent = `${rows.length} entries`;
    }
}

async function loadDashboardOverview() {
    const dashboard = byId("dashboardOverview");
    if (!dashboard) {
        return;
    }

    try {
        const [settingsResponse, dataResponse] = await Promise.all([
            fetch("/api/settings"),
            fetch("/api/live-data?t=" + Date.now()),
        ]);

        const thresholds = settingsResponse.ok ? await settingsResponse.json() : null;
        const data = await dataResponse.json();
        const history = data.history || [];
        let latest = data.latest || null;

        if (history.length) {
            const latestFromHistory = history[history.length - 1];
            if (!latest || !latest.timestamp || !latestFromHistory.timestamp || new Date(latestFromHistory.timestamp) > new Date(latest.timestamp)) {
                latest = latestFromHistory;
            }
        }

        updateDashboardCards(latest);
        updateStatusBars(latest, thresholds);
        renderRecentRows(history);
    } catch (err) {
        console.warn("Unable to load dashboard data:", err);
    }
}

function buildTableRow(entry) {
    const row = document.createElement("div");
    row.className = "table-row";
    row.innerHTML = `
            <div>${entry.id || "-"}</div>
        <div>${formatMeasurement(entry.temperature, 1, " °C")}</div>
        <div>${formatMeasurement(entry.humidity, 1, " %")}</div>
        <div>${formatMeasurement(entry.static_charge, 1, " V")}</div>
        <div>${formatMeasurement(entry.voltage, 2, " V")}</div>
        <div>${toNumber(entry.risk_score, 0).toFixed(2)}</div>
        <div>${entry.fault_status || "Safe"}</div>
        <div>${formatTimestamp(entry.timestamp)}</div>
        <div>${entry.device_id || "Device"}</div>
    `;
    return row;
}

async function loadLiveDataTable() {
    const table = byId("liveDataTable");
    if (!table) {
        return;
    }
    try {
        const response = await fetch("/api/live-data?t=" + Date.now());
        const data = await response.json();
        const rows = data.history || [];

        const existing = Array.from(table.querySelectorAll(".table-row.dynamic-row"));
        existing.forEach(node => node.remove());

        rows.slice(-10).reverse().forEach(entry => {
            const row = buildTableRow(entry);
            table.appendChild(row);
        });
    } catch (err) {
        console.warn("Unable to load live sensor data:", err);
    }
}

const historyChartState = {
    outer: null,
    middle: null,
    inner: null,
};
let historyFilterMinutes = 20;

async function loadHistoryTable() {
    const table = byId("liveDataTable");
    if (!table) {
        return;
    }
    try {
        const response = await fetch("/api/history?t=" + Date.now());
        const data = await response.json();
        const rows = data.history || [];

        const existing = Array.from(table.querySelectorAll(".table-row.dynamic-row"));
        existing.forEach(node => node.remove());

        rows.reverse().forEach(entry => {
            const row = buildTableRow(entry);
            table.appendChild(row);
        });
    } catch (err) {
        console.warn("Unable to load history data:", err);
    }
}

function setHistoryFilter(minutes, button) {
    historyFilterMinutes = minutes;
    document.querySelectorAll(".history-filter").forEach(btn => {
        btn.classList.toggle("active", btn === button);
    });
    loadHistoricalAnalysis();
}

function getFilteredHistory(history) {
    if (!history || !history.length) {
        return [];
    }
    const cutoff = Date.now() - historyFilterMinutes * 60 * 1000;
    return history.filter(entry => {
        const ts = entry.timestamp ? new Date(entry.timestamp).getTime() : 0;
        return ts >= cutoff;
    });
}

function buildChart(chartId, config) {
    const canvas = byId(chartId);
    if (!canvas) {
        return null;
    }
    if (historyChartState[chartId]) {
        // Update existing chart data
        historyChartState[chartId].data.labels = config.data.labels;
        historyChartState[chartId].data.datasets.forEach((dataset, i) => {
            dataset.data = config.data.datasets[i].data;
        });
        historyChartState[chartId].update('none'); // Update without animation for speed
        return historyChartState[chartId];
    }
    historyChartState[chartId] = new Chart(canvas, config);
    return historyChartState[chartId];
}

function computeHistorySummary(history) {
    const summary = {
        latest: null,
        peakStatic: 0,
        avgStatic: 0,
        avgRisk: 0,
        riskCounts: { safe: 0, medium: 0, high: 0 },
        thresholdCrossings: 0,
        fluctuation: 0,
        avgTemp: 0,
        avgHumidity: 0,
        avgVoltage: 0,
        latestZone: "Safe",
    };

    if (!history || !history.length) {
        return summary;
    }

    const validStatic = history.map(entry => toNumber(entry.static_charge, 0));
    const validTemp = history.map(entry => toNumber(entry.temperature, 0));
    const validHumidity = history.map(entry => toNumber(entry.humidity, 0));
    const validVoltage = history.map(entry => toNumber(entry.voltage, 0));
    const validRisk = history.map(entry => toNumber(entry.risk_score, 0));

    summary.latest = history[history.length - 1];
    summary.peakStatic = Math.max(...validStatic, 0);
    summary.avgStatic = validStatic.reduce((sum, v) => sum + v, 0) / validStatic.length || 0;
    summary.avgRisk = validRisk.reduce((sum, v) => sum + v, 0) / validRisk.length || 0;
    summary.avgTemp = validTemp.reduce((sum, v) => sum + v, 0) / validTemp.length || 0;
    summary.avgHumidity = validHumidity.reduce((sum, v) => sum + v, 0) / validHumidity.length || 0;
    summary.avgVoltage = validVoltage.reduce((sum, v) => sum + v, 0) / validVoltage.length || 0;

    let lastStatic = validStatic[0];
    summary.fluctuation = validStatic.reduce((acc, curr) => acc + Math.abs(curr - lastStatic), 0);
    if (validStatic.length) {
        summary.fluctuation = summary.fluctuation / validStatic.length;
    }

    history.forEach(entry => {
        const risk = toNumber(entry.risk_score, 0);
        if (risk >= 0.70) {
            summary.riskCounts.high += 1;
        } else if (risk >= 0.35) {
            summary.riskCounts.medium += 1;
        } else {
            summary.riskCounts.safe += 1;
        }
        if ((entry.fault_status || "").toLowerCase().includes("medium") || (entry.fault_status || "").toLowerCase().includes("high")) {
            summary.thresholdCrossings += 1;
        }
    });

    const latestRisk = toNumber(summary.latest?.risk_score, 0);
    if (latestRisk >= 0.70) {
        summary.latestZone = "Higher";
    } else if (latestRisk >= 0.35) {
        summary.latestZone = "Medium";
    } else {
        summary.latestZone = "Safe";
    }

    return summary;
}

function renderHistoricalAnalysis(history) {
    const filtered = getFilteredHistory(history);
    const summary = computeHistorySummary(filtered);

    byId("historyRecordCount").textContent = filtered.length;
    byId("historyLastUpdated").textContent = summary.latest ? formatTimestamp(summary.latest.timestamp) : "--";
    byId("outerTempValue").textContent = `${summary.avgTemp.toFixed(1)} °C`;
    byId("outerHumidityValue").textContent = `${summary.avgHumidity.toFixed(1)} %`;
    byId("outerVoltageValue").textContent = `${summary.avgVoltage.toFixed(2)} V`;
    byId("middleStaticAvg").textContent = `${summary.avgStatic.toFixed(1)} V`;
    byId("middleStaticPeak").textContent = `${summary.peakStatic.toFixed(1)} V`;
    byId("middleStaticFluctuation").textContent = `${summary.fluctuation.toFixed(1)} V`;
    byId("innerRiskLatest").textContent = `${summary.latest ? summary.latest.risk_score.toFixed(2) : "--"}`;
    byId("innerRiskPeaks").textContent = `${summary.riskCounts.high + summary.riskCounts.medium}`;
    byId("innerRiskZone").textContent = summary.latestZone;
    byId("summaryPeakStatic").textContent = `${summary.peakStatic.toFixed(1)} V`;
    byId("summaryAvgRisk").textContent = `${summary.avgRisk.toFixed(2)}`;
    byId("summaryCrossings").textContent = `${summary.thresholdCrossings}`;

    const timeLabels = filtered.map(entry => formatTimestamp(entry.timestamp));
    const tempSeries = filtered.map(entry => toNumber(entry.temperature, 0));
    const humiditySeries = filtered.map(entry => toNumber(entry.humidity, 0));
    const voltageSeries = filtered.map(entry => toNumber(entry.voltage, 0));
    const staticSeries = filtered.map(entry => toNumber(entry.static_charge, 0));
    const riskSeries = filtered.map(entry => toNumber(entry.risk_score, 0));

    buildChart("outerHistoryChart", {
        type: "line",
        data: {
            labels: timeLabels,
            datasets: [
                {
                    label: "Temperature",
                    data: tempSeries,
                    borderColor: "#3b82f6",
                    backgroundColor: "rgba(59, 130, 246, 0.18)",
                    tension: 0.35,
                    fill: true,
                    pointRadius: 0,
                    borderWidth: 3,
                },
                {
                    label: "Humidity",
                    data: humiditySeries,
                    borderColor: "#f97316",
                    backgroundColor: "rgba(249, 115, 22, 0.18)",
                    tension: 0.35,
                    fill: true,
                    pointRadius: 0,
                    borderWidth: 3,
                },
                {
                    label: "Voltage",
                    data: voltageSeries,
                    borderColor: "#22c55e",
                    backgroundColor: "rgba(34, 197, 94, 0.18)",
                    tension: 0.35,
                    fill: true,
                    pointRadius: 0,
                    borderWidth: 3,
                },
            ],
        },
        options: {
            responsive: true,
            animation: { duration: 1200, easing: "easeOutQuart" },
            plugins: { legend: { display: false } },
            scales: {
                x: { display: false },
                y: { ticks: { color: "#cbd5e1" }, grid: { color: "rgba(148, 163, 184, 0.08)" } },
            },
        },
    });

    buildChart("middleHistoryChart", {
        type: "line",
        data: {
            labels: timeLabels,
            datasets: [
                {
                    label: "Static Charge",
                    data: staticSeries,
                    borderColor: "#a855f7",
                    backgroundColor: "rgba(168, 85, 247, 0.22)",
                    tension: 0.35,
                    fill: true,
                    pointRadius: 0,
                    borderWidth: 3,
                },
            ],
        },
        options: {
            responsive: true,
            animation: { duration: 1200, easing: "easeOutQuart" },
            plugins: { legend: { display: false } },
            scales: {
                x: { display: false },
                y: { ticks: { color: "#cbd5e1" }, grid: { color: "rgba(148, 163, 184, 0.08)" } },
            },
        },
    });

    buildChart("innerHistoryChart", {
        type: "doughnut",
        data: {
            labels: ["Safe", "Medium", "Higher"],
            datasets: [{
                data: [summary.riskCounts.safe, summary.riskCounts.medium, summary.riskCounts.high],
                backgroundColor: ["rgba(16, 185, 129, 0.85)", "rgba(249, 115, 22, 0.85)", "rgba(239, 68, 68, 0.85)"],
                borderWidth: 0,
            }],
        },
        options: {
            responsive: true,
            animation: { duration: 1200, easing: "easeOutQuart" },
            cutout: "70%",
            plugins: { legend: { position: "bottom", labels: { color: "#cbd5e1", boxWidth: 10 } } },
        },
    });
}

async function loadHistoricalAnalysis() {
    try {
        const response = await fetch("/api/history?t=" + Date.now());
        const data = await response.json();
        const history = data.history || [];
        renderHistoricalAnalysis(history);
    } catch (err) {
        console.warn("Unable to load historical analysis:", err);
    }
}

async function refreshAlerts() {
    const table = byId("alertsTable");
    if (!table) {
        return;
    }
    try {
        const response = await fetch("/api/history?t=" + Date.now());
        const data = await response.json();
        const alerts = (data.history || []).filter(entry => {
            return entry.fault_status && /high|critical|medium/i.test(entry.fault_status);
        });

        const existing = Array.from(table.querySelectorAll(".table-row.dynamic-row"));
        existing.forEach(node => node.remove());

        alerts.reverse().slice(0, 12).forEach(entry => {
            const row = document.createElement("div");
            row.className = "table-row dynamic-row";
            row.innerHTML = `
                <div>${entry.fault_status || "Alert"}</div>
                <div>${entry.fault_status || "Medium"}</div>
                <div>Risk score ${ (entry.risk_score || 0).toFixed(2) } from live telemetry</div>
                <div>${formatTimestamp(entry.timestamp)}</div>
            `;
            table.appendChild(row);
        });
    } catch (err) {
        console.warn("Unable to refresh alerts:", err);
    }
}

async function handlePrediction(event) {
    if (event) {
        event.preventDefault();
    }
    const temperature = parseFloat(byId("predictTemperature").value) || 0;
    const humidity = parseFloat(byId("predictHumidity").value) || 0;
    const staticCharge = parseFloat(byId("predictStatic").value) || 0;
    const voltage = parseFloat(byId("predictVoltage").value) || 0;

    try {
        const response = await fetch("/api/predict", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                temperature,
                humidity,
                static_charge: staticCharge,
                voltage,
            }),
        });
        const result = await response.json();
        const container = byId("predictionResult");
        container.innerHTML = `
            <div class="prediction-card">
                <h3>Result: ${result.predicted_class}</h3>
                <p>Risk probability: <strong>${(result.risk_probability || 0).toFixed(4)}</strong></p>
                <p>Confidence: <strong>${(result.confidence_score || 0).toFixed(4)}</strong></p>
                <p>Timestamp: <strong>${result.timestamp || "--"}</strong></p>
            </div>
        `;
    } catch (err) {
        console.warn("Prediction request failed:", err);
    }
}

function exportCSV() {
    alert("CSV export is currently a demonstration feature. Use the data view or browser tools to save reports.");
}

function exportPDF() {
    alert("PDF export is currently a demonstration feature. Please use the report generation page.");
}

window.addEventListener("DOMContentLoaded", () => {
    if (byId("dashboardOverview")) {
        loadDashboardOverview();
        setInterval(loadDashboardOverview, 10000);
    }
    if (byId("liveDataTable") && window.location.pathname === "/live-data") {
        loadLiveDataTable();
        setInterval(loadLiveDataTable, 10000);
    }
    if (byId("liveDataTable") && window.location.pathname === "/history") {
        loadHistoryTable();
        loadHistoricalAnalysis();
        setInterval(() => {
            loadHistoryTable();
            loadHistoricalAnalysis();
        }, 10000);
    }
    if (byId("alertsTable")) {
        refreshAlerts();
        setInterval(refreshAlerts, 10000);
    }
    if (byId("predictionForm")) {
        byId("predictionForm").addEventListener("submit", handlePrediction);
    }
});
let outerChart = null;
let middleChart = null;
let innerChart = null;

async function loadHistoricalAnalysis() {
    try {
        const response = await fetch('/api/history-data');
        const data = await response.json();

        if (!data || !data.timestamps || data.timestamps.length === 0) {
            console.log("No history data available");
            return;
        }

        renderHistoryCharts(data);
        updateHistoryMetrics(data);

    } catch (error) {
        console.error("History load failed:", error);
    }
}

function renderHistoryCharts(data) {
    const labels = data.timestamps;

    if (outerChart) outerChart.destroy();
    if (middleChart) middleChart.destroy();
    if (innerChart) innerChart.destroy();

    /* MAIN ENVIRONMENT CHART */
    outerChart = new Chart(
        document.getElementById("outerHistoryChart"),
        {
            type: "line",
            data: {
                labels,
                datasets: [
                    {
                        label: "Temperature",
                        data: data.temperature,
                        borderColor: "#3b82f6",
                        tension: 0.4
                    },
                    {
                        label: "Humidity",
                        data: data.humidity,
                        borderColor: "#22c55e",
                        tension: 0.4
                    },
                    {
                        label: "Voltage",
                        data: data.voltage,
                        borderColor: "#f97316",
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        }
    );

    /* STATIC CHARGE */
    middleChart = new Chart(
        document.getElementById("middleHistoryChart"),
        {
            type: "line",
            data: {
                labels,
                datasets: [{
                    label: "Static Charge",
                    data: data.static_charge,
                    borderColor: "#eab308",
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        }
    );

    /* RISK */
    innerChart = new Chart(
        document.getElementById("innerHistoryChart"),
        {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    label: "Risk Score",
                    data: data.risk_score,
                    backgroundColor: "#ef4444"
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        }
    );
}

function updateHistoryMetrics(data) {
    const avg = arr => (arr.reduce((a,b)=>a+b,0)/arr.length).toFixed(1);

    document.getElementById("outerTempValue").innerText =
        avg(data.temperature) + " °C";

    document.getElementById("outerHumidityValue").innerText =
        avg(data.humidity) + " %";

    document.getElementById("outerVoltageValue").innerText =
        avg(data.voltage) + " V";

    document.getElementById("middleStaticAvg").innerText =
        avg(data.static_charge) + " V";

    document.getElementById("middleStaticPeak").innerText =
        Math.max(...data.static_charge) + " V";

    document.getElementById("summaryPeakStatic").innerText =
        Math.max(...data.static_charge) + " V";
}

window.addEventListener("DOMContentLoaded", function () {
    loadHistoricalAnalysis();
});