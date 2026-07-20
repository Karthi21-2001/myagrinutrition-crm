/**
 * AgriNutrition Dashboard Analytics Script
 * Handles Chart.js initializations and dynamic data rendering.
 */

document.addEventListener("DOMContentLoaded", () => {
    // 1. Global Chart.js Styling Configurations
    Chart.defaults.color = '#64748b';
    Chart.defaults.borderColor = 'rgba(30, 41, 59, 0.5)';
    Chart.defaults.font.family = "'Inter', sans-serif";

    // Reusable Options Object
    const baseOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false }
        }
    };

    /**
     * Safe JSON Data Extractor
     * Reads embedded JSON script tags from Django DOM safely
     * @param {string} id - HTML Element ID
     * @returns {Array} Parsed JSON array or fallback empty array
     */
    const getJsonData = (id) => {
        try {
            const element = document.getElementById(id);
            return element ? JSON.parse(element.textContent) : [];
        } catch (error) {
            console.warn(`[Analytics Warning] Failed to parse JSON script ID "${id}":`, error);
            return [];
        }
    };

    // 2. Fetch Data Embeds from Django `json_script`
    const monthLabels = getJsonData("ds-month-labels");
    const monthData = getJsonData("ds-month-data");
    const yearLabels = getJsonData("ds-year-labels");
    const yearData = getJsonData("ds-year-data");
    const execLabels = getJsonData("ds-exec-labels");
    const execData = getJsonData("ds-exec-data");
    const prodLabels = getJsonData("ds-prod-labels");
    const prodData = getJsonData("ds-prod-data");
    const problemLabels = getJsonData("ds-problem-labels");
    const problemData = getJsonData("ds-problem-data");
    const stateLabels = getJsonData("ds-state-labels");
    const stateData = getJsonData("ds-state-data");

    // ----------------------------------------------------
    // 📈 3. MONTH-WISE TREND CHART (LINE)
    // ----------------------------------------------------
    const ctxMonth = document.getElementById('monthWiseTrendChart');
    if (ctxMonth) {
        const monthCanvas = ctxMonth.getContext('2d');
        const gradMonth = monthCanvas.createLinearGradient(0, 0, 0, 250);
        gradMonth.addColorStop(0, 'rgba(16, 185, 129, 0.25)');
        gradMonth.addColorStop(1, 'rgba(16, 185, 129, 0.0)');

        new Chart(ctxMonth, {
            type: 'line',
            data: {
                labels: monthLabels.length ? monthLabels : ['Jan', 'Feb', 'Mar', 'Apr', 'May'],
                datasets: [{
                    label: 'Monthly Revenue',
                    data: monthData.length ? monthData : [0, 0, 0, 0, 0],
                    borderColor: '#10b981',
                    backgroundColor: gradMonth,
                    borderWidth: 2.5,
                    tension: 0.38,
                    fill: true,
                    pointBackgroundColor: '#10b981',
                    pointHoverRadius: 6
                }]
            },
            options: {
                ...baseOptions,
                scales: {
                    x: { grid: { display: false } },
                    y: { 
                        ticks: { 
                            callback: (val) => '₹' + Number(val).toLocaleString('en-IN') 
                        } 
                    }
                }
            }
        });
    }

    // ----------------------------------------------------
    // 📈 4. YEAR-WISE TREND CHART (LINE)
    // ----------------------------------------------------
    const ctxYear = document.getElementById('yearWiseTrendChart');
    if (ctxYear) {
        const yearCanvas = ctxYear.getContext('2d');
        const gradYear = yearCanvas.createLinearGradient(0, 0, 0, 250);
        gradYear.addColorStop(0, 'rgba(6, 182, 212, 0.25)');
        gradYear.addColorStop(1, 'rgba(6, 182, 212, 0.0)');

        new Chart(ctxYear, {
            type: 'line',
            data: {
                labels: yearLabels.length ? yearLabels : ['2023', '2024', '2025', '2026'],
                datasets: [{
                    label: 'Yearly Aggregate',
                    data: yearData.length ? yearData : [0, 0, 0, 0],
                    borderColor: '#06b6d4',
                    backgroundColor: gradYear,
                    borderWidth: 2.5,
                    tension: 0.38,
                    fill: true,
                    pointBackgroundColor: '#06b6d4',
                    pointHoverRadius: 6
                }]
            },
            options: {
                ...baseOptions,
                scales: {
                    x: { grid: { display: false } },
                    y: { 
                        ticks: { 
                            callback: (val) => '₹' + Number(val).toLocaleString('en-IN') 
                        } 
                    }
                }
            }
        });
    }

    // ----------------------------------------------------
    // 📊 5. EXECUTIVE REVENUE CHART (HORIZONTAL BAR)
    // ----------------------------------------------------
    const ctxExec = document.getElementById('execRevBarChart');
    if (ctxExec) {
        new Chart(ctxExec, {
            type: 'bar',
            data: {
                labels: execLabels,
                datasets: [{
                    data: execData,
                    backgroundColor: '#38bdf8',
                    borderRadius: 4,
                    barThickness: 10
                }]
            },
            options: {
                ...baseOptions,
                indexAxis: 'y',
                scales: {
                    x: { ticks: { display: false }, grid: { display: false } }
                }
            }
        });
    }

    // ----------------------------------------------------
    // 🍩 6. PRODUCT ALLOCATION (DONUT)
    // ----------------------------------------------------
    const ctxProd = document.getElementById('prodSalesDonut');
    if (ctxProd) {
        new Chart(ctxProd, {
            type: 'doughnut',
            data: {
                labels: prodLabels,
                datasets: [{
                    data: prodData,
                    backgroundColor: ['#06b6d4', '#3b82f6', '#6366f1', '#a855f7', '#475569'],
                    borderWidth: 0
                }]
            },
            options: {
                ...baseOptions,
                cutout: '75%',
                plugins: {
                    legend: {
                        display: true,
                        position: 'bottom',
                        labels: { boxWidth: 8, padding: 10, font: { size: 9 }, color: '#94a3b8' }
                    }
                }
            }
        });
    }

    // ----------------------------------------------------
    // 🍩 7. FIELD PROBLEMS OBSERVED (DONUT)
    // ----------------------------------------------------
    const ctxProblem = document.getElementById('problemsDonut');
    if (ctxProblem) {
        new Chart(ctxProblem, {
            type: 'doughnut',
            data: {
                labels: problemLabels,
                datasets: [{
                    data: problemData,
                    backgroundColor: ['#f43f5e', '#f59e0b', '#10b981', '#06b6d4', '#475569'],
                    borderWidth: 0
                }]
            },
            options: {
                ...baseOptions,
                cutout: '75%',
                plugins: {
                    legend: {
                        display: true,
                        position: 'bottom',
                        labels: { boxWidth: 8, padding: 10, font: { size: 9 }, color: '#94a3b8' }
                    }
                }
            }
        });
    }

    // ----------------------------------------------------
    // 🗺️ 8. STATE VISITS CHART (HORIZONTAL BAR)
    // ----------------------------------------------------
    const ctxState = document.getElementById('stateVisitsChart');
    if (ctxState) {
        new Chart(ctxState, {
            type: 'bar',
            data: {
                labels: stateLabels,
                datasets: [{
                    data: stateData,
                    backgroundColor: ['#3b82f6', '#f97316', '#a855f7', '#10b981'],
                    borderRadius: 4,
                    barThickness: 12
                }]
            },
            options: {
                ...baseOptions,
                indexAxis: 'y',
                scales: {
                    x: { grid: { display: false }, ticks: { color: '#64748b' } },
                    y: { grid: { display: false }, ticks: { color: '#f1f5f9', font: { weight: 'bold' } } }
                }
            }
        });
    }
});
