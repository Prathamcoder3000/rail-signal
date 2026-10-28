"""
Academic Project Report Generator for RAIL / SIGNAL.
Builds the complete DOCX matching the exact styling of the reference PDF,
then converts to PDF using Microsoft Word (win32com).
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

# ---------------------------------------------------------------------------
# Styling & Formatting Constants
# ---------------------------------------------------------------------------
FONT_FAMILY = "Times New Roman"
COLOR_PRIMARY = RGBColor(0x1A, 0x23, 0x7E)    # Deep Navy
COLOR_BODY = RGBColor(0x22, 0x22, 0x22)       # Charcoal Body Text
COLOR_HEADER_BG = "E8EEF5"                    # Soft Table Header Blue
COLOR_BORDER = "CCCCCC"                       # Soft Border Grey

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Set inner padding for table cell."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('w:top', top), ('w:bottom', bottom), ('w:left', left), ('w:right', right)]:
        node = OxmlElement(m)
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def set_cell_bg(cell, hex_color):
    """Set cell background color."""
    shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading)

def set_table_borders(table):
    """Apply clean academic borders to table."""
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

def add_header_footer(section, is_cover=False):
    """Configure running academic header and footer."""
    if is_cover:
        section.different_first_page_header_footer = True
        return

    # Header: "Data Engineering\tClass: D12A\tCA 1: Mini Project"
    header = section.header
    p_head = header.paragraphs[0]
    p_head.text = ""
    run1 = p_head.add_run("Data Engineering\tClass: D12A\tCA 1: Mini Project")
    run1.font.name = FONT_FAMILY
    run1.font.size = Pt(10)
    run1.font.color.rgb = RGBColor(0x44, 0x44, 0x44)

    # Footer: "RAIL / SIGNAL — Indian Railways Pipeline | [Page Number]"
    footer = section.footer
    p_foot = footer.paragraphs[0]
    p_foot.text = ""
    p_foot.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run_f = p_foot.add_run("RAIL / SIGNAL — Indian Railways Data Engineering and Analytics Pipeline | ")
    run_f.font.name = FONT_FAMILY
    run_f.font.size = Pt(9.5)
    run_f.font.color.rgb = RGBColor(0x66, 0x66, 0x66)
    
    # Word dynamic page field
    fldSimple = parse_xml(r'<w:fldSimple %s w:instr="PAGE"/>' % nsdecls('w'))
    p_foot._p.append(fldSimple)

def add_styled_paragraph(doc, text, style='Normal', space_before=0, space_after=6, line_spacing=1.15, align=WD_ALIGN_PARAGRAPH.LEFT, bold=False, italic=False, font_size=11, color=COLOR_BODY):
    p = doc.add_paragraph()
    p.alignment = align
    p.paragraph_format.space_before = Pt(space_before)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = line_spacing
    
    run = p.add_run(text)
    run.font.name = FONT_FAMILY
    run.font.size = Pt(font_size)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = color
    return p

def add_bullet_item(doc, text, bold_prefix="", font_size=10.5, space_after=4):
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.15
    
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.font.name = FONT_FAMILY
        r_pre.font.size = Pt(font_size)
        r_pre.bold = True
        r_pre.font.color.rgb = COLOR_BODY
        
    r_body = p.add_run(text)
    r_body.font.name = FONT_FAMILY
    r_body.font.size = Pt(font_size)
    r_body.font.color.rgb = COLOR_BODY
    return p

def add_chapter_title(doc, number, title):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(10)
    p.paragraph_format.keep_with_next = True
    
    run = p.add_run(f"{number}. {title.upper()}:")
    run.font.name = FONT_FAMILY
    run.font.size = Pt(14)
    run.bold = True
    run.font.color.rgb = RGBColor(0x1A, 0x23, 0x7E)
    return p

def add_section_heading(doc, num_str, title):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    
    run = p.add_run(f"{num_str} {title}")
    run.font.name = FONT_FAMILY
    run.font.size = Pt(12)
    run.bold = True
    run.font.color.rgb = RGBColor(0x11, 0x11, 0x11)
    return p

def add_styled_table(doc, headers, data, col_widths=None):
    table = doc.add_table(rows=len(data) + 1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_table_borders(table)
    
    # Header Row
    hdr_cells = table.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].text = ""
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.space_before = Pt(3)
        p.paragraph_format.space_after = Pt(3)
        run = p.add_run(title)
        run.font.name = FONT_FAMILY
        run.font.size = Pt(10)
        run.bold = True
        set_cell_bg(hdr_cells[i], COLOR_HEADER_BG)
        set_cell_margins(hdr_cells[i], top=100, bottom=100, left=140, right=140)
        
    # Data Rows
    for r_idx, row_data in enumerate(data):
        row_cells = table.rows[r_idx + 1].cells
        bg = "FFFFFF" if r_idx % 2 == 0 else "F9FBFD"
        for c_idx, val in enumerate(row_data):
            row_cells[c_idx].text = ""
            p = row_cells[c_idx].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.space_before = Pt(2.5)
            p.paragraph_format.space_after = Pt(2.5)
            run = p.add_run(str(val))
            run.font.name = FONT_FAMILY
            run.font.size = Pt(9.5)
            set_cell_bg(row_cells[c_idx], bg)
            set_cell_margins(row_cells[c_idx], top=80, bottom=80, left=140, right=140)
            
    # Set Widths if specified
    if col_widths:
        for row in table.rows:
            for idx, width in enumerate(col_widths):
                row.cells[idx].width = Inches(width)
                
    doc.add_paragraph().paragraph_format.space_after = Pt(6)
    return table

def add_image_with_caption(doc, img_path, caption_text, width=Inches(6.0)):
    if not os.path.exists(img_path):
        print(f"Warning: Image not found: {img_path}")
        return
    p_img = doc.add_paragraph()
    p_img.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_img.paragraph_format.space_before = Pt(8)
    p_img.paragraph_format.space_after = Pt(4)
    p_img.paragraph_format.keep_with_next = True
    run_img = p_img.add_run()
    run_img.add_picture(img_path, width=width)
    
    p_cap = doc.add_paragraph()
    p_cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_cap.paragraph_format.space_before = Pt(2)
    p_cap.paragraph_format.space_after = Pt(10)
    run_cap = p_cap.add_run(caption_text)
    run_cap.font.name = FONT_FAMILY
    run_cap.font.size = Pt(10)
    run_cap.bold = True
    run_cap.font.color.rgb = RGBColor(0x33, 0x33, 0x33)

print("Report generator helpers initialized.")
