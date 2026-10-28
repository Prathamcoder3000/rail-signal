"""
Architecture diagram generator for RAIL / SIGNAL Mini Project Report.
Generates high-resolution architecture diagram reflecting the genuine system components.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as patches

def generate_architecture_diagram():
    fig, ax = plt.subplots(figsize=(14, 8), dpi=300)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 9)
    ax.axis("off")

    # Colors
    bg_color = "#FFFFFF"
    fig.patch.set_facecolor(bg_color)
    
    c_source = "#E3F2FD"      # Light Blue
    c_ingest = "#E8F5E9"      # Light Green
    c_storage = "#FFF3E0"     # Light Orange
    c_api = "#EDE7F6"         # Light Purple
    c_ui = "#FCE4EC"          # Light Pink
    c_monitor = "#ECEFF1"     # Light Grey
    border_color = "#37474F"

    # Title
    ax.text(7, 8.5, "RAIL / SIGNAL — End-to-End System Architecture", 
            ha="center", va="center", fontsize=16, fontweight="bold", color="#1A237E")
    ax.text(7, 8.15, "Indian Railways Data Engineering, Verification & Analytical Intelligence Platform", 
            ha="center", va="center", fontsize=10, style="italic", color="#455A64")

    # 1. Data Sources Box
    box_src = patches.FancyBboxPatch((0.5, 3.8), 2.2, 3.8, boxstyle="round,pad=0.2",
                                     fc=c_source, ec="#1976D2", lw=1.5)
    ax.add_patch(box_src)
    ax.text(1.6, 7.3, "1. Raw Data Sources", ha="center", va="center", fontsize=11, fontweight="bold", color="#0D47A1")
    ax.text(1.6, 6.4, "DataMeet Timetable\n• schedules.json (82 MB)\n• stations.json (1.8 MB)\n• trains.json (14.8 MB)", 
            ha="center", va="center", fontsize=8.5, color="#263238")
    ax.text(1.6, 4.8, "Operational Journeys\n• ir_train.csv (337 MB)\n• ir_test.csv (76 MB)\n(1.875M Records)", 
            ha="center", va="center", fontsize=8.5, color="#263238")

    # Arrow 1 -> 2
    ax.annotate("", xy=(3.3, 5.7), xytext=(2.8, 5.7),
                arrowprops=dict(facecolor="#37474F", edgecolor="#37474F", width=1.5, headwidth=7))

    # 2. Ingestion & Transformation Box
    box_etl = patches.FancyBboxPatch((3.4, 3.8), 2.6, 3.8, boxstyle="round,pad=0.2",
                                     fc=c_ingest, ec="#388E3C", lw=1.5)
    ax.add_patch(box_etl)
    ax.text(4.7, 7.3, "2. Pipeline & ETL Engine", ha="center", va="center", fontsize=11, fontweight="bold", color="#1B5E20")
    ax.text(4.7, 6.3, "Stage 1: Preflight & Config\nStage 2: Schema Validation\nStage 3: Chunked Transform\nStage 4: Quarantine Engine\nStage 5: Post-Load Audit", 
            ha="center", va="center", fontsize=8.5, color="#263238")
    ax.text(4.7, 4.6, "Session Advisory Lock\n(Key: 842091238471)\nFail-Safe Autocommit Guard\nMulti-Table Overwrite Guard", 
            ha="center", va="center", fontsize=8, color="#1B5E20", fontweight="semibold")

    # Arrow 2 -> 3
    ax.annotate("", xy=(6.6, 5.7), xytext=(6.1, 5.7),
                arrowprops=dict(facecolor="#37474F", edgecolor="#37474F", width=1.5, headwidth=7))

    # 3. Storage Layer Box
    box_store = patches.FancyBboxPatch((6.7, 3.8), 2.6, 3.8, boxstyle="round,pad=0.2",
                                       fc=c_storage, ec="#F57C00", lw=1.5)
    ax.add_patch(box_store)
    ax.text(8.0, 7.3, "3. Authoritative Storage", ha="center", va="center", fontsize=11, fontweight="bold", color="#E65100")
    ax.text(8.0, 6.3, "PostgreSQL 16 Relational\n• stations (8,988)\n• trains (5,207)\n• schedules (394,469)\n• journey_train (1.50M)\n• journey_test (375K)\nTotal: 2,283,664 Rows", 
            ha="center", va="center", fontsize=8.5, color="#263238")
    ax.text(8.0, 4.5, "Columnar Data Lake\n• 5 Snappy Parquet Files\n(data/processed/*.parquet)", 
            ha="center", va="center", fontsize=8.5, color="#BF360C")

    # Arrow 3 -> 4
    ax.annotate("", xy=(9.9, 5.7), xytext=(9.4, 5.7),
                arrowprops=dict(facecolor="#37474F", edgecolor="#37474F", width=1.5, headwidth=7))

    # 4. Backend API Box
    box_api = patches.FancyBboxPatch((10.0, 3.8), 2.2, 3.8, boxstyle="round,pad=0.2",
                                     fc=c_api, ec="#7B1FA2", lw=1.5)
    ax.add_patch(box_api)
    ax.text(11.1, 7.3, "4. FastAPI Backend", ha="center", va="center", fontsize=11, fontweight="bold", color="#4A148C")
    ax.text(11.1, 6.3, "FastAPI Service (Port 8000)\n• /api/health (Relational)\n• /api/overview (Distributions)\n• /api/pipelines (5 Catalogs)\n• /api/pipeline/history\n• /api/trains (Search/Filter)\n• /api/quality/report\n• /docs (Interactive OpenAPI)", 
            ha="center", va="center", fontsize=8, color="#263238")
    ax.text(11.1, 4.4, "Psycopg2 Pooled Layer\nCORS Security Configured", 
            ha="center", va="center", fontsize=8, color="#4A148C", fontweight="semibold")

    # Arrow 4 -> 5 (Downwards to Frontend)
    ax.annotate("", xy=(11.1, 2.7), xytext=(11.1, 3.7),
                arrowprops=dict(facecolor="#37474F", edgecolor="#37474F", width=1.5, headwidth=7))

    # 5. Frontend Dashboard Box
    box_ui = patches.FancyBboxPatch((7.0, 0.7), 6.3, 1.9, boxstyle="round,pad=0.2",
                                    fc=c_ui, ec="#C2185B", lw=1.5)
    ax.add_patch(box_ui)
    ax.text(10.15, 2.3, "5. Next.js 16 Presentation & Intelligence Interface (Port 3000)", 
            ha="center", va="center", fontsize=11, fontweight="bold", color="#880E4F")
    ax.text(10.15, 1.45, "• Overview Dashboard (5 Verified Relational KPIs, State/Zone Distributions)\n• 8-Stage Interactive ETL Flow Execution & Lineage Tracker\n• 5-Pipeline Enterprise Catalog & History Table with Filtering\n• Real-Time Railway Analytics (Punctuality, Utilisation, Distance Profiling)\n• Data Quality & Quarantine Transparency Engine with Invariant Formatters", 
            ha="center", va="center", fontsize=8.5, color="#263238")

    # 6. Pipeline Monitoring & Governance (Bottom Left)
    box_mon = patches.FancyBboxPatch((0.5, 0.7), 5.8, 1.9, boxstyle="round,pad=0.2",
                                     fc=c_monitor, ec="#455A64", lw=1.5)
    ax.add_patch(box_mon)
    ax.text(3.4, 2.3, "Data Governance & Execution Auditing", 
            ha="center", va="center", fontsize=11, fontweight="bold", color="#263238")
    ax.text(3.4, 1.45, "• PostgreSQL pipeline_runs & pipeline_stage_runs Audit Ledger\n• Execution ID (run_id), Duration, Record Counts, Status Logging\n• Thread-Safe Pytest Automated Testing Suite (143 Tests Passed)\n• Strict Concurrency Protection via Session pg_advisory_lock", 
            ha="center", va="center", fontsize=8.5, color="#37474F")

    # Bi-directional Arrow between Storage and Monitoring
    ax.annotate("", xy=(3.4, 2.7), xytext=(3.4, 3.7),
                arrowprops=dict(arrowstyle="<->", color="#455A64", lw=1.5))

    plt.tight_layout()
    output_path = "reports/RAIL_SIGNAL_Mini_Project_Report/assets/diagrams/01_system_architecture.png"
    plt.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Architecture diagram generated: {output_path}")

if __name__ == "__main__":
    generate_architecture_diagram()
