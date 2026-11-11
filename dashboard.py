"""NSE Pulse – Streamlit Analytics & Monitoring Dashboard.

Interactive frontend for market data exploration, pipeline triggering,
quality score breakdown, and historical change detection.

Run with:
    streamlit run dashboard.py
"""

import json
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import streamlit as st

from app.config.settings import DatasetConfig, get_settings
from app.monitoring.health import PipelineHealthMonitor
from app.services.orchestrator import PipelineOrchestrator

# Set page configuration
st.set_page_config(
    page_title="NSE Pulse – Market Data Engineering",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    .main-header { font-size: 2.2rem; font-weight: 700; color: #38bdf8; margin-bottom: 0px; }
    .sub-header { color: #94a3b8; font-size: 1.0rem; margin-bottom: 20px; }
    .metric-card { background-color: #1e293b; padding: 15px; border-radius: 8px; border: 1px solid #334155; }
    .badge-healthy { color: #10b981; font-weight: bold; }
    .badge-degraded { color: #f59e0b; font-weight: bold; }
    .badge-unhealthy { color: #ef4444; font-weight: bold; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_app_settings():
    settings = get_settings()
    settings.ensure_directories()
    return settings


settings = get_app_settings()


# Helper to load latest CSV for a dataset
def load_dataset_csv(csv_prefix: str, execution_date: Optional[date] = None) -> Optional[pd.DataFrame]:
    if execution_date:
        filename = f"{csv_prefix}_{execution_date.strftime('%Y-%m-%d')}.csv"
        path = settings.output_dir / filename
        if path.exists():
            return pd.read_csv(path)

    # Fallback to latest matching file
    matching_files = sorted(settings.output_dir.glob(f"{csv_prefix}_*.csv"), reverse=True)
    if matching_files:
        return pd.read_csv(matching_files[0])
    return None


# Helper to load recent audit reports
def load_recent_reports(limit: int = 20):
    report_files = sorted(settings.reports_dir.glob("run_*.json"), reverse=True)[:limit]
    reports = []
    for rf in report_files:
        try:
            with open(rf, "r", encoding="utf-8") as f:
                reports.append(json.load(f))
        except Exception:
            continue
    return reports


# Sidebar Controls
st.sidebar.markdown("### ⚙️ Pipeline Control")

if st.sidebar.button("▶ Run All 4 Datasets Now", type="primary", use_container_width=True):
    with st.spinner("Executing pipeline across all 4 NSE datasets..."):
        orchestrator = PipelineOrchestrator(settings)
        report = orchestrator.run()
        if report.overall_status == "SUCCESS":
            st.sidebar.success(f"Run {report.run_id} completed successfully in {report.total_duration_seconds}s!")
        elif report.overall_status == "PARTIAL_SUCCESS":
            st.sidebar.warning(f"Run {report.run_id} completed with partial success ({report.datasets_succeeded}/4 succeeded).")
        else:
            st.sidebar.error(f"Run {report.run_id} failed.")
        st.rerun()

st.sidebar.markdown("---")
view_mode = st.sidebar.radio(
    "Navigation",
    [
        "📊 System Overview & Health",
        "🚀 Top Gainers & Losers",
        "⚡ Upper Band Hitters",
        "💥 Volume Gainers / Spurts",
        "🏆 52-Week High Equity",
        "📜 Historical Audit Reports",
    ],
)

st.sidebar.markdown("---")
st.sidebar.info(
    "**NSE Pulse v1.0.0**\n"
    "Production-grade pipeline for NSE India market data.\n\n"
    "• Atomic file staging\n"
    "• Rule-based validation\n"
    "• Failure isolation\n"
    "• Transparent quality scoring"
)


# Main Content Area
monitor = PipelineHealthMonitor(settings.reports_dir)
sys_health = monitor.get_system_health()

# ==============================================================================
# 1. System Overview & Health View
# ==============================================================================
if view_mode == "📊 System Overview & Health":
    st.markdown('<div class="main-header">📈 NSE Pulse System Overview</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Live pipeline status, data quality scores, and dataset availability</div>', unsafe_allow_html=True)

    # Top KPI Metrics
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        status_color = "badge-healthy" if sys_health.status == "HEALTHY" else ("badge-degraded" if sys_health.status == "DEGRADED" else "badge-unhealthy")
        st.markdown(f"**Pipeline Health:** <span class='{status_color}'>{sys_health.status}</span>", unsafe_allow_html=True)
        st.metric(label="System Status", value=sys_health.status)

    with c2:
        st.metric(label="Observed Pipeline Runs", value=sys_health.total_reports_analyzed)

    with c3:
        st.metric(label="Active Datasets", value=len(sys_health.datasets))

    with c4:
        db_text = "Enabled" if settings.db_enabled else "CSV-Only (Standalone)"
        st.metric(label="PostgreSQL Mode", value=db_text)

    st.markdown("---")

    # Dataset Status Cards
    st.subheader("Official NSE Datasets Status")
    cols = st.columns(4)

    dataset_keys = list(DatasetConfig.DATASETS.keys())
    for idx, key in enumerate(dataset_keys):
        cfg = DatasetConfig.get_config(key)
        h = sys_health.datasets.get(key)
        csv_df = load_dataset_csv(cfg["csv_prefix"])

        with cols[idx]:
            st.markdown(f"#### {cfg['name']}")
            if h and h.is_healthy:
                st.success("Status: Healthy")
            else:
                st.error("Status: Failed / Unhealthy")

            st.write(f"**Success Rate:** {h.success_rate_pct if h else 100}%")
            st.write(f"**Avg Records:** {h.avg_records_retrieved if h else 0}")
            st.write(f"**Quality Score:** {h.avg_quality_score if h and h.avg_quality_score else 'N/A'}")

            if csv_df is not None:
                st.download_button(
                    label=f"📥 Download CSV",
                    data=csv_df.to_csv(index=False),
                    file_name=f"{cfg['csv_prefix']}_{date.today().isoformat()}.csv",
                    mime="text/csv",
                    key=f"dl_{key}",
                    use_container_width=True,
                )

    st.markdown("---")

    # Recent Execution History
    st.subheader("Recent Execution Audit Trail")
    reports = load_recent_reports(limit=10)
    if reports:
        report_rows = []
        for r in reports:
            report_rows.append({
                "Run ID": r.get("run_id"),
                "Started At (UTC)": r.get("started_at", "")[:19].replace("T", " "),
                "Overall Status": r.get("overall_status"),
                "Succeeded": f"{r.get('datasets_succeeded', 0)}/{r.get('datasets_attempted', 0)}",
                "Failed": r.get("datasets_failed", 0),
                "Duration (s)": r.get("total_duration_seconds", 0.0),
            })
        st.dataframe(pd.DataFrame(report_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No execution reports found yet. Click 'Run All 4 Datasets Now' in the sidebar.")


# ==============================================================================
# 2. Top Gainers & Losers View
# ==============================================================================
elif view_mode == "🚀 Top Gainers & Losers":
    st.markdown('<div class="main-header">🚀 Top Gainers & Losers</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Source: <a href="https://www.nseindia.com/market-data/top-gainers-losers" target="_blank">NSE Official Top Gainers / Losers</a></div>',
        unsafe_allow_html=True,
    )

    df = load_dataset_csv("top_gainers_losers")
    if df is not None and not df.empty:
        c1, c2, c3 = st.columns(3)
        with c1:
            gainers_count = len(df[df["category"] == "gainer"]) if "category" in df.columns else 0
            st.metric("Total Gainers", gainers_count)
        with c2:
            losers_count = len(df[df["category"] == "loser"]) if "category" in df.columns else 0
            st.metric("Total Losers", losers_count)
        with c3:
            st.metric("Total Tracked", len(df))

        # Visual Chart: % Change
        if "symbol" in df.columns and "pct_change" in df.columns:
            st.subheader("Price Movement (% Change)")
            chart_df = df[["symbol", "pct_change"]].set_index("symbol").sort_values("pct_change", ascending=False)
            st.bar_chart(chart_df, height=300)

        st.subheader("Data Records")
        st.dataframe(df, use_container_width=True)

        st.download_button(
            "📥 Export to CSV",
            data=df.to_csv(index=False),
            file_name=f"top_gainers_losers_{date.today().isoformat()}.csv",
            mime="text/csv",
        )
    else:
        st.warning("No data found for Top Gainers & Losers. Run the pipeline from the sidebar to populate.")


# ==============================================================================
# 3. Upper Band Hitters View
# ==============================================================================
elif view_mode == "⚡ Upper Band Hitters":
    st.markdown('<div class="main-header">⚡ Upper Band Hitters</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Source: <a href="https://www.nseindia.com/market-data/upper-band-hitters" target="_blank">NSE Official Upper Band Hitters</a></div>',
        unsafe_allow_html=True,
    )

    df = load_dataset_csv("upper_band_hitters")
    if df is not None and not df.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Stocks at Upper Circuit", len(df))
        with c2:
            max_vol_stock = df.loc[df["traded_qty"].idxmax()]["symbol"] if "traded_qty" in df.columns and not df.empty else "N/A"
            st.metric("Highest Volume Circuit Stock", max_vol_stock)

        if "symbol" in df.columns and "traded_qty" in df.columns:
            st.subheader("Traded Quantity Volume Distribution")
            st.bar_chart(df[["symbol", "traded_qty"]].set_index("symbol"), height=300)

        st.subheader("Data Records")
        st.dataframe(df, use_container_width=True)

        st.download_button(
            "📥 Export to CSV",
            data=df.to_csv(index=False),
            file_name=f"upper_band_hitters_{date.today().isoformat()}.csv",
            mime="text/csv",
        )
    else:
        st.warning("No data found for Upper Band Hitters. Run the pipeline from the sidebar to populate.")


# ==============================================================================
# 4. Volume Gainers / Spurts View
# ==============================================================================
elif view_mode == "💥 Volume Gainers / Spurts":
    st.markdown('<div class="main-header">💥 Volume Gainers / Spurts</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Source: <a href="https://www.nseindia.com/market-data/volume-gainers-spurts" target="_blank">NSE Official Volume Spurts</a></div>',
        unsafe_allow_html=True,
    )

    df = load_dataset_csv("volume_gainers_spurts")
    if df is not None and not df.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Total Volume Spurts", len(df))
        with c2:
            max_spurt = f"{df['volume_change_pct'].max()}%" if "volume_change_pct" in df.columns and not df.empty else "N/A"
            st.metric("Peak Volume Jump", max_spurt)

        if "symbol" in df.columns and "volume_change_pct" in df.columns:
            st.subheader("Volume Spike Percentage")
            st.bar_chart(df[["symbol", "volume_change_pct"]].set_index("symbol"), height=300)

        st.subheader("Data Records")
        st.dataframe(df, use_container_width=True)

        st.download_button(
            "📥 Export to CSV",
            data=df.to_csv(index=False),
            file_name=f"volume_gainers_spurts_{date.today().isoformat()}.csv",
            mime="text/csv",
        )
    else:
        st.warning("No data found for Volume Gainers / Spurts. Run the pipeline from the sidebar to populate.")


# ==============================================================================
# 5. 52-Week High Equity View
# ==============================================================================
elif view_mode == "🏆 52-Week High Equity":
    st.markdown('<div class="main-header">🏆 52-Week High – Equity Market</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sub-header">Source: <a href="https://www.nseindia.com/market-data/52-week-high-equity-market" target="_blank">NSE Official 52-Week High</a></div>',
        unsafe_allow_html=True,
    )

    df = load_dataset_csv("52_week_high_equity")
    if df is not None and not df.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Stocks at 52-Week High", len(df))
        with c2:
            highest_priced = df.loc[df["ltp"].idxmax()]["symbol"] if "ltp" in df.columns and not df.empty else "N/A"
            st.metric("Highest Priced Stock", highest_priced)

        if "symbol" in df.columns and "ltp" in df.columns and "low_52_week" in df.columns:
            st.subheader("Current LTP vs 52-Week Low Comparison")
            st.bar_chart(df[["symbol", "ltp", "low_52_week"]].set_index("symbol"), height=300)

        st.subheader("Data Records")
        st.dataframe(df, use_container_width=True)

        st.download_button(
            "📥 Export to CSV",
            data=df.to_csv(index=False),
            file_name=f"52_week_high_equity_{date.today().isoformat()}.csv",
            mime="text/csv",
        )
    else:
        st.warning("No data found for 52-Week High Equity. Run the pipeline from the sidebar to populate.")


# ==============================================================================
# 6. Historical Audit Reports View
# ==============================================================================
elif view_mode == "📜 Historical Audit Reports":
    st.markdown('<div class="main-header">📜 Execution Audit Reports</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">Inspect machine-readable JSON execution summaries, validation issues, and quality scores</div>', unsafe_allow_html=True)

    reports = load_recent_reports(limit=30)
    if reports:
        report_options = [f"Run {r.get('run_id')} ({r.get('started_at', '')[:19].replace('T', ' ')}) - {r.get('overall_status')}" for r in reports]
        selected_option = st.selectbox("Select Pipeline Run", report_options)
        selected_index = report_options.index(selected_option)
        selected_report = reports[selected_index]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Run ID", selected_report.get("run_id"))
        c2.metric("Overall Status", selected_report.get("overall_status"))
        c3.metric("Duration", f"{selected_report.get('total_duration_seconds')}s")
        c4.metric("Success Count", f"{selected_report.get('datasets_succeeded')}/{selected_report.get('datasets_attempted')}")

        st.subheader("Per-Dataset Breakdown")
        for ds_name, ds_info in selected_report.get("datasets", {}).items():
            with st.expander(f"{ds_name.upper()} - {ds_info.get('status')} ({ds_info.get('records_valid', 0)} valid records, Quality: {ds_info.get('quality_score', 0):.1f})"):
                st.write(f"**Records Fetched:** {ds_info.get('records_fetched')}")
                st.write(f"**Records Valid:** {ds_info.get('records_valid')}")
                st.write(f"**Records Rejected:** {ds_info.get('records_rejected')}")
                st.write(f"**Duplicates Removed:** {ds_info.get('duplicates_removed')}")
                st.write(f"**Quality Score:** {ds_info.get('quality_score')} (Grade {ds_info.get('quality_grade')})")
                st.write(f"**CSV File:** `{ds_info.get('csv_file_path')}`")

                if ds_info.get("validation_summary"):
                    st.json(ds_info["validation_summary"])

        st.subheader("Raw JSON Audit Payload")
        st.json(selected_report)
    else:
        st.info("No audit reports available.")

