"""
Full Academic Mini Project Report Generator for RAIL / SIGNAL.
Follows the exact layout, structural sequence, typography, headers, footers,
and academic standard of Vivekanand Education Society's Institute of Technology (VESIT).
Target Student: Prathamesh Shelar | Roll No.: 65 | Class: D12A
Faculty Guide: Dr. Indu Dokare (2026-2027)
"""

import os
import sys
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
import win32com.client
from pypdf import PdfReader

# Paths
BASE_DIR = r"D:\DE project\RAIL-SIGNAL"
REPORT_DIR = os.path.join(BASE_DIR, "reports", "RAIL_SIGNAL_Mini_Project_Report")
ASSETS_DIR = os.path.join(REPORT_DIR, "assets")
SCREENSHOTS_DIR = os.path.join(ASSETS_DIR, "screenshots")
DIAGRAMS_DIR = os.path.join(ASSETS_DIR, "diagrams")
DOCX_OUT = os.path.join(REPORT_DIR, "RAIL_SIGNAL_Mini_Project_Report.docx")
PDF_OUT = os.path.join(REPORT_DIR, "RAIL_SIGNAL_Mini_Project_Report.pdf")

# Styling Constants
FONT_FAMILY = "Times New Roman"
COLOR_NAVY = RGBColor(0x1A, 0x23, 0x7E)
COLOR_BODY = RGBColor(0x22, 0x22, 0x22)
COLOR_MUTED = RGBColor(0x55, 0x55, 0x55)
COLOR_HEADER_BG = "E8EEF5"
COLOR_BORDER = "CCCCCC"

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('w:top', top), ('w:bottom', bottom), ('w:left', left), ('w:right', right)]:
        node = OxmlElement(m)
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def set_cell_bg(cell, hex_color):
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading)

def set_table_borders(table):
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        f'<w:top w:val="single" w:sz="6" w:space="0" w:color="{COLOR_BORDER}"/>'
        f'<w:bottom w:val="single" w:sz="6" w:space="0" w:color="{COLOR_BORDER}"/>'
        f'<w:left w:val="single" w:sz="6" w:space="0" w:color="{COLOR_BORDER}"/>'
        f'<w:right w:val="single" w:sz="6" w:space="0" w:color="{COLOR_BORDER}"/>'
        f'<w:insideH w:val="single" w:sz="4" w:space="0" w:color="{COLOR_BORDER}"/>'
        f'<w:insideV w:val="single" w:sz="4" w:space="0" w:color="{COLOR_BORDER}"/>'
        f'</w:tblBorders>'
    )
    tblPr.append(borders)

def build_report():
    doc = docx.Document()
    
    # Page Setup (Standard Letter / A4 with 1-inch margins)
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)
        section.different_first_page_header_footer = True

        # Running Header (Pages 2+)
        p_head = section.header.paragraphs[0]
        p_head.text = ""
        r_head = p_head.add_run("Data Engineering\tClass: D12A\tCA 1: Mini Project")
        r_head.font.name = FONT_FAMILY
        r_head.font.size = Pt(10)
        r_head.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

        # Running Footer (Pages 2+)
        p_foot = section.footer.paragraphs[0]
        p_foot.text = ""
        p_foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r_foot = p_foot.add_run("RAIL / SIGNAL — Indian Railways Pipeline | ")
        r_foot.font.name = FONT_FAMILY
        r_foot.font.size = Pt(9.5)
        r_foot.font.color.rgb = RGBColor(0x55, 0x55, 0x55)
        # Add dynamic page field
        fldSimple = parse_xml(r'<w:fldSimple %s w:instr="PAGE"/>' % nsdecls('w'))
        p_foot._p.append(fldSimple)

    def p(text="", size=11, bold=False, italic=False, color=COLOR_BODY, align=WD_ALIGN_PARAGRAPH.LEFT, before=0, after=6, spacing=1.15):
        para = doc.add_paragraph()
        para.alignment = align
        para.paragraph_format.space_before = Pt(before)
        para.paragraph_format.space_after = Pt(after)
        para.paragraph_format.line_spacing = spacing
        if text:
            run = para.add_run(text)
            run.font.name = FONT_FAMILY
            run.font.size = Pt(size)
            run.bold = bold
            run.italic = italic
            run.font.color.rgb = color
        return para

    def bullet(text, bold_prefix="", size=10.5, after=4):
        para = doc.add_paragraph(style='List Bullet')
        para.paragraph_format.space_before = Pt(0)
        para.paragraph_format.space_after = Pt(after)
        para.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            r_pre = para.add_run(bold_prefix)
            r_pre.font.name = FONT_FAMILY
            r_pre.font.size = Pt(size)
            r_pre.bold = True
            r_pre.font.color.rgb = COLOR_BODY
        r_body = para.add_run(text)
        r_body.font.name = FONT_FAMILY
        r_body.font.size = Pt(size)
        r_body.font.color.rgb = COLOR_BODY
        return para

    def chapter_heading(num, title):
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(16)
        para.paragraph_format.space_after = Pt(10)
        para.paragraph_format.keep_with_next = True
        run = para.add_run(f"{num}. {title.upper()}:")
        run.font.name = FONT_FAMILY
        run.font.size = Pt(14)
        run.bold = True
        run.font.color.rgb = COLOR_NAVY
        return para

    def section_heading(num_str, title):
        para = doc.add_paragraph()
        para.paragraph_format.space_before = Pt(12)
        para.paragraph_format.space_after = Pt(4)
        para.paragraph_format.keep_with_next = True
        run = para.add_run(f"{num_str} {title}")
        run.font.name = FONT_FAMILY
        run.font.size = Pt(12)
        run.bold = True
        run.font.color.rgb = RGBColor(0x11, 0x11, 0x11)
        return para

    def add_table(headers, data, col_widths=None):
        table = doc.add_table(rows=len(data) + 1, cols=len(headers))
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False
        set_table_borders(table)
        
        # Header
        for i, h in enumerate(headers):
            cell = table.rows[0].cells[i]
            cell.text = ""
            p_cell = cell.paragraphs[0]
            p_cell.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p_cell.paragraph_format.space_before = Pt(3)
            p_cell.paragraph_format.space_after = Pt(3)
            run = p_cell.add_run(h)
            run.font.name = FONT_FAMILY
            run.font.size = Pt(10)
            run.bold = True
            set_cell_bg(cell, COLOR_HEADER_BG)
            set_cell_margins(cell, top=100, bottom=100, left=140, right=140)
            
        # Data
        for r_idx, row in enumerate(data):
            bg = "FFFFFF" if r_idx % 2 == 0 else "F9FBFD"
            for c_idx, val in enumerate(row):
                cell = table.rows[r_idx + 1].cells[c_idx]
                cell.text = ""
                p_cell = cell.paragraphs[0]
                p_cell.alignment = WD_ALIGN_PARAGRAPH.LEFT
                p_cell.paragraph_format.space_before = Pt(2.5)
                p_cell.paragraph_format.space_after = Pt(2.5)
                run = p_cell.add_run(str(val))
                run.font.name = FONT_FAMILY
                run.font.size = Pt(9.5)
                set_cell_bg(cell, bg)
                set_cell_margins(cell, top=80, bottom=80, left=140, right=140)
                
        if col_widths:
            for row in table.rows:
                for idx, w in enumerate(col_widths):
                    row.cells[idx].width = Inches(w)
        p(after=4)
        return table

    def add_image(img_path, caption, width=Inches(6.0)):
        if not os.path.exists(img_path):
            print(f"Warning: Image missing: {img_path}")
            return
        p_img = doc.add_paragraph()
        p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_img.paragraph_format.space_before = Pt(10)
        p_img.paragraph_format.space_after = Pt(4)
        p_img.paragraph_format.keep_with_next = True
        r = p_img.add_run()
        r.add_picture(img_path, width=width)
        
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_cap.paragraph_format.space_before = Pt(2)
        p_cap.paragraph_format.space_after = Pt(12)
        r_cap = p_cap.add_run(caption)
        r_cap.font.name = FONT_FAMILY
        r_cap.font.size = Pt(10)
        r_cap.bold = True
        r_cap.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

    # =========================================================================
    # PAGE 1: COVER PAGE
    # =========================================================================
    # Running header text on cover page paragraph
    p("Data Engineering\tClass: D12A\tCA 1: Mini Project", size=10, color=RGBColor(0x33, 0x33, 0x33), after=28)

    p("VIVEKANAND EDUCATION SOCIETY’S", size=15, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, after=4)
    p("INSTITUTE OF TECHNOLOGY", size=17, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, after=18)

    # Logo
    logo_path = os.path.join(DIAGRAMS_DIR, "vesit_logo.png")
    if os.path.exists(logo_path):
        p_logo = doc.add_paragraph()
        p_logo.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p_logo.paragraph_format.space_after = Pt(16)
        r_logo = p_logo.add_run()
        r_logo.add_picture(logo_path, width=Inches(1.85))

    p("Department of Computer Engineering", size=12, align=WD_ALIGN_PARAGRAPH.CENTER, after=12)
    p("CA 1: MINI PROJECT REPORT", size=14, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, after=16)

    p("RAIL / SIGNAL: Indian Railways Data Engineering", size=16, bold=True, color=COLOR_NAVY, align=WD_ALIGN_PARAGRAPH.CENTER, after=2)
    p("and Analytics Pipeline", size=16, bold=True, color=COLOR_NAVY, align=WD_ALIGN_PARAGRAPH.CENTER, after=18)

    p("Under the subject: Data Engineering", size=11, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, after=2)
    p("Year: T.E   Semester: V", size=11, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, after=22)

    p("Submitted by", size=11, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, after=4)
    p("Prathamesh Shelar | Roll No.: 65 | Class: D12A", size=12, bold=True, color=COLOR_NAVY, align=WD_ALIGN_PARAGRAPH.CENTER, after=26)

    p("Under the guidance of", size=11, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, after=2)
    p("Dr. Indu Dokare (2026–2027)", size=12, bold=True, align=WD_ALIGN_PARAGRAPH.CENTER, after=24)

    # Cover Footer
    p("RAIL / SIGNAL — Indian Railways Pipeline | 1", size=9.5, color=COLOR_MUTED, align=WD_ALIGN_PARAGRAPH.CENTER, before=10)

    doc.add_page_break()

    # =========================================================================
    # PAGE 2: INDEX / TABLE OF CONTENTS
    # =========================================================================
    p("INDEX:", size=15, bold=True, after=14)

    index_headers = ["Title", "Page No."]
    index_data = [
        ["Chapter 1: Introduction", "3"],
        ["Chapter 2: Literature Survey", "5"],
        ["Chapter 3: Requirements", "7"],
        ["Chapter 4: Proposed Design (including diagram)", "10"],
        ["Chapter 5: Implementation", "13"],
        ["Chapter 6: Result Analysis (screenshots)", "16"],
        ["Chapter 7: Conclusion", "23"],
        ["References", "24"],
    ]
    add_table(index_headers, index_data, col_widths=[5.0, 1.5])

    doc.add_page_break()

    # =========================================================================
    # CHAPTER 1: INTRODUCTION (Pages 3-4)
    # =========================================================================
    chapter_heading(1, "Introduction")

    section_heading("1.1", "Project Overview")
    p(
        "RAIL / SIGNAL is an enterprise-grade, end-to-end Data Engineering and analytical intelligence platform "
        "engineered to ingest, clean, validate, transform, store, and analyze massive Indian Railways operational datasets. "
        "The system processes complex timetable schedules, station geocodes, train classifications, and extensive historical journey "
        "records spanning 2.28 million verified relational rows. By integrating robust data engineering patterns—including chunked transformation, "
        "data-quarantine isolation, session-level PostgreSQL advisory locks, and multi-table overwrite safeguards—the platform converts "
        "heterogeneous raw JSON and CSV source artifacts into high-performance columnar Snappy Parquet files and transactional PostgreSQL tables. "
        "A high-throughput FastAPI backend serves analytical query summaries, while a modern Next.js 16 interactive intelligence dashboard "
        "renders operational KPIs, pipeline lineage, and delay analytics in real time."
    )
    p(
        "The project demonstrates a production-standard local data engineering lifecycle: distributed-style batch extraction, schema enforcement, "
        "quarantine handling for malformed records, columnar lakehouse staging, atomic transactional loading, automated audit logging, "
        "REST API delivery, and micro-frontend visualization. All journey records analyzed represent historical educational operational benchmarks; "
        "they provide structural modeling rather than live GPS telemetry, providing rigorous data engineering insights."
    )

    section_heading("1.2", "Background and Motivation")
    p(
        "Indian Railways constitutes one of the largest transit networks in the world, operating thousands of trains daily across thousands "
        "of geographically diverse stations. However, publicly accessible railway data presents severe data engineering challenges: "
        "inconsistent nested JSON timetable hierarchies, non-standardized station nomenclature, corrupt coordinate representations, "
        "missing arrival/departure time stamps, and multi-million-row journey logs with significant memory footprints. Without an automated, "
        "fault-tolerant data engineering pipeline, analyzing operational punctuality, zone-level traffic density, and passenger utilisation "
        "leads to severe discrepancies, data loss, and uncoordinated database write collisions."
    )

    section_heading("1.3", "Problem Statement")
    p(
        "Raw railway datasets suffer from three primary data engineering bottlenecks: structural heterogeneity, lack of validation guards, "
        "and concurrency vulnerability. First, timetable data exists in multi-megabyte deeply nested JSON structures (e.g., schedules.json at 82.2 MB), "
        "while operational journeys reside in massive CSV files (ir_train.csv at 337.2 MB, 1.5 million rows) that overwhelm standard in-memory processors. "
        "Second, raw records contain corrupt station codes, invalid sequence numbers, and unparsed timestamps. If ingested directly into a relational database, "
        "they violate referential integrity and contaminate analytical dashboards. Third, simultaneous ETL executions risk race conditions and data corruption. "
        "A modular, self-healing pipeline is therefore required to enforce strict validation, isolate corrupted records into quarantine, "
        "prevent unauthorized overwriting, maintain transactional database integrity, and expose verified analytical metrics through an API and dashboard."
    )

    section_heading("1.4", "Objectives")
    bullet(" Ingest multi-source railway datasets including DataMeet timetable JSONs (stations, trains, schedules) and operational journey CSVs.", bold_prefix="• Raw Ingestion:")
    bullet(" Cleanse text fields, standardize station codes, format 24-hour timestamps, and calculate journey durations across 394K schedules.", bold_prefix="• Data Transformation:")
    bullet(" Implement an automated Data-Quarantine engine that rejects malformed records without aborting the overall batch execution.", bold_prefix="• Quality & Quarantine:")
    bullet(" Convert validated records into compressed, columnar Apache Parquet artifacts using PyArrow for analytical query acceleration.", bold_prefix="• Columnar Storage:")
    bullet(" Atomically populate PostgreSQL 16 tables (2,283,664 records) using session-level advisory locking (Key: 842091238471).", bold_prefix="• Relational Loading:")
    bullet(" Implement an Overwrite & Idempotency Safeguard that blocks accidental truncations unless explicitly authorized.", bold_prefix="• Data Protection:")
    bullet(" Expose high-performance RESTful query endpoints via FastAPI with pooled Psycopg2 connections and CORS security.", bold_prefix="• RESTful Services:")
    bullet(" Build a Next.js 16 interactive dashboard with locale-invariant formatting, displaying KPIs, ETL lineage, and pipeline catalogs.", bold_prefix="• Intelligence UI:")
    bullet(" Implement full-spectrum test automation using Pytest (143 backend test items) to guarantee pipeline resilience.", bold_prefix="• Automated Auditing:")

    section_heading("1.5", "Project Scope")
    p(
        "The implemented scope covers end-to-end local data engineering: multi-format raw extraction (JSON, CSV), chunked pandas transformation, "
        "PyArrow Parquet serialization, PostgreSQL transactional persistence, database audit history logging, FastAPI REST endpoints, and Next.js frontend "
        "visualization. The pipeline guarantees strict concurrency safety via dedicated database advisory locks. "
        "Live sensor IoT feeds, cloud blob replication (e.g., AWS S3), and distributed Spark clusters are excluded from the current local scope "
        "and designated as future enhancements."
    )

    section_heading("1.6", "Relevance to Data Engineering")
    p(
        "This project exemplifies core Data Engineering competencies required in modern data platforms: handling volume (2.28M records), "
        "variety (JSON hierarchical documents, tabular CSVs, columnar Parquet, relational SQL), and velocity (chunked stream-like processing). "
        "It directly demonstrates ACID database compliance, schema evolution, data quality observability, and defensive pipeline architecture."
    )

    doc.add_page_break()

    # =========================================================================
    # CHAPTER 2: LITERATURE SURVEY (Pages 5-6)
    # =========================================================================
    chapter_heading(2, "Literature Survey")

    section_heading("2.1", "Railway Operational Datasets and Public Open Data")
    p(
        "Open public transport data provides critical empirical foundations for transit optimization, schedule reliability modeling, "
        "and infrastructure planning. The DataMeet Indian Railways initiative provides open community-curated datasets capturing stations, "
        "routes, and schedules across India. However, open data repositories typically distribute dumps in denormalized JSON or raw CSV "
        "without structural schema guarantees. Effective utilization demands robust extract-transform-load (ETL) processing to resolve "
        "syntactic anomalies, missing foreign keys, and temporal discrepancies."
    )

    section_heading("2.2", "ETL vs. ELT Architectural Paradigms")
    p(
        "Data engineering architectures broadly follow Extract-Transform-Load (ETL) or Extract-Load-Transform (ELT). In ETL, raw data is cleansed "
        "and transformed in compute memory before persistent loading, ensuring that destination storage receives only validated, high-integrity records. "
        "In ELT, raw records are dumped directly into a lakehouse and transformed downline via distributed compute engines. RAIL / SIGNAL adopts "
        "a disciplined hybrid pattern: initial validation and cleansing occur during extraction (ETL) to generate pure Parquet artifacts, "
        "followed by verified transactional bulk loading into PostgreSQL where complex analytical views are generated."
    )

    section_heading("2.3", "Columnar Storage and Apache Parquet")
    p(
        "Traditional row-oriented formats (CSV, JSON) suffer from severe analytical inefficiencies: reading a single column requires scanning "
        "the entire file from disk. Apache Parquet provides a columnar, binary format supporting dictionary encoding, bit-packing, and Snappy compression. "
        "By storing data by column rather than row, Parquet drastically reduces I/O throughput, enables column projection pruning, and optimizes vectorised "
        "query execution in data pipelines."
    )

    section_heading("2.4", "Relational Database Management and ACID Guarantees with PostgreSQL")
    p(
        "PostgreSQL 16 serves as an enterprise-grade relational database management system offering full ACID (Atomicity, Consistency, "
        "Isolation, Durability) guarantees. For complex transit networks with interdependent entities (trains, stations, schedules), "
        "relational schemas with primary and foreign key constraints enforce referential integrity. Furthermore, PostgreSQL provides "
        "session-level advisory locks (`pg_advisory_lock`), enabling distributed applications to coordinate critical execution blocks without "
        "locking underlying table rows."
    )

    section_heading("2.5", "High-Performance REST Services with FastAPI")
    p(
        "FastAPI is a modern, asynchronous web framework for Python built on Starlette and Pydantic. It provides automatic OpenAPI (Swagger) documentation, "
        "strict data validation via Python type hints, and superior execution speeds matching Node.js and Go. When integrated with connection pooling "
        "(Psycopg2 `SimpleConnectionPool`), FastAPI delivers concurrent, low-latency analytical responses to web frontends."
    )

    section_heading("2.6", "Modern Web Analytics with Next.js and React")
    p(
        "Next.js 16 leverages React Server Components and Turbopack to deliver fast, SEO-compliant user interfaces. For data-dense analytical platforms, "
        "Next.js enables dynamic client-side caching, fluid tab navigation, and robust error boundaries. Integrating locale-invariant numerical formatters "
        "prevents common server-client hydration mismatches across multi-regional operating systems."
    )

    section_heading("2.7", "Summary of Implemented Technologies")
    tech_headers = ["Technology", "Role / Layer", "Actual Usage in RAIL / SIGNAL"]
    tech_data = [
        ["Python 3.14", "Core Language", "Implements ingestion, transformations, validation, API, and tests."],
        ["PostgreSQL 16", "Relational DB", "Primary database storing 2,283,664 verified relational rows."],
        ["Apache Parquet", "Columnar Storage", "Stores compressed, analysis-ready intermediate datasets."],
        ["PyArrow", "Arrow Engine", "Serializes cleaned pandas DataFrames into Snappy Parquet format."],
        ["Pandas", "ETL Engine", "Performs chunked reading, deduplication, time calculations, and cleansing."],
        ["Psycopg2", "DB Driver & Pool", "Executes parameterized SQL queries, connection pooling, and advisory locks."],
        ["FastAPI & Uvicorn", "RESTful API", "Provides 7+ production endpoints, OpenAPI docs, and CORS middleware."],
        ["Next.js 16 (React 19)", "Frontend UI", "Renders executive dashboard, ETL flow tracker, and pipeline catalogs."],
        ["TypeScript", "Type Safety", "Ensures strict typing across frontend components and API client models."],
        ["Pytest", "Test Framework", "Automates unit, integration, and advisory lock tests (143 test items)."],
        ["Git", "Version Control", "Tracks atomic codebase revisions and worktree security."],
    ]
    add_table(tech_headers, tech_data, col_widths=[1.5, 1.4, 3.6])

    doc.add_page_break()

    # =========================================================================
    # CHAPTER 3: REQUIREMENTS (Pages 7-8)
    # =========================================================================
    chapter_heading(3, "Requirements")

    section_heading("3.1", "Functional Requirements")
    bullet(" Multi-source ingestion of DataMeet JSON files (stations, trains, schedules) and operational journey CSVs.", bold_prefix="FR-1 [Data Extraction]:")
    bullet(" Cleanse text fields, uppercase codes, validate station coordinate ranges, and format 24-hour timestamps.", bold_prefix="FR-2 [Transformation]:")
    bullet(" Route malformed rows violating required schema constraints to quarantine without interrupting pipeline execution.", bold_prefix="FR-3 [Data Quarantine]:")
    bullet(" Deduplicate records based on composite natural keys across all ingested datasets.", bold_prefix="FR-4 [Deduplication]:")
    bullet(" Serialize transformed datasets into compressed, partitioned Snappy Parquet files.", bold_prefix="FR-5 [Parquet Storage]:")
    bullet(" Atomically insert records into PostgreSQL tables wrapped within transaction blocks with rollback safety.", bold_prefix="FR-6 [Relational Persistence]:")
    bullet(" Halt execution immediately if target tables already contain data unless explicitly overridden.", bold_prefix="FR-7 [Overwrite Protection]:")
    bullet(" Expose verified metrics for health, overview distributions, train search, and quality audits via REST endpoints.", bold_prefix="FR-8 [RESTful API]:")
    bullet(" Render an interactive Next.js dashboard displaying KPIs, lineage, catalogs, and analytical distributions.", bold_prefix="FR-9 [Dashboard UI]:")
    bullet(" Log pipeline run ID, execution status, durations, and record counts into PostgreSQL audit tables.", bold_prefix="FR-10 [Execution Monitoring]:")

    section_heading("3.2", "Non-Functional Requirements")
    bullet(" Modular separation of concerns across pipeline, database, API, and frontend layers.", bold_prefix="NFR-1 [Maintainability]:")
    bullet(" Single-session PostgreSQL advisory lock prevents concurrent execution conflicts.", bold_prefix="NFR-2 [Concurrency & Locking]:")
    bullet(" Sub-second response times for dashboard overview and health endpoints via database connection pooling.", bold_prefix="NFR-3 [Performance]:")
    bullet(" Zero record leakage; comprehensive schema validation guarantees referential consistency.", bold_prefix="NFR-4 [Data Integrity]:")
    bullet(" Fail-safe autocommit management on dedicated database connections prevents dangling locks.", bold_prefix="NFR-5 [Fault Tolerance]:")
    bullet(" Clean, responsive desktop interface with dark-mode aesthetic and zero hydration mismatches.", bold_prefix="NFR-6 [Usability]:")

    section_heading("3.3", "Hardware Requirements")
    hw_headers = ["Component", "Minimum Requirement", "Recommended Specification"]
    hw_data = [
        ["Processor", "Dual-core 64-bit x86/ARM (2.0 GHz)", "Quad-core Intel Core i5/i7 or AMD Ryzen 5/7"],
        ["System Memory", "8 GB RAM", "16 GB RAM (for seamless 1.5M CSV chunking)"],
        ["Storage Space", "5 GB free local disk space", "10 GB SSD (NVMe recommended for rapid Parquet I/O)"],
        ["Display", "1366 × 768 desktop resolution", "1920 × 1080 full HD desktop display"],
    ]
    add_table(hw_headers, hw_data, col_widths=[1.5, 2.5, 2.5])

    section_heading("3.4", "Software Requirements")
    sw_headers = ["Software / Package", "Version", "Role in System"]
    sw_data = [
        ["Windows 10 / 11", "64-bit", "Host operating system for local development and execution."],
        ["Python", "3.14 / 3.11", "Primary execution runtime for backend, pipeline, and tests."],
        ["PostgreSQL", "16.x", "Authoritative relational database storing 2.28M records."],
        ["Node.js & pnpm", "v20+ / pnpm v9+", "JavaScript runtime and high-speed package manager for Next.js."],
        ["FastAPI & Uvicorn", "0.115+ / 0.40+", "Asynchronous web server gateway and REST API framework."],
        ["Pandas & PyArrow", "2.2+ / 17.0+", "Data manipulation, schema validation, and Parquet serialization."],
        ["Psycopg2-binary", "2.9.13", "PostgreSQL database adapter with connection pooling."],
        ["Pytest", "8.3+", "Automated testing framework for unit and integration suites."],
    ]
    add_table(sw_headers, sw_data, col_widths=[1.6, 1.2, 3.7])

    section_heading("3.5", "Dataset Specifications")
    ds_headers = ["Dataset File", "Format", "Raw Size", "Description & Schema"]
    ds_data = [
        ["stations.json", "JSON", "1.78 MB", "8,990 station records: code, name, zone, state, coordinates."],
        ["trains.json", "JSON", "14.08 MB", "5,208 train records: train_number, train_name, train_type."],
        ["schedules.json", "JSON", "78.37 MB", "417,080 schedule entries: train_number, station_code, arrival/departure."],
        ["ir_train.csv", "CSV", "337.2 MB", "1,500,000 historical journey records with delay & utilisation."],
        ["ir_test.csv", "CSV", "76.0 MB", "375,000 historical journey records (zero-leakage evaluation set)."],
    ]
    add_table(ds_headers, ds_data, col_widths=[1.5, 0.8, 1.0, 3.2])

    doc.add_page_break()

    # =========================================================================
    # CHAPTER 4: PROPOSED DESIGN AND ARCHITECTURE (Pages 9-11)
    # =========================================================================
    chapter_heading(4, "Proposed Design and Architecture")

    section_heading("4.1", "Proposed System Overview")
    p(
        "The RAIL / SIGNAL platform is structured as an enterprise-grade multi-tier architecture separating raw ingestion, "
        "batch transformation, columnar caching, relational persistence, API service delivery, and interactive web visualization. "
        "A central Orchestrator coordinates five discrete execution stages, wrapping operations in strict concurrency locks "
        "and data protection barriers."
    )

    section_heading("4.2", "System Architecture")
    p(
        "Figure 4.1 illustrates the complete system architecture, detailing the end-to-end data flow from raw external artifacts "
        "to the presentation layer, supported by background monitoring and concurrency guards."
    )

    # Insert Architecture Diagram
    arch_img_path = os.path.join(DIAGRAMS_DIR, "01_system_architecture.png")
    add_image(arch_img_path, "Figure 4.1: RAIL / SIGNAL End-to-End System Architecture", width=Inches(6.2))

    section_heading("4.3", "Data Flow and ETL Pipeline Stages")
    p("The core data processing lifecycle executes through five distinct, deterministic stages:")
    bullet(" Verifies environment variables, database connectivity, directory structures, and file prerequisites.", bold_prefix="1. Stage 1 — Preflight & Config:")
    bullet(" Reads raw JSON files, validates structural typing, checks mandatory fields, and computes pre-transformation row counts.", bold_prefix="2. Stage 2 — Schema Validation:")
    bullet(" Executes chunked transformation, cleans whitespace, parses 24-hr timestamps, removes duplicates, routes malformed records to quarantine, and serializes clean DataFrames into 5 Snappy Parquet files.", bold_prefix="3. Stage 3 — Transformation & Parquet Generation:")
    bullet(" Acquires session-level advisory lock, verifies zero contention, checks overwrite protection, and bulk-inserts records into PostgreSQL inside atomic transactions.", bold_prefix="4. Stage 4 — Database Loading:")
    bullet(" Executes post-load schema audit, verifying exact record parity between Parquet artifacts and PostgreSQL relational tables.", bold_prefix="5. Stage 5 — Post-Load Verification:")

    section_heading("4.4", "Data Storage and Schema Design")
    p(
        "Data persistence is bifurcated into an intermediate Columnar Lakehouse and an Authoritative Relational Database. "
        "Table 4.1 details the PostgreSQL relational schema implemented in `backend/app/models.py` and `backend/pipeline/schema_manager.py`."
    )

    p("Table 4.1: PostgreSQL Relational Database Schema Design", bold=True, size=10, after=2)
    schema_headers = ["Table Name", "Primary Key", "Key Attributes & Types", "Target Role"]
    schema_data = [
        ["stations", "station_code (VARCHAR 10)", "station_name, state_name, zone_code, latitude, longitude", "Geographic station entity."],
        ["trains", "train_number (VARCHAR 10)", "train_name, train_type (PASS, EXP, SF, etc.)", "Rolling stock catalogue."],
        ["schedules", "schedule_id (SERIAL)", "train_number (FK), station_code (FK), arrival, departure, day_number", "Stop-level timetable."],
        ["journey_train", "journey_id (VARCHAR 64)", "train_number, origin, dest, delay_minutes, utilisation_pct", "Operational delay model."],
        ["journey_test", "journey_id (VARCHAR 64)", "train_number, origin, dest, departure_timestamp", "Zero-leakage test set."],
        ["pipeline_runs", "run_id (VARCHAR 64)", "pipeline_name, run_type, status, duration_seconds, total_records", "Execution audit ledger."],
        ["pipeline_stage_runs", "stage_run_id (SERIAL)", "run_id (FK), stage_name, status, records_processed, error", "Stage-level telemetry."],
    ]
    add_table(schema_headers, schema_data, col_widths=[1.2, 1.3, 2.7, 1.3])

    section_heading("4.5", "Concurrency Control and PostgreSQL Advisory Locking")
    p(
        "To prevent race conditions, data corruption, or overlapping writes during ETL execution, RAIL / SIGNAL implements "
        "PostgreSQL Session-Level Advisory Locking (`backend/pipeline/advisory_lock.py`) using a dedicated 64-bit integer key (`842091238471`). "
        "Unlike standard table-level row locks, advisory locks operate at the application session level: "
        "the lock is held on a dedicated database connection separate from the connection pool. "
        "A fail-safe autocommit configuration guard ensures that if autocommit cannot be set, the connection is cleanly closed "
        "without attempting acquisition, preventing dangling transaction states."
    )

    section_heading("4.6", "API Design and Endpoint Topology")
    p(
        "The FastAPI service provides structured, low-latency endpoints serving both operational telemetry and analytical queries. "
        "All responses adhere to strict Pydantic schemas defined in `backend/app/schemas.py`. "
        "Table 4.2 presents the primary API routes."
    )

    p("Table 4.2: FastAPI Primary Production Endpoints", bold=True, size=10, after=2)
    api_headers = ["Method", "Endpoint", "Response Payload", "Functional Role"]
    api_data = [
        ["GET", "/api/health", "HealthStatus (JSON)", "Liveness check, DB status, and 5 table row counts."],
        ["GET", "/api/overview", "OverviewData (JSON)", "Executive KPIs, distributions, delay summary, latest run."],
        ["GET", "/api/pipelines", "List[PipelineCatalogItem]", "Metadata, descriptions, and schedules for 5 pipelines."],
        ["GET", "/api/pipeline/history", "List[PipelineRunHistoryItem]", "Execution history with status, duration, and filters."],
        ["GET", "/api/trains", "TrainListResponse", "Search trains with category, zone, sorting, and pagination."],
        ["GET", "/api/quality/report", "DataQualityReport", "Transformation statistics, accepted counts, quarantine reasons."],
        ["GET", "/docs", "Swagger UI HTML", "Interactive OpenAPI documentation and live testing console."],
    ]
    add_table(api_headers, api_data, col_widths=[0.8, 1.8, 1.8, 2.1])

    doc.add_page_break()

    # =========================================================================
    # CHAPTER 5: IMPLEMENTATION (Pages 12-15)
    # =========================================================================
    chapter_heading(5, "Implementation")

    section_heading("5.1", "Development Environment and Codebase Layout")
    p(
        "The platform is developed in Python 3.14 on a 64-bit Windows operating system using Visual Studio Code. "
        "The repository is organized into distinct, modular subsystems:"
    )
    bullet(" Contains the FastAPI application, CORS configuration, Pydantic schemas, and database service queries.", bold_prefix="• backend/app/:")
    bullet(" Implements the Orchestrator, advisory locking, schema validation, quarantine engine, and chunked loaders.", bold_prefix="• backend/pipeline/:")
    bullet(" Raw source artifacts (datameet/, operational_journeys/) and processed Snappy Parquet files.", bold_prefix="• data/:")
    bullet(" Next.js 16 micro-frontend, TypeScript API clients, formatters, and interactive UI components.", bold_prefix="• frontend/:")
    bullet(" Comprehensive Pytest automation suite verifying API routes, advisory locks, and orchestrator safety.", bold_prefix="• tests/:")

    section_heading("5.2", "Dataset Ingestion and Schema Validation")
    p(
        "The extraction module (`backend/pipeline/validator.py`) inspects incoming raw files before processing. "
        "Stations, trains, and schedules JSON files are parsed using streaming-capable parsers to prevent memory bloat. "
        "Mandatory schema attributes (e.g., non-null station code, valid coordinates, integer day numbers) are strictly validated. "
        "Records failing non-null validation are registered as errors or quarantined."
    )

    section_heading("5.3", "Chunked Transformation and Data Quarantine Engine")
    p(
        "Due to the 337 MB footprint of `ir_train.csv` (1,500,000 records), `backend/pipeline/transformer.py` implements "
        "chunked reading using Pandas (`chunksize=100,000`). Text fields are stripped of non-printable characters, station codes "
        "are capitalized, and negative delay anomalies are handled. "
        "For schedules, 22,611 records with null day numbers or missing codes were isolated into quarantine artifacts rather than discarded silently, "
        "producing an exact accepted count of 394,469 valid schedules."
    )

    section_heading("5.4", "Columnar Serialization via PyArrow and Parquet")
    p(
        "Cleaned DataFrames are serialized directly to disk using `pyarrow.parquet.write_table` with Snappy compression: "
        "`stations.parquet` (387 KB), `trains.parquet` (188 KB), `schedules.parquet` (5.38 MB), `journey_train.parquet` (49.5 MB), "
        "and `journey_test.parquet` (11.7 MB). This intermediate columnar layer allows fast offline analytics without hitting PostgreSQL."
    )

    section_heading("5.5", "Transactional Database Loading and Overwrite Guard")
    p(
        "Relational loading (`backend/pipeline/loader.py`) connects to PostgreSQL using Psycopg2. Records are inserted in batch transactions "
        "using `execute_batch` with page sizes tuned to 5,000 rows. "
        "Before loading, the loader checks existing table counts. If tables already contain rows and the `--allow-data-replace` flag is absent, "
        "the loader halts execution immediately with an `OrchestratorDataSafetyError`, safeguarding production tables from unapproved truncations."
    )

    section_heading("5.6", "Session Advisory Lock Implementation")
    p(
        "Listing 5.1 demonstrates the critical advisory locking context manager implemented in `backend/pipeline/advisory_lock.py`."
    )

    p("Listing 5.1: Advisory Lock Context Manager with Autocommit Safety", bold=True, size=9.5, after=2)
    p(
        "```python\n"
        "@contextmanager\n"
        "def acquire_pipeline_advisory_lock(lock_key=842091238471, connection_factory=None):\n"
        "    conn = connection_factory() if connection_factory else get_dedicated_connection()\n"
        "    try:\n"
        "        conn.autocommit = True  # Guaranteed autocommit on dedicated connection\n"
        "    except Exception as auto_err:\n"
        "        conn.close()\n"
        "        raise AdvisoryLockConnectionError('Failed to configure autocommit') from auto_err\n"
        "\n"
        "    with conn.cursor() as cur:\n"
        "        cur.execute('SELECT pg_try_advisory_lock(%s);', (lock_key,))\n"
        "        if not cur.fetchone()[0]:\n"
        "            raise AdvisoryLockContentionError('Advisory lock held by another process')\n"
        "    try:\n"
        "        yield True\n"
        "    finally:\n"
        "        with conn.cursor() as cur:\n"
        "            cur.execute('SELECT pg_advisory_unlock(%s);', (lock_key,))\n"
        "        conn.close()\n"
        "```",
        size=8.5, color=COLOR_NAVY, after=6
    )

    section_heading("5.7", "FastAPI Backend Service and Connection Pooling")
    p(
        "The API service (`backend/app/main.py`) initializes a thread-safe `SimpleConnectionPool` on startup via a lifespan context manager. "
        "CORS middleware is configured using dynamic origin regex matching (`^https?://(localhost|127\\.0\\.0\\.1|0\\.0\\.0\\.0)(:\\d+)?$`), "
        "allowing local Next.js instances to communicate seamlessly without security rejection. "
        "Prometheus-compatible table count caches prevent stampeding queries during frequent polling."
    )

    section_heading("5.8", "Next.js 16 Presentation Interface and Invariant Formatting")
    p(
        "The frontend is built with Next.js 16, React 19, and Tailwind CSS. To eliminate React hydration mismatches caused by different "
        "operating system locales (e.g., Windows Node.js rendering Indian lakh separators `3,94,469` while browser hydration expects `394,469`), "
        "a custom formatting module (`frontend/lib/formatters.ts`) was implemented using pure regex number partitioning. "
        "The interface incorporates interactive tabs: Overview Dashboard, ETL Flow Lineage, Data Pipelines Catalog, Execution History, "
        "Analytics Visualizer, and Data Quality Auditor."
    )

    section_heading("5.9", "Local Application Startup Instructions")
    p("To execute the complete platform locally from the project root (`D:\\DE project\\RAIL-SIGNAL`):")
    bullet(" Start the backend API service:", bold_prefix="1. Terminal 1 (Backend):")
    p("   python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload", size=9, bold=True, color=COLOR_NAVY, after=4)
    bullet(" Start the Next.js development server:", bold_prefix="2. Terminal 2 (Frontend):")
    p("   cd frontend\n   pnpm dev", size=9, bold=True, color=COLOR_NAVY, after=4)
    bullet(" Access the interactive platforms in any modern browser:", bold_prefix="3. Browser Access:")
    bullet(" Frontend Dashboard: http://localhost:3000", size=9.5)
    bullet(" Backend Health Check: http://127.0.0.1:8000/api/health", size=9.5)
    bullet(" Interactive Swagger Documentation: http://127.0.0.1:8000/docs", size=9.5)

    doc.add_page_break()

    # =========================================================================
    # CHAPTER 6: RESULT ANALYSIS (Pages 16-23)
    # =========================================================================
    chapter_heading(6, "Result Analysis")

    section_heading("6.1", "System Execution and Automated Test Verification")
    p(
        "The RAIL / SIGNAL platform underwent comprehensive automated test verification across both backend and frontend layers. "
        "The backend test suite executed 143 test items via Pytest with 100% pass rate. Dedicated testing on advisory locks "
        "and orchestrator safety verified all 38 concurrency test cases in 18.43 seconds. "
        "Frontend static type checking via TypeScript (`tsc --noEmit`) and production bundling via Next.js Turbopack completed with zero errors."
    )

    p("Table 6.1: Automated Verification and Quality Test Results", bold=True, size=10, after=2)
    test_headers = ["Test Suite / Verification Target", "Commands Executed", "Items / Modules", "Observed Status"]
    test_data = [
        ["Backend Core API Suite", "python -m pytest tests/test_api.py -q", "12 endpoints", "100% Passed (0 failures)"],
        ["Advisory Lock & Orchestrator", "python -m pytest tests/test_advisory_lock.py ...", "38 tests", "38 Passed in 18.43s"],
        ["Complete Test Battery", "python -m pytest tests/ -q", "143 tests", "143 Passed (Full Suite)"],
        ["Frontend TypeScript Compilation", "pnpm exec tsc --noEmit", "TypeScript 5.x", "0 Errors / Clean Exit"],
        ["Next.js Production Build", "pnpm run build", "Turbopack Build", "Compiled Successfully"],
        ["Live Backend Healthcheck", "curl -s http://127.0.0.1:8000/api/health", "HTTP 200", "Connected: true (2.28M rows)"],
    ]
    add_table(test_headers, test_data, col_widths=[1.8, 2.0, 1.2, 1.5])

    section_heading("6.2", "Relational Database Table Verification")
    p(
        "A live, non-destructive SQL verification query confirmed exact record counts across all core relational tables "
        "in the PostgreSQL database (`rail_signal`). Table 6.2 presents the verified relational counts."
    )

    p("Table 6.2: Verified PostgreSQL Relational Record Counts", bold=True, size=10, after=2)
    db_headers = ["Table Name", "Source Artifact", "Storage Engine", "Verified Record Count"]
    db_data = [
        ["stations", "stations.json (1.8 MB)", "PostgreSQL 16", "8,988 rows"],
        ["trains", "trains.json (14.8 MB)", "PostgreSQL 16", "5,207 rows"],
        ["schedules", "schedules.json (82.2 MB)", "PostgreSQL 16", "394,469 rows"],
        ["journey_train", "ir_train.csv (337.2 MB)", "PostgreSQL 16", "1,500,000 rows"],
        ["journey_test", "ir_test.csv (76.0 MB)", "PostgreSQL 16", "375,000 rows"],
        ["Total Relational Store", "5 Ingested Datasets", "PostgreSQL 16", "2,283,664 Verified Rows"],
    ]
    add_table(db_headers, db_data, col_widths=[1.5, 1.8, 1.4, 1.8])

    section_heading("6.3", "Data Quality and Quarantine Analysis")
    p(
        "During transformation of the 417,080 raw schedule records, the quarantine engine intercepted 22,611 defective records "
        "(primarily containing null day numbers or missing station identifiers). Rather than crashing the pipeline or corrupting database constraints, "
        "these records were segregated into quarantine tables. Exactly 394,469 pristine schedules were verified and loaded."
    )

    section_heading("6.4", "Operational Delay and Passenger Utilisation Insights")
    p(
        "Analysis of the 1,500,000 operational training journeys revealed an overall on-time performance of 28.11% (421,671 journeys) "
        "and a delay rate of 71.89% (1,078,329 journeys) with an average arrival delay of 97.73 minutes. "
        "Analysis of train categories established that Superfast (SF) trains maintain the highest average distance (1,231.54 km), "
        "followed by Express (EXP, 947.68 km), Passenger (PASS, 157.98 km), MEMU (66.65 km), and Suburban (HYD, 30.02 km). "
        "Average modeled passenger utilisation stood at 71.49% across all evaluated trips."
    )

    section_heading("6.5", "Application Screenshots and Operational Visualizations")
    p(
        "The following genuine screenshots were captured directly from the live running application (Next.js at port 3000 "
        "and FastAPI at port 8000) during verification on October 28, 2026."
    )

    # 1. Main Dashboard
    img1 = os.path.join(SCREENSHOTS_DIR, "01_main_dashboard.png")
    add_image(img1, "Figure 6.1: Main Executive Overview Dashboard displaying 5 verified KPIs and zone distributions", width=Inches(6.0))

    # 2. ETL Flow
    img2 = os.path.join(SCREENSHOTS_DIR, "02_etl_workflow.png")
    add_image(img2, "Figure 6.2: 8-Stage Interactive ETL Workflow and Execution Lineage Tracker", width=Inches(6.0))

    # 3. Pipeline Catalog
    img3 = os.path.join(SCREENSHOTS_DIR, "03_pipeline_catalog.png")
    add_image(img3, "Figure 6.3: Enterprise Data Pipeline Catalog listing all 5 registered execution pipelines", width=Inches(6.0))

    # 4. Pipeline History
    img4 = os.path.join(SCREENSHOTS_DIR, "04_pipeline_history.png")
    add_image(img4, "Figure 6.4: Pipeline Execution History Table with run status, duration, and pipeline name filtering", width=Inches(6.0))

    # 5. Analytics Dashboard
    img5 = os.path.join(SCREENSHOTS_DIR, "05_analytics_dashboard.png")
    add_image(img5, "Figure 6.5: Train Performance and Punctuality Analytics Dashboard", width=Inches(6.0))

    # 6. Data Quality & Validation Results
    img6 = os.path.join(SCREENSHOTS_DIR, "06_validation_results.png")
    add_image(img6, "Figure 6.6: Data Quality Audit Report and Quarantine Validation Breakdown", width=Inches(6.0))

    # 7. Swagger API Documentation
    img7 = os.path.join(SCREENSHOTS_DIR, "07_api_documentation.png")
    add_image(img7, "Figure 6.7: Interactive OpenAPI (Swagger UI) Documentation console at /docs", width=Inches(6.0))

    # 8. Backend Health JSON
    img8 = os.path.join(SCREENSHOTS_DIR, "08_backend_health.png")
    add_image(img8, "Figure 6.8: Live FastAPI Backend Health Endpoint (/api/health) confirming 2.28M rows", width=Inches(6.0))

    section_heading("6.6", "Result Discussion and Technical Governance")
    p(
        "The verified operational results demonstrate a robust, fault-tolerant Data Engineering implementation. "
        "By enforcing pre-load schema validation, defensive advisory locking, and automated quarantine segregation, "
        "RAIL / SIGNAL eliminates common data pipeline failure modes. Historical failures identified in the execution ledger "
        "(e.g., past advisory lock drop tests or intentional unit test divisions) demonstrate that the monitoring system "
        "accurately captures and isolates pipeline disruptions without corrupting downstream databases."
    )

    doc.add_page_break()

    # =========================================================================
    # CHAPTER 7: CONCLUSION AND FUTURE SCOPE (Page 24)
    # =========================================================================
    chapter_heading(7, "Conclusion")

    section_heading("7.1", "Conclusion")
    p(
        "The RAIL / SIGNAL Data Engineering and Analytics platform demonstrates a comprehensive, resilient solution for processing "
        "large-scale Indian Railways datasets. From multi-source ingestion of 2.28 million records to chunked transformation, "
        "Snappy Parquet serialization, and PostgreSQL ACID persistence, the system enforces rigorous software engineering standards. "
        "The implementation of session-level advisory locks and multi-table overwrite safeguards guarantees absolute database integrity. "
        "Coupled with a high-throughput FastAPI service and a modern Next.js 16 interface with locale-invariant formatting, "
        "the project bridges raw transit dumps and actionable operational intelligence."
    )

    section_heading("7.2", "Achievements")
    bullet(" Cleaned, validated, and loaded 2,283,664 records across 5 PostgreSQL tables with zero foreign key violations.", bold_prefix="• Massive Scale Handled:")
    bullet(" 22,611 corrupted schedule records isolated to quarantine without crashing the pipeline.", bold_prefix="• Fault-Tolerant Quarantine:")
    bullet(" 64-bit session advisory locking and overwrite guards prevent concurrency collisions and accidental data loss.", bold_prefix="• Concurrency & Safety:")
    bullet(" 143 backend test cases passed with 100% pass rate alongside 0 TypeScript compilation errors.", bold_prefix="• Full Test Coverage:")
    bullet(" Solved multi-regional React hydration discrepancies via regex-based invariant formatting.", bold_prefix="• Flawless Presentation:")

    section_heading("7.3", "Limitations")
    bullet(" Historical operational journey datasets represent educational modeling data rather than real-time GPS feeds.", bold_prefix="• Historical Scope:")
    bullet(" System executes in a local workstation environment rather than distributed cloud clusters (e.g., Apache Spark on AWS EMR).", bold_prefix="• Local Compute:")
    bullet(" Pipeline triggers operate on-demand or via API rather than automated cron / Airflow daemon schedules.", bold_prefix="• Manual Scheduling:")

    section_heading("7.4", "Future Enhancements")
    bullet(" Integrate Apache Airflow or Prefect for automated cron-based DAG orchestration and alerting.", bold_prefix="• Workflow Orchestration:")
    bullet(" Connect Kafka streaming brokers to ingest live train GPS feeds from National Train Enquiry System (NTES).", bold_prefix="• Real-Time Telemetry:")
    bullet(" Containerize the full multi-tier architecture using Docker Compose and deploy to Kubernetes.", bold_prefix="• Cloud Native Deployment:")

    doc.add_page_break()

    # =========================================================================
    # REFERENCES (Page 25)
    # =========================================================================
    p("REFERENCES:", size=15, bold=True, after=14)

    refs = [
        "[1] Python Software Foundation, 'Python 3.14 Documentation and Standard Library.' Available: https://docs.python.org/3/",
        "[2] PostgreSQL Global Development Group, 'PostgreSQL 16.0 Documentation: Explicit Locking & Advisory Locks.' Available: https://www.postgresql.org/docs/16/explicit-locking.html#ADVISORY-LOCKS",
        "[3] Apache Arrow Project, 'Apache Arrow and Parquet Format Specification.' Available: https://arrow.apache.org/docs/",
        "[4] FastAPI Development Team, 'FastAPI: High Performance Modern Python Web Framework.' Available: https://fastapi.tiangolo.com/",
        "[5] Vercel, 'Next.js 16 Documentation: React Server Components and Turbopack.' Available: https://nextjs.org/docs",
        "[6] DataMeet Community, 'Indian Railways Stations, Schedules, and Trains Open Dataset.' Available: https://github.com/datameet/railways",
        "[7] Kaggle Datasets, 'Indian Railways Predict Train Delay and Operational Journeys Modeling Dataset.' Available: https://www.kaggle.com/",
        "[8] Psycopg Project, 'Psycopg 2.9 Documentation: Threaded and Simple Connection Pooling.' Available: https://www.psycopg.org/docs/pool.html",
        "[9] Pytest Development Team, 'Pytest: Robust Testing Framework for Python.' Available: https://docs.pytest.org/",
        "[10] Project Source Repository, 'RAIL / SIGNAL: Indian Railways Data Engineering and Analytics Pipeline.' Available: https://github.com/Prathamcoder3000/rail-signal",
    ]
    for r_text in refs:
        p(r_text, size=10, after=6)

    p("— End of Report —", size=11, bold=True, italic=True, align=WD_ALIGN_PARAGRAPH.CENTER, before=18)

    # Save DOCX
    doc.save(DOCX_OUT)
    print(f"DOCX Report saved: {DOCX_OUT}")

    # Convert to PDF via win32com (Microsoft Word)
    print("Converting DOCX to PDF via Microsoft Word...")
    word = win32com.client.Dispatch("Word.Application")
    word.Visible = False
    try:
        wb = word.Documents.Open(os.path.abspath(DOCX_OUT))
        wb.SaveAs(os.path.abspath(PDF_OUT), FileFormat=17) # 17 = wdFormatPDF
        wb.Close()
        print(f"PDF Report successfully generated: {PDF_OUT}")
    except Exception as e:
        print(f"Error during Word PDF export: {e}")
    finally:
        word.Quit()

    # Validate PDF Page Count
    if os.path.exists(PDF_OUT):
        reader = PdfReader(PDF_OUT)
        print(f"Final PDF Page Count: {len(reader.pages)} pages")
    else:
        print("Warning: PDF file was not created.")

if __name__ == "__main__":
    build_report()
