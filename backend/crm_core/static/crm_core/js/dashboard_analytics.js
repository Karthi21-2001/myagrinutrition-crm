/**
 * MY AGRINUTRITION CRM - Analytical Canvas Engine
 * Generates Power BI style chart elements over DOM canvas hooks.
 * Location: C:\Users\USER\OneDrive\Desktop\CRM_Project\backend\crm_core\static\crm_core\js\dashboard.js
 */

// Global declarations to hold chart references for async updates
window.barChartEngine = null;
window.pieChartEngine = null;
window.yearChartEngine = null;
window.monthChartEngine = null;

document.addEventListener("DOMContentLoaded", function () {
    // ---------------------------------------------------------
    // 1. Initial Chart Initializations (Mounting Canvas Engines)
    // ---------------------------------------------------------

    // Fallback safe defaults if Django database query arrays are empty initially
    const initialLabels = (typeof rawChartLabels !== 'undefined' && rawChartLabels.length) ? rawChartLabels : ["Namakkal", "Coimbatore", "Salem"];
    const initialValues = (typeof rawChartData !== 'undefined' && rawChartData.length) ? rawChartData : [12, 19, 7];

    // Bar Chart Engine Initialization
    const ctxBar = document.getElementById('districtBarChart')?.getContext('2d');
    if (ctxBar) {
        window.barChartEngine = new Chart(ctxBar, {
            type: 'bar',
            data: {
                labels: initialLabels,
                datasets: [{
                    label: 'Visits Logged',
                    data: initialValues,
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
    }

    // Pie/Doughnut Chart Engine Initialization
    const ctxPie = document.getElementById('visitPieChart')?.getContext('2d');
    if (ctxPie) {
        window.pieChartEngine = new Chart(ctxPie, {
            type: 'doughnut',
            data: {
                labels: initialLabels,
                datasets: [{
                    data: initialValues,
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
    }

    // Year Revenue Chart Engine Initialization
    const ctxYear = document.getElementById('yearRevenueChart')?.getContext('2d');
    if (ctxYear) {
        window.yearChartEngine = new Chart(ctxYear, {
            type: 'line',
            data: { labels: [], datasets: [{ label: 'Revenue Growth', data: [], borderColor: '#fbbf24', backgroundColor: 'rgba(251, 191, 36, 0.1)', borderWidth: 2, tension: 0.3, fill: true }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { color: '#334155' }, ticks: { color: '#94a3b8' } }, x: { grid: { color: '#334155' }, ticks: { color: '#94a3b8' } } } }
        });
    }

    // Month Revenue Chart Engine Initialization
    const ctxMonth = document.getElementById('monthRevenueChart')?.getContext('2d');
    if (ctxMonth) {
        window.monthChartEngine = new Chart(ctxMonth, {
            type: 'line',
            data: { labels: [], datasets: [{ label: 'Monthly Cycles', data: [], borderColor: '#34d399', backgroundColor: 'rgba(52, 211, 153, 0.1)', borderWidth: 2, tension: 0.3, fill: true }] },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { color: '#334155' }, ticks: { color: '#94a3b8' } }, x: { grid: { color: '#334155' }, ticks: { color: '#94a3b8' } } } }
        });
    }

    // ---------------------------------------------------------
    // 2. Setup Event Listeners on HTML Filter Selectors
    // ---------------------------------------------------------
    const filterSelectors = ['stateSelect', 'countrySelect', 'districtSelect', 'executiveSelect', 'businessTypeSelect', 'monthSelect', 'yearSelect'];
    filterSelectors.forEach(id => {
        document.getElementById(id)?.addEventListener('change', applyFilters);
    });

    // Run telemetry fetch on load to sync empty line charts
    applyFilters();
});

// ---------------------------------------------------------
// 3. Dynamic Async API Dispatcher (The Filter Logic)
// ---------------------------------------------------------
function applyFilters() {
    // Gather values from HTML nodes using explicit DOM element IDs
    const state = document.getElementById('stateSelect')?.value || 'All';
    const country = document.getElementById('countrySelect')?.value || 'All';
    const district = document.getElementById('districtSelect')?.value || 'All';
    const executive = document.getElementById('executiveSelect')?.value || 'All';
    const month = document.getElementById('monthSelect')?.value || 'All';
    const year = document.getElementById('yearSelect')?.value || 'All';
    const businessType = document.getElementById('businessTypeSelect')?.value || 'All';

    // Construct the query parameter string dynamically
    const queryParams = new URLSearchParams({
        state: state,
        country: country,
        district: district,
        executive: executive,
        month: month,
        year: year,
        business_type: businessType
    });

    // Dispatch AJAX fetch context payload
    fetch(`${window.location.pathname}?${queryParams.toString()}`, {
        headers: {
            'X-Requested-With': 'XMLHttpRequest'
        }
    })
    .then(response => {
        if (!response.ok) throw new Error("Telemetry refresh fault generated.");
        return response.json();
    })
    .then(data => {
        // 📊 Update Graph 1: Field Visit Frequency Bar Chart
        if (window.barChartEngine) {
            window.barChartEngine.data.labels = data.labels && data.labels.length ? data.labels : ['No Visits Found'];
            window.barChartEngine.data.datasets[0].data = data.values && data.values.length ? data.values : [0];
            window.barChartEngine.update();
        }

        // 🎯 Update Graph 2: Zone-wise Breakdown Doughnut Chart
        if (window.pieChartEngine) {
            window.pieChartEngine.data.labels = data.zone_labels && data.zone_labels.length ? data.zone_labels : ['No Data Found'];
            window.pieChartEngine.data.datasets[0].data = data.zone_data && data.zone_data.length ? data.zone_data : [0];
            window.pieChartEngine.update();
        }

        // 📈 Update Graph 3: Year-wise Revenue Trends Line Chart
        if (window.yearChartEngine) {
            window.yearChartEngine.data.labels = data.year_labels && data.year_labels.length ? data.year_labels : ['No Trends'];
            window.yearChartEngine.data.datasets[0].data = data.year_data && data.year_data.length ? data.year_data : [0];
            window.yearChartEngine.update();
        }

        // 📅 Update Graph 4: Month-wise Revenue Cycle Line Chart
        if (window.monthChartEngine) {
            window.monthChartEngine.data.labels = data.month_labels && data.month_labels.length ? data.month_labels : ['No Data'];
            window.monthChartEngine.data.datasets[0].data = data.month_data && data.month_data.length ? data.month_data : [0];
            window.monthChartEngine.update();
        }
    })
    .catch(error => {
        console.error("Critical error cycle updates inside dynamic asset engine:", error);
    });
}
