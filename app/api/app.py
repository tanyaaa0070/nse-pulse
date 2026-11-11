"""FastAPI Application Factory for NSE Pulse.

Provides RESTful API and interactive visual monitoring dashboard.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.api.routes import router
from app.config.settings import get_settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings = get_settings()
    settings.ensure_directories()

    app = FastAPI(
        title="NSE Pulse – Market Data Engineering Platform",
        description=(
            "Production-quality data pipeline platform for automated retrieval, "
            "validation, normalization, and storage of official NSE India market datasets."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include REST routes
    app.include_router(router, prefix="/api/v1")
    # Also mount router without prefix for direct root access matching assignment spec
    app.include_router(router)

    # Interactive Dashboard Route
    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/dashboard", response_class=HTMLResponse, include_in_schema=False)
    def dashboard() -> HTMLResponse:
        """Render interactive HTML monitoring dashboard."""
        html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>NSE Pulse – Market Data Engineering Platform</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
  <style>
    :root {
      --bg-dark: #0f172a;
      --card-bg: #1e293b;
      --accent: #38bdf8;
      --success: #10b981;
      --warning: #f59e0b;
      --danger: #ef4444;
      --text: #f8fafc;
      --text-muted: #94a3b8;
    }
    body { background-color: var(--bg-dark); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    .navbar { background-color: var(--card-bg); border-bottom: 1px solid #334155; }
    .card { background-color: var(--card-bg); border: 1px solid #334155; border-radius: 8px; margin-bottom: 20px; }
    .badge-success { background-color: var(--success); color: #fff; }
    .badge-danger { background-color: var(--danger); color: #fff; }
    .badge-warning { background-color: var(--warning); color: #000; }
    .table-dark { background-color: var(--card-bg); }
    .btn-pulse { background-color: var(--accent); color: #000; font-weight: 600; }
    .btn-pulse:hover { background-color: #0284c7; color: #fff; }
    .stat-val { font-size: 2rem; font-weight: 700; color: var(--accent); }
    .stat-label { font-size: 0.85rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em; }
  </style>
</head>
<body>
  <nav class="navbar navbar-expand-lg navbar-dark px-4">
    <a class="navbar-brand d-flex align-items-center gap-2" href="#">
      <i class="fa-solid fa-chart-line text-info"></i>
      <span class="fw-bold">NSE Pulse</span>
      <span class="badge bg-secondary ms-2" style="font-size:0.7rem">v1.0.0</span>
    </a>
    <div class="ms-auto d-flex gap-2">
      <a href="/docs" class="btn btn-sm btn-outline-light"><i class="fa-solid fa-book me-1"></i> API Docs</a>
      <button onclick="triggerAllDownload()" class="btn btn-sm btn-pulse" id="btn-sync"><i class="fa-solid fa-cloud-arrow-down me-1"></i> Run Pipeline</button>
    </div>
  </nav>

  <div class="container-fluid py-4 px-4">
    <!-- Top Stats -->
    <div class="row g-3 mb-4">
      <div class="col-md-3">
        <div class="card p-3">
          <div class="stat-label">Pipeline Status</div>
          <div class="stat-val d-flex align-items-center gap-2" id="stat-status">
            <span class="spinner-border spinner-border-sm text-info"></span>
          </div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="card p-3">
          <div class="stat-label">Total Execution Runs</div>
          <div class="stat-val" id="stat-runs">-</div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="card p-3">
          <div class="stat-label">Active Datasets</div>
          <div class="stat-val" id="stat-datasets">4</div>
        </div>
      </div>
      <div class="col-md-3">
        <div class="card p-3">
          <div class="stat-label">Database Sync</div>
          <div class="stat-val" id="stat-db" style="font-size:1.5rem">-</div>
        </div>
      </div>
    </div>

    <!-- Dataset Cards -->
    <h5 class="fw-bold mb-3"><i class="fa-solid fa-layer-group me-2 text-info"></i> Official NSE Datasets</h5>
    <div class="row g-3 mb-4" id="dataset-cards">
      <div class="col-12 text-center py-4 text-muted"><span class="spinner-border text-info"></span> Loading datasets...</div>
    </div>

    <!-- Execution History -->
    <h5 class="fw-bold mb-3"><i class="fa-solid fa-clock-rotate-left me-2 text-info"></i> Recent Execution Runs</h5>
    <div class="card p-0">
      <div class="table-responsive">
        <table class="table table-dark table-hover mb-0 align-middle">
          <thead>
            <tr style="border-bottom: 2px solid #334155;">
              <th>Run ID</th>
              <th>Started (UTC)</th>
              <th>Status</th>
              <th>Succeeded</th>
              <th>Failed</th>
              <th>Duration</th>
            </tr>
          </thead>
          <tbody id="runs-table-body">
            <tr><td colspan="6" class="text-center py-3 text-muted">Loading execution history...</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <script>
    async function loadMetrics() {
      try {
        const res = await fetch('/metrics');
        const data = await res.json();
        
        const statusEl = document.getElementById('stat-status');
        const statusColor = data.system_status === 'HEALTHY' ? 'text-success' : (data.system_status === 'DEGRADED' ? 'text-warning' : 'text-danger');
        statusEl.innerHTML = `<span class="${statusColor}">${data.system_status}</span>`;
        
        document.getElementById('stat-runs').innerText = data.total_runs;
        document.getElementById('stat-datasets').innerText = data.datasets_active;
        document.getElementById('stat-db').innerHTML = data.database_connected 
          ? '<span class="text-success"><i class="fa-solid fa-circle-check"></i> Connected</span>'
          : '<span class="text-muted"><i class="fa-solid fa-database"></i> Optional / CSV Mode</span>';

        renderDatasetCards(data.dataset_health);
      } catch (e) {
        console.error(e);
      }
    }

    function renderDatasetCards(healthData) {
      const container = document.getElementById('dataset-cards');
      const names = {
        'top-gainers-losers': { title: 'Top Gainers & Losers', icon: 'fa-arrow-trend-up', url: 'https://www.nseindia.com/market-data/top-gainers-losers' },
        'upper-band-hitters': { title: 'Upper Band Hitters', icon: 'fa-bolt', url: 'https://www.nseindia.com/market-data/upper-band-hitters' },
        'volume-gainers-spurts': { title: 'Volume Gainers / Spurts', icon: 'fa-fire', url: 'https://www.nseindia.com/market-data/volume-gainers-spurts' },
        '52-week-high-equity': { title: '52-Week High Equity', icon: 'fa-trophy', url: 'https://www.nseindia.com/market-data/52-week-high-equity-market' }
      };

      let html = '';
      for (const [key, meta] of Object.entries(names)) {
        const h = healthData && healthData[key] ? healthData[key] : {};
        const isHealthy = h.is_healthy ?? true;
        const statusBadge = isHealthy 
          ? '<span class="badge badge-success">HEALTHY</span>'
          : '<span class="badge badge-danger">FAILED</span>';
        
        html += `
          <div class="col-md-3">
            <div class="card p-3 h-100">
              <div class="d-flex justify-content-between align-items-center mb-2">
                <i class="fa-solid ${meta.icon} text-info fs-4"></i>
                ${statusBadge}
              </div>
              <h6 class="fw-bold mb-1">${meta.title}</h6>
              <div class="text-muted small mb-2"><a href="${meta.url}" target="_blank" class="text-decoration-none text-info">NSE Source <i class="fa-solid fa-arrow-up-right-from-square" style="font-size:0.7rem"></i></a></div>
              <div class="mt-auto pt-2 border-top border-secondary">
                <div class="d-flex justify-content-between small text-muted">
                  <span>Success Rate:</span>
                  <span class="text-light fw-bold">${h.success_rate_pct ?? 100}%</span>
                </div>
                <div class="d-flex justify-content-between small text-muted">
                  <span>Avg Records:</span>
                  <span class="text-light fw-bold">${h.avg_records_retrieved ?? 0}</span>
                </div>
                <div class="d-flex justify-content-between small text-muted mb-3">
                  <span>Quality Score:</span>
                  <span class="text-light fw-bold">${h.avg_quality_score ? h.avg_quality_score + '/100' : 'N/A'}</span>
                </div>
                <button onclick="triggerDatasetDownload('${key}')" class="btn btn-sm btn-outline-info w-100"><i class="fa-solid fa-download me-1"></i> Run Dataset</button>
              </div>
            </div>
          </div>
        `;
      }
      container.innerHTML = html;
    }

    async function loadRuns() {
      try {
        const res = await fetch('/runs?limit=10');
        const runs = await res.json();
        const tbody = document.getElementById('runs-table-body');
        if (!runs.length) {
          tbody.innerHTML = '<tr><td colspan="6" class="text-center py-3 text-muted">No runs recorded yet. Click "Run Pipeline" above!</td></tr>';
          return;
        }

        tbody.innerHTML = runs.map(r => {
          const badge = r.overall_status === 'SUCCESS' 
            ? '<span class="badge badge-success">SUCCESS</span>'
            : (r.overall_status === 'PARTIAL_SUCCESS' ? '<span class="badge badge-warning">PARTIAL</span>' : '<span class="badge badge-danger">FAILED</span>');
          return `
            <tr>
              <td><code>${r.run_id}</code></td>
              <td>${r.started_at ? r.started_at.replace('T', ' ').substring(0, 19) : '-'}</td>
              <td>${badge}</td>
              <td><span class="text-success fw-bold">${r.datasets_succeeded}</span> / ${r.datasets_attempted}</td>
              <td><span class="${r.datasets_failed > 0 ? 'text-danger fw-bold' : 'text-muted'}">${r.datasets_failed}</span></td>
              <td>${r.total_duration_seconds}s</td>
            </tr>
          `;
        }).join('');
      } catch (e) {
        console.error(e);
      }
    }

    async function triggerAllDownload() {
      const btn = document.getElementById('btn-sync');
      const origText = btn.innerHTML;
      btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Running...';
      btn.disabled = true;
      try {
        await fetch('/download/all', { method: 'POST' });
        await loadMetrics();
        await loadRuns();
      } catch (e) {
        alert('Pipeline execution failed: ' + e);
      } finally {
        btn.innerHTML = origText;
        btn.disabled = false;
      }
    }

    async function triggerDatasetDownload(datasetName) {
      try {
        const res = await fetch(`/download/${datasetName}`, { method: 'POST' });
        const data = await res.json();
        alert(`Execution for ${datasetName}: ${data.status} (${data.records_valid || 0} valid records)`);
        await loadMetrics();
        await loadRuns();
      } catch (e) {
        alert('Error: ' + e);
      }
    }

    loadMetrics();
    loadRuns();
  </script>
</body>
</html>
"""
        return HTMLResponse(content=html_content)

    return app

