/**
 * My AgriNutrition - Advanced Analytics Engine
 * Renders performance telemetry, sales trends, and diagnostic visualizations.
 */

document.addEventListener("DOMContentLoaded", () => {
    // 🎨 Global Chart.js styling defaults
    Chart.defaults.color = '#64748b';
    Chart.defaults.borderColor = 'rgba(30, 41, 59, 0.5)';
    Chart.defaults.font.family = "'Inter', sans-serif";

    const baseOptions = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: { display: false }
        }
    };

    // Safe data retriever helper
    const getGlobalData = (key) => (typeof window[key] !== "undefined" && Array.isArray(window[key])) ? window[key] : [];

    // 1. 📈 Month-Wise Revenue Trend Chart
    const monthElem = document.getElementById('monthWiseTrendChart');
    if (monthElem) {
        const ctxMonth = monthElem.getContext('2d');
        const gradMonth = ctxMonth.createLinearGradient(0, 0, 0, 250);
        gradMonth.addColorStop(0, 'rgba(16, 185, 129, 0.2)');
        gradMonth.addColorStop(1, 'rgba(16, 185, 129, 0.0)');

        new Chart(ctxMonth, {
            type: 'line',
            data: {
                labels: getGlobalData('monthLabels'),
                datasets: [{
                    label: 'Monthly Net',
                    data: getGlobalData('monthData'),
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

    // 2. 📊 Year-Wise Revenue Trend Chart
    const yearElem = document.getElementById('yearWiseTrendChart');
    if (yearElem) {
        const ctxYear = yearElem.getContext('2d');
        const gradYear = ctxYear.createLinearGradient(0, 0, 0, 250);
        gradYear.addColorStop(0, 'rgba(6, 182, 212, 0.2)');
        gradYear.addColorStop(1, 'rgba(6, 182, 212, 0.0)');

        new Chart(ctxYear, {
            type: 'line',
            data: {
                labels: getGlobalData('yearLabels'),
                datasets: [{
                    label: 'Yearly Aggregate',
                    data: getGlobalData('yearData'),
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

    // 3. 👤 Executive Revenue Bar Chart
    const execElem = document.getElementById('execRevBarChart');
    if (execElem) {
        new Chart(execElem.getContext('2d'), {
            type: 'bar',
            data: {
                labels: getGlobalData('execLabels'),
                datasets: [{
                    data: getGlobalData('execData'),
                    backgroundColor: '#38bdf8',
                    borderRadius: 4,
                    barThickness: 10
                }]
            },
            options: {
                ...baseOptions,
                indexAxis: 'y',
                scales: {
                    x: { ticks: { display: false }, grid: { display: false } },
                    y: { grid: { display: false } }
                }
            }
        });
    }

    // 4. 🗺️ State-Wise Visits Chart
    const stateElem = document.getElementById('stateVisitsChart');
    if (stateElem) {
        new Chart(stateElem.getContext('2d'), {
            type: 'bar',
            data: {
                labels: getGlobalData('stateLabels'),
                datasets: [{
                    data: getGlobalData('stateData'),
                    backgroundColor: ['#3b82f6', '#f97316', '#a855f7', '#10b981'],
                    borderRadius: 4,
                    barThickness: 12
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                indexAxis: 'y',
                scales: {
                    x: { grid: { display: false }, ticks: { color: '#64748b' } },
                    y: { grid: { display: false }, ticks: { color: '#f1f5f9', font: { weight: 'bold' } } }
                }
            }
        });
    }

    // 5. 📦 Product Sales Donut Chart
    const prodElem = document.getElementById('prodSalesDonut');
    if (prodElem) {
        new Chart(prodElem.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: getGlobalData('prodLabels'),
                datasets: [{
                    data: getGlobalData('prodData'),
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

    // 6. 🩺 Diagnostic Field Problems Donut Chart
    const problemElem = document.getElementById('problemsDonut');
    if (problemElem) {
        new Chart(problemElem.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: getGlobalData('problemLabels'),
                datasets: [{
                    data: getGlobalData('problemData'),
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
});