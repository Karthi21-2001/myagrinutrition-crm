/**
 * MY AGRINUTRITION CRM - Analytical Canvas Engine
 * Generates Power BI style chart elements over DOM canvas hooks.
 */

document.addEventListener("DOMContentLoaded", function () {
    // Fallback safe defaults if Django database query arrays are empty
    const labels = rawChartLabels.length ? rawChartLabels : ["Namakkal", "Coimbatore", "Salem"];
    const dataValues = rawChartData.length ? rawChartData : [12, 19, 7];

    // 1. Bar Chart Engine Initialization
    const ctxBar = document.getElementById('districtBarChart').getContext('2d');
    new Chart(ctxBar, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Visits Logged',
                data: dataValues,
                backgroundColor: '#38bdf8',
                borderColor: '#0284c7',
                borderWidth: 1,
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, grid: { color: '#334155' }, ticks: { color: '#94a3b8' } },
                x: { grid: { display: false }, ticks: { color: '#94a3b8' } }
            }
        }
    });

    // 2. Pie Chart Engine Initialization
    const ctxPie = document.getElementById('visitPieChart').getContext('2d');
    new Chart(ctxPie, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: dataValues,
                backgroundColor: ['#38bdf8', '#4ade80', '#fbbf24', '#f87171', '#a78bfa'],
                borderWidth: 2,
                borderColor: '#1e293b'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'right', labels: { color: '#cbd5e1', font: { size: 12 } } }
            }
        }
    });
});
