# RAIL / SIGNAL — Academic Mini Project Report Package

This directory contains the complete academic mini-project report for **RAIL / SIGNAL: Indian Railways Data Engineering and Analytics Pipeline**, prepared for **CA 1: Mini Project Report** at **Vivekanand Education Society's Institute of Technology (VESIT)**.

---

## 🎓 Academic Metadata
- **Student Name:** Prathamesh Shelar
- **Roll Number:** 65
- **Class:** D12A
- **Department:** Department of Computer Engineering
- **Institute:** Vivekanand Education Society's Institute of Technology (VESIT)
- **Year / Semester:** T.E. / Semester V
- **Academic Year:** 2026–2027
- **Subject:** Data Engineering (CA 1 Mini Project)
- **Faculty Guide:** Dr. Indu Dokare

---

## 📁 Deliverables Summary

| Deliverable | File Path | Format / Description |
|---|---|---|
| **Academic Report (PDF)** | [RAIL_SIGNAL_Mini_Project_Report.pdf](file:///D:/DE%20project/RAIL-SIGNAL/reports/RAIL_SIGNAL_Mini_Project_Report/RAIL_SIGNAL_Mini_Project_Report.pdf) | **24 Pages**, formal academic styling, embedded architecture diagrams, real screenshots, running headers/footers, and verified index. |
| **Academic Report (DOCX)** | [RAIL_SIGNAL_Mini_Project_Report.docx](file:///D:/DE%20project/RAIL-SIGNAL/reports/RAIL_SIGNAL_Mini_Project_Report/RAIL_SIGNAL_Mini_Project_Report.docx) | Fully editable Microsoft Word document with editable tables, embedded figures, and formal typography. |
| **Generation Script** | [generate_report.py](file:///D:/DE%20project/RAIL-SIGNAL/reports/RAIL_SIGNAL_Mini_Project_Report/generate_report.py) | Python automation script (`python-docx`, `win32com`, `pypdf`) to build DOCX and export native PDF. |
| **Architecture Diagram Script** | [generate_diagram.py](file:///D:/DE%20project/RAIL-SIGNAL/reports/RAIL_SIGNAL_Mini_Project_Report/assets/diagrams/generate_diagram.py) | High-resolution matplotlib script generating the 5-tier architecture diagram. |

---

## 🖼️ Included Assets & Evidence

### 1. Architectural & Institutional Diagrams (`assets/diagrams/`)
- `vesit_logo.png`: Official Vivekanand Education Society's Institute of Technology emblem.
- `01_system_architecture.png`: High-resolution 300 DPI architecture diagram detailing Data Sources, Ingestion/ETL, Columnar Lakehouse, PostgreSQL 16 ACID storage, FastAPI, Next.js 16 UI, and Governance.

### 2. Genuine Application Screenshots (`assets/screenshots/`)
All screenshots were captured live from the running services (`localhost:3000` and `127.0.0.1:8000`):
1. `01_main_dashboard.png`: Executive Overview Dashboard displaying 5 verified relational KPIs (`stations`: 8,988; `trains`: 5,207; `schedules`: 394,469; `journeys`: 1,875,000; Total: **2,283,664** rows).
2. `02_etl_workflow.png`: 8-Stage Interactive ETL Workflow and Execution Lineage Tracker.
3. `03_pipeline_catalog.png`: Enterprise Data Pipeline Catalog exposing all 5 registered execution pipelines.
4. `04_pipeline_history.png`: Pipeline Execution History Table with run status, duration, and pipeline name filtering.
5. `05_analytics_dashboard.png`: Train Performance and Punctuality Analytics Dashboard.
6. `06_validation_results.png`: Data Quality Audit Report and Quarantine Validation Breakdown.
7. `07_api_documentation.png`: Interactive OpenAPI (Swagger UI) Documentation console at `/docs`.
8. `08_backend_health.png`: Live FastAPI Backend Health Endpoint (`/api/health`) returning HTTP 200 with relational table counts.

---

## 🛠️ How to Regenerate the Report
To regenerate the documents from source:
```powershell
cd "D:\DE project\RAIL-SIGNAL"
python reports/RAIL_SIGNAL_Mini_Project_Report/generate_report.py
```
*Note: Requires Microsoft Word installed on Windows for native Word-to-PDF conversion via `win32com`.*
