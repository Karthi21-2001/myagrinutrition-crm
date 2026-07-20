{% load static %}
<!DOCTYPE html>
<html lang="en" class="h-full bg-[#0b0f19] text-slate-100">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My AgriNutrition - Analytics & Visit Report</title>
    
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://cdn.tailwindcss.com"></script>

    <style>
        body { font-family: 'Inter', sans-serif; }
        .custom-scrollbar::-webkit-scrollbar { width: 6px; height: 6px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: #0b0f19; }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: #334155; border-radius: 9999px; }
        
        input[type="date"]::-webkit-calendar-picker-indicator {
            filter: invert(0.8);
            cursor: pointer;
        }
    </style>
</head>
<body class="min-h-full flex flex-col antialiased bg-[#0b0f19] text-slate-100 pb-12 custom-scrollbar">

    <!-- TOP NAVIGATION & FILTER BAR -->
    <header class="border-b border-slate-800 bg-[#131c2e] sticky top-0 z-50 px-6 py-4 shadow-md">
        <div class="max-w-[1600px] mx-auto flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
            <div>
                <h1 class="text-xl font-black tracking-tight text-white uppercase flex items-center gap-2">
                    <span class="text-cyan-400"><i class="fa-solid fa-chart-pie"></i></span>
                    My AgriNutrition Analytics
                </h1>
                <p class="text-xs text-slate-400 font-medium mt-0.5">Real-time data synchronization from Field Visit Logs</p>
            </div>
            
            <form method="GET" action="" class="flex flex-wrap items-center gap-2.5 w-full md:w-auto text-xs font-semibold">
                <select name="executive" onchange="this.form.submit()" class="bg-[#0b0f19] border border-slate-800 text-slate-200 font-bold rounded-lg px-3 py-2 cursor-pointer focus:border-cyan-500 outline-none min-w-[160px]">
                    <option value="ALL" {% if selected_executive == "ALL" or not selected_executive %}selected{% endif %}>👥 All Executives</option>
                    {% for exec in executives_list %}
                        <option value="{{ exec.id }}" {% if selected_executive == exec.id|stringformat:"s" %}selected{% endif %}>👤 {{ exec.get_full_name|default:exec.username }}</option>
                    {% endfor %}
                </select>

                <div class="relative flex items-center bg-[#0b0f19] border border-slate-800 rounded-lg px-3 py-2">
                    <input type="date" name="start_date" value="{{ start_date|default:'' }}" onchange="this.form.submit()" class="bg-transparent text-slate-200 outline-none font-medium cursor-pointer [color-scheme:dark]">
                </div>
                <div class="relative flex items-center bg-[#0b0f19] border border-slate-800 rounded-lg px-3 py-2">
                    <input type="date" name="end_date" value="{{ end_date|default:'' }}" onchange="this.form.submit()" class="bg-transparent text-slate-200 outline-none font-medium cursor-pointer [color-scheme:dark]">
                </div>
                
                <select name="sector" onchange="this.form.submit()" class="bg-[#0b0f19] border border-slate-800 text-slate-200 rounded-lg px-3 py-2 cursor-pointer focus:border-cyan-500 outline-none">
                    <option value="ALL" {% if selected_sector == "ALL" or not selected_sector %}selected{% endif %}>All Sectors</option>
                    <option value="POULTRY" {% if selected_sector == "POULTRY" %}selected{% endif %}>🐓 Poultry Sector</option>
                    <option value="AQUA" {% if selected_sector == "AQUA" %}selected{% endif %}>🐟 Aqua Sector</option>
                </select>
                
                <a href="{% url 'export_excel' %}" class="bg-cyan-600 hover:bg-cyan-700 text-white px-4 py-2 rounded-lg transition font-bold flex items-center gap-1.5 ml-auto md:ml-0 shadow-md">
                    <i class="fa-solid fa-file-excel"></i> Export Matrix
                </a>
            </form>
        </div>
    </header>

    <!-- CORE CONTAINER -->
    <main class="flex-1 max-w-[1600px] w-full mx-auto px-6 space-y-6 mt-6">

        <!-- SYSTEM TELEMETRY BAR -->
        <div class="flex justify-between items-center border-b border-slate-800 pb-3">
            <h2 class="text-xs font-bold text-slate-300 tracking-wider uppercase flex items-center gap-2">
                <i class="fa-solid fa-tower-cell text-emerald-400"></i>
                Live Management Performance & Pipeline Telemetry
            </h2>
            <span class="text-[10px] text-slate-400 bg-slate-800/80 px-2.5 py-1 rounded border border-slate-700/50 font-mono">
                System Status: <span class="text-emerald-400 font-bold">ONLINE</span>
            </span>
        </div>

        <!-- KPI CARDS GRID -->
        <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
            <!-- Card 1 -->
            <div class="bg-[#131c2e] border border-slate-800 rounded-xl p-4 flex flex-col justify-between shadow-md h-32">
                <div class="flex justify-between items-center text-slate-400">
                    <span class="text-[10px] font-bold uppercase tracking-wider">Total Visits Logged</span>
                    <i class="fa-solid fa-folder-open text-sky-400"></i>
                </div>
                <h3 class="text-2xl font-black text-white">{{ total_visits|default:"0" }}</h3>
                <span class="text-[10px] text-emerald-400 font-bold"><i class="fa-solid fa-caret-up"></i> {{ visits_growth|default:"0%" }}</span>
            </div>
            
            <!-- Card 2 -->
            <div class="bg-[#131c2e] border border-slate-800 rounded-xl p-4 flex flex-col justify-between shadow-md h-32">
                <div class="flex justify-between items-center text-slate-400">
                    <span class="text-[10px] font-bold uppercase tracking-wider">Active Executives</span>
                    <i class="fa-solid fa-user-tie text-violet-400"></i>
                </div>
                <h3 class="text-2xl font-black text-white">{{ total_executives|default:"0" }}</h3>
                <span class="text-[10px] text-slate-400 font-medium">Live Tracking Active</span>
            </div>

            <!-- Card 3 -->
            <div class="bg-[#131c2e] border border-slate-800 rounded-xl p-4 flex flex-col justify-between shadow-md h-32">
                <div class="flex justify-between items-center text-slate-400">
                    <span class="text-[10px] font-bold uppercase tracking-wider">Farms Covered</span>
                    <i class="fa-solid fa-wheat-api text-amber-400"></i>
                </div>
                <h3 class="text-2xl font-black text-white">{{ total_farms|default:"0" }}</h3>
                <span class="text-[10px] text-emerald-400 font-bold"><i class="fa-solid fa-caret-up"></i> {{ farms_expansion|default:"0%" }} expansion</span>
            </div>

            <!-- Card 4 -->
            <div class="bg-[#131c2e] border border-slate-800 rounded-xl p-4 flex flex-col justify-between shadow-md h-32">
                <div class="flex justify-between items-center text-slate-400">
                    <span class="text-[10px] font-bold uppercase tracking-wider">Total Orders Qty</span>
                    <i class="fa-solid fa-boxes-stacked text-orange-400"></i>
                </div>
                <h3 class="text-2xl font-black text-white">{{ total_qty|default:"0" }} <span class="text-xs font-normal text-slate-400">Units</span></h3>
                <span class="text-[10px] text-emerald-400 font-bold"><i class="fa-solid fa-caret-up"></i> {{ qty_velocity|default:"0%" }} velocity</span>
            </div>

            <!-- Card 5 -->
            <div class="bg-[#131c2e] border border-emerald-500/30 rounded-xl p-4 flex flex-col justify-between shadow-md h-32">
                <div class="flex justify-between items-center text-slate-400">
                    <span class="text-[10px] font-bold uppercase tracking-wider">Confirmed Revenue</span>
                    <i class="fa-solid fa-indian-rupee-sign text-emerald-400"></i>
                </div>
                <h3 class="text-2xl font-black text-emerald-400">₹{{ total_revenue|default:"0.00" }}</h3>
                <span class="text-[10px] text-emerald-400 font-bold"><i class="fa-solid fa-caret-up"></i> {{ revenue_growth|default:"0%" }} Growth</span>
            </div>

            <!-- Card 6 -->
            <div class="bg-[#131c2e] border border-slate-800 rounded-xl p-4 flex flex-col justify-between shadow-md h-32">
                <div class="flex justify-between items-center text-slate-400">
                    <span class="text-[10px] font-bold uppercase tracking-wider">Avg Order Value</span>
                    <i class="fa-solid fa-calculator text-cyan-400"></i>
                </div>
                <h3 class="text-2xl font-black text-white">₹{{ avg_revenue|default:"0" }}</h3>
                <span class="text-[10px] text-emerald-400 font-bold"><i class="fa-solid fa-caret-up"></i> {{ avg_growth|default:"0%" }}</span>
            </div>
        </div>

        <!-- CHARTS LAYER 1 -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div class="bg-[#131c2e] p-5 rounded-xl border border-slate-800 flex flex-col h-80 shadow-md">
                <div class="flex justify-between items-center mb-4">
                    <div>
                        <h3 class="text-xs font-bold text-white uppercase tracking-wider">Month-Wise Revenue Review</h3>
                        <p class="text-[10px] text-slate-400">Fiscal performance scaling across active financial months</p>
                    </div>
                    <span class="text-[10px] text-emerald-400 font-bold bg-emerald-500/10 px-2 py-0.5 border border-emerald-500/20 rounded">Monthly Ledger</span>
                </div>
                <div class="relative flex-1 w-full min-h-0">
                    <canvas id="monthWiseTrendChart"></canvas>
                </div>
            </div>

            <div class="bg-[#131c2e] p-5 rounded-xl border border-slate-800 flex flex-col h-80 shadow-md">
                <div class="flex justify-between items-center mb-4">
                    <div>
                        <h3 class="text-xs font-bold text-white uppercase tracking-wider">Year-Wise Revenue Review</h3>
                        <p class="text-[10px] text-slate-400">Historical macro conversion comparison parameters</p>
                    </div>
                    <span class="text-[10px] text-cyan-400 font-bold bg-cyan-500/10 px-2 py-0.5 border border-cyan-500/20 rounded">Yearly Ledger</span>
                </div>
                <div class="relative flex-1 w-full min-h-0">
                    <canvas id="yearWiseTrendChart"></canvas>
                </div>
            </div>
        </div>

    </main>

    <!-- DATA EMBEDDING -->
    {{ month_labels_json|json_script:"ds-month-labels" }}
    {{ month_data_json|json_script:"ds-month-data" }}
    {{ year_labels_json|json_script:"ds-year-labels" }}
    {{ year_data_json|json_script:"ds-year-data" }}

    <!-- CHART INITIALIZATION -->
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script>
        document.addEventListener("DOMContentLoaded", () => {
            const getJsonData = (id) => {
                try {
                    return JSON.parse(document.getElementById(id).textContent) || [];
                } catch {
                    return [];
                }
            };

            const monthLabels = getJsonData("ds-month-labels");
            const monthData = getJsonData("ds-month-data");
            const yearLabels = getJsonData("ds-year-labels");
            const yearData = getJsonData("ds-year-data");

            Chart.defaults.color = '#64748b';
            Chart.defaults.borderColor = '#1e293b';

            // Month Line Chart
            const ctxMonth = document.getElementById('monthWiseTrendChart');
            if (ctxMonth) {
                new Chart(ctxMonth, {
                    type: 'line',
                    data: {
                        labels: monthLabels.length ? monthLabels : ['Jan', 'Feb', 'Mar', 'Apr', 'May'],
                        datasets: [{
                            label: 'Revenue',
                            data: monthData.length ? monthData : [0, 0, 0, 0, 0],
                            borderColor: '#10b981',
                            backgroundColor: 'rgba(16, 185, 129, 0.1)',
                            fill: true,
                            tension: 0.3
                        }]
                    },
                    options: { responsive: true, maintainAspectRatio: false }
                });
            }

            // Year Line Chart
            const ctxYear = document.getElementById('yearWiseTrendChart');
            if (ctxYear) {
                new Chart(ctxYear, {
                    type: 'line',
                    data: {
                        labels: yearLabels.length ? yearLabels : ['2023', '2024', '2025', '2026'],
                        datasets: [{
                            label: 'Revenue',
                            data: yearData.length ? yearData : [0, 0, 0, 0],
                            borderColor: '#06b6d4',
                            backgroundColor: 'rgba(6, 182, 212, 0.1)',
                            fill: true,
                            tension: 0.3
                        }]
                    },
                    options: { responsive: true, maintainAspectRatio: false }
                });
            }
        });
    </script>
</body>
</html>
