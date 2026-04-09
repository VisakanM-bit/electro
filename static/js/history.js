let outerChart = null;
let middleChart = null;
let innerChart = null;

let fullHistoryData = null;
let selectedRange = 20;

/* =========================================
   PAGE LOAD
   ========================================= */
window.addEventListener("DOMContentLoaded", function () {
    loadHistoricalAnalysis();
});

/* =========================================
   FETCH DATA
   ========================================= */
async function loadHistoricalAnalysis() {
    try {
        const response = await fetch("/api/history-data");
        fullHistoryData = await response.json();

        if (!fullHistoryData || !fullHistoryData.timestamps) {
            console.error("No history data found");
            return;
        }

        updateHistoryView(selectedRange);

    } catch (error) {
        console.error("History load failed:", error);
    }
}

/* =========================================
   TIME RANGE BUTTON
   ========================================= */
function setHistoryFilter(minutes, button) {
    selectedRange = minutes;

    document.querySelectorAll(".history-filter").forEach(btn => {
        btn.classList.remove("active");
    });

    if (button) {
        button.classList.add("active");
    }

    updateHistoryView(minutes);
}

/* =========================================
   MAIN UPDATE
   ========================================= */
function updateHistoryView(minutes) {
    if (!fullHistoryData) return;

    const filtered = filterHistoryData(fullHistoryData, minutes);

    renderCharts(filtered);
    updateMetrics(filtered);
    loadHistoryTable(filtered);
}

/* =========================================
   FILTER DATA
   ========================================= */
function filterHistoryData(data, minutes) {
    const total = data.timestamps.length;

    let points = 5;

    if (minutes <= 20) points = 5;
    else if (minutes <= 60) points = 8;
    else if (minutes <= 120) points = 10;
    else if (minutes <= 180) points = 12;
    else if (minutes <= 300) points = 15;
    else points = total;

    return {
        timestamps: data.timestamps.slice(-points),
        temperature: data.temperature.slice(-points),
        humidity: data.humidity.slice(-points),
        static_charge: data.static_charge.slice(-points),
        voltage: data.voltage.slice(-points),
        risk_score: data.risk_score.slice(-points)
    };
}

/* =========================================
   RENDER CHARTS
   ========================================= */
function renderCharts(data) {
    const labels = data.timestamps;

    if (outerChart) outerChart.destroy();
    if (middleChart) middleChart.destroy();
    if (innerChart) innerChart.destroy();

    /* MAIN CHART */
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
                        borderWidth: 3,
                        tension: 0.45,
                        fill: true,
                        backgroundColor: "rgba(59,130,246,0.12)"
                    },
                    {
                        label: "Humidity",
                        data: data.humidity,
                        borderColor: "#22c55e",
                        borderWidth: 3,
                        tension: 0.45,
                        fill: true,
                        backgroundColor: "rgba(34,197,94,0.10)"
                    },
                    {
                        label: "Voltage",
                        data: data.voltage,
                        borderColor: "#f97316",
                        borderWidth: 3,
                        tension: 0.45
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: {
                    duration: 1000
                }
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
                    borderWidth: 3,
                    tension: 0.45,
                    fill: true,
                    backgroundColor: "rgba(234,179,8,0.12)"
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        }
    );

    /* RISK CHART */
    innerChart = new Chart(
        document.getElementById("innerHistoryChart"),
        {
            type: "bar",
            data: {
                labels,
                datasets: [{
                    label: "Risk Score",
                    data: data.risk_score,
                    backgroundColor: "rgba(239,68,68,0.75)",
                    borderRadius: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        }
    );
}

/* =========================================
   UPDATE VALUES
   ========================================= */
function updateMetrics(data) {
    const avg = arr =>
        (arr.reduce((a, b) => a + b, 0) / arr.length).toFixed(1);

    const setText = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.innerText = value;
    };

    setText("outerTempValue", avg(data.temperature) + " °C");
    setText("outerHumidityValue", avg(data.humidity) + " %");
    setText("outerVoltageValue", avg(data.voltage) + " V");

    setText("middleStaticAvg", avg(data.static_charge) + " V");
    setText("middleStaticPeak", Math.max(...data.static_charge) + " V");

    setText("summaryPeakStatic", Math.max(...data.static_charge) + " V");
    setText("summaryAvgRisk", avg(data.risk_score));

    setText(
        "summaryCrossings",
        data.risk_score.filter(x => x > 0.5).length
    );
}

/* =========================================
   LOAD TABLE
   ========================================= */
function loadHistoryTable(data) {
    const table = document.getElementById("liveDataTable");

    if (!table) {
        console.error("History table not found");
        return;
    }

    table.innerHTML = `
        <div class="table-row table-head">
            <div>ID</div>
            <div>Temperature</div>
            <div>Humidity</div>
            <div>Static Charge</div>
            <div>Voltage</div>
            <div>Risk Score</div>
            <div>Fault Status</div>
            <div>Timestamp</div>
            <div>Device ID</div>
        </div>
    `;

    data.timestamps.forEach((time, index) => {
        table.innerHTML += `
            <div class="table-row">
                <div>${index + 1}</div>
                <div>${data.temperature[index]} °C</div>
                <div>${data.humidity[index]} %</div>
                <div>${data.static_charge[index]} V</div>
                <div>${data.voltage[index]} V</div>
                <div>${data.risk_score[index]}</div>
                <div>${data.risk_score[index] > 0.5 ? "High" : "Safe"}</div>
                <div>${time}</div>
                <div>ESD-${index + 1}</div>
            </div>
        `;
    });
}