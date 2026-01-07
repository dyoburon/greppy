# Greppy Experiment: Chart Generation Search

**Date:** 2026-01-07
**Task:** Find all code related to chart generation logic
**Project:** datafeeds

## Timer Results

| Metric | Value |
|--------|-------|
| Duration | 1m 16s (76 seconds) |
| Input Tokens | 136 |
| Output Tokens | 264 |
| Total Tokens | 400 |
| Estimated Cost | $0.0218 |

## Queries Used

1. `greppy search "chart generation logic"`
2. `greppy search "chart rendering D3 visualization" -n 20`
3. `greppy exact "CHART_REGISTRY"`
4. `greppy search "D3 chart component render SVG" -n 15`
5. `greppy exact "D3ChartRenderer"`
6. `greppy exact "ChartView"`

## Results Summary

### Backend (Python - Chart Rendering)

**Core Chart System:**
- `backend/src/charts/base.py` - Main chart registry (`CHART_REGISTRY`) and `generate_chart()` function
- `backend/src/charts/__init__.py` - Chart module exports
- `backend/src/charts/chart_mapper.py` - Maps data to chart types

**Individual Chart Renderers:**
- `backend/src/charts/comparison_bar.py`
- `backend/src/charts/multi_line.py`
- `backend/src/charts/spread_area.py`
- `backend/src/charts/drawdown.py`
- `backend/src/charts/recovery_path.py`
- `backend/src/charts/relative_strength.py`
- `backend/src/charts/rolling_correlation.py`
- `backend/src/charts/range_band.py`
- `backend/src/charts/histogram.py`
- `backend/src/charts/scatter.py`
- `backend/src/charts/table.py`

**Pipeline Integration:**
- `backend/src/pipeline_v2/pipeline.py` - Main pipeline that generates chart data
- `backend/src/pipeline/output_engine.py` - Output formatting with charts
- `backend/src/routing/chart_intent_router.py` - Routes queries to appropriate chart types
- `backend/src/advanced_charts.py` - Advanced chart handling

**Special Use Cases:**
- `backend/src/questions_of_the_day/chart_config.py` - Chart config for daily questions

### Frontend (React/TypeScript - Chart Display)

**D3-based Rendering:**
- `frontend/components/charts/D3ChartRenderer.tsx:678` - Main D3 chart renderer component

**Data Visualization Views:**
- `frontend/components/fred/ChartView.tsx:87` - FRED data chart view with Recharts
- `frontend/components/fred/ChartEventsOverlay.tsx` - Events overlay for charts

**Chat Integration:**
- `frontend/components/ChatMessage.tsx:495` - Renders charts in chat messages using D3ChartRenderer

### Documentation
- `docs/newd3charts/implementation.md` - D3 charts implementation plan
- `docs/darkmodecharts/implementation.md` - Dark mode chart styling

## Notes

- Used a combination of semantic search (`greppy search`) and exact match (`greppy exact`) to cover both conceptual and specific code references
- 6 queries were sufficient to map out the entire chart generation architecture
- Total cost under $0.03 for comprehensive codebase exploration
