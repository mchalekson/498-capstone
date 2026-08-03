"""
build_college_report.py -- regenerate the two meeting deliverables that package the college
clustering for the client, so docs/COLLEGE_CLUSTERING_REPORT.pdf and
docs/DATA_DICTIONARIES_<date>.xlsx are reproducible rather than committed binary blobs.

  1. COLLEGE_CLUSTERING_REPORT.pdf   -- 2-page companion to Sheng's OPE<->CEEB merge report;
                                        objective, method, the 6 segments, feature gaps, next steps.
  2. DATA_DICTIONARIES_<date>.xlsx   -- the modeling-dataset and schools_org_enriched dictionaries
                                        in one workbook (two tabs).

The segment table mirrors build_college_clustering.py's k=6 profile output. Prose is written for
a client audience and is intentionally hand-authored, not generated.

Run:  python build_college_report.py            # writes into ../docs/
"""
import os

import pandas as pd
from openpyxl.utils import get_column_letter
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

ETL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(ETL_DIR, ".."))
DOCS = os.path.join(REPO, "docs")
CSV = os.path.join(REPO, "csv_exports")
STAMP = "2026-08-02"  # deliverable date; keep in sync with the clustering run being packaged


def make_pdf():
    out = os.path.join(DOCS, "COLLEGE_CLUSTERING_REPORT.pdf")
    styles = getSampleStyleSheet()
    H1 = ParagraphStyle("H1", parent=styles["Title"], fontSize=18, spaceAfter=4, alignment=0)
    SUB = ParagraphStyle("SUB", parent=styles["Normal"], fontSize=9.5,
                         textColor=colors.HexColor("#444444"), spaceAfter=12, leading=13)
    H2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=12.5, spaceBefore=12, spaceAfter=4,
                        textColor=colors.HexColor("#1a1a1a"))
    BODY = ParagraphStyle("BODY", parent=styles["Normal"], fontSize=9.7, leading=13.5, spaceAfter=6)
    SMALL = ParagraphStyle("SMALL", parent=styles["Normal"], fontSize=8.3, leading=11,
                           textColor=colors.HexColor("#555555"))
    CELL = ParagraphStyle("CELL", parent=styles["Normal"], fontSize=8.2, leading=10)
    CELLB = ParagraphStyle("CELLB", parent=CELL, fontName="Helvetica-Bold")

    s = []
    s.append(Paragraph("College Clustering &mdash; Segmenting the CEEB Colleges", H1))
    s.append(Paragraph(
        "Companion to the <i>OPE&#8596;CEEB Merge Report</i> &middot; Date: " + STAMP + " &middot; "
        "Input: <font face='Courier'>ope_ceeb_scorecard_merged_clean_" + STAMP + ".csv</font> &middot; "
        "Code: <font face='Courier'>etl/build_college_clustering.py</font> &middot; "
        "<b>Exploratory first pass</b> &mdash; pattern detection, not a final model.", SUB))

    s.append(Paragraph("1.&nbsp;&nbsp;Objective", H2))
    s.append(Paragraph(
        "The merge delivers <b>what</b> each CEEB college is (identity + Scorecard metrics). This step asks "
        "<b>which colleges resemble each other</b> &mdash; grouping them by location, academic profile, price, "
        "and student funding, and surfacing the natural segments in the file. It is the secondary-goal "
        "&ldquo;cluster similar institutions / detect patterns&rdquo; applied directly to the merged data.", BODY))

    s.append(Paragraph("2.&nbsp;&nbsp;Universe and method", H2))
    s.append(Paragraph(
        "<b>Universe: 2,381 degree-granting colleges.</b> The ~30% of CEEB rows with no live federal record "
        "(closed / renamed / non-Title-IV holders &mdash; the same tail documented in the merge report) carry no "
        "metrics and are excluded, as are non-degree entities. "
        "<b>Geography was filled from IPEDS HD2023</b> (already in hand): locale/urbanicity and coordinates, which "
        "the clean merge did not carry &mdash; this lifts the &ldquo;location&rdquo; dimension from state-only to "
        "~100% coverage. Features are z-scored, reduced by PCA, and clustered with k-means (complete-case, no "
        "imputation). Admission rate, SAT and completion are <i>thinly covered by design</i> (open-admission and "
        "2-year schools are exempt from the IPEDS admissions component), so they are reported as segment "
        "<i>overlays</i>, not clustering inputs.", BODY))
    s.append(Paragraph(
        "The dominant structure is a clean two-way split (public 2-year vs. private 4-year). A six-segment cut is "
        "reported below because it is the operationally useful view.", BODY))

    s.append(Paragraph("3.&nbsp;&nbsp;The six segments", H2))
    hdr = [Paragraph(x, CELLB) for x in
           ["#", "n", "Segment (plain-English)", "Type", "Setting /<br/>region", "Med.<br/>UG",
            "Med. net<br/>price", "Pell", "Adm.", "SAT", "Compl."]]
    rows = [
        ["0", "729", "Large public community colleges", "public / assoc.", "City &middot; South",
         "7,629", "$10,400", "31%", "76%", "1159", "51%"],
        ["1", "173", "High-need small private colleges (access-oriented; likely MSI/HBCU-heavy)",
         "private / bach.", "City &middot; South", "536", "$13,996", "67%", "71%", "982", "37%"],
        ["2", "415", "Mid-size regional private colleges", "private / bach.", "City &middot; South",
         "1,097", "$22,870", "35%", "76%", "1142", "56%"],
        ["3", "465", "Small-town / rural public 2-year (most open-access)", "public / assoc.",
         "Town &middot; South", "1,710", "$10,075", "31%", "82%", "1103", "42%"],
        ["4", "300", "Selective private colleges (the elite tier)", "private / bach.",
         "City &middot; Northeast", "3,439", "$32,106", "19%", "52%", "1357", "78%"],
        ["5", "211", "Small Midwest liberal-arts privates", "private / bach.", "Town &middot; Midwest",
         "958", "$22,139", "32%", "72%", "1154", "55%"],
    ]
    data = [hdr] + [[Paragraph(c, CELL) for c in r] for r in rows]
    tbl = Table(data, colWidths=[0.22*inch, 0.32*inch, 1.75*inch, 0.72*inch, 0.82*inch, 0.5*inch,
                                 0.62*inch, 0.4*inch, 0.4*inch, 0.42*inch, 0.44*inch], repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#372a80")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f0f8")]),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    s.append(tbl)
    s.append(Paragraph(
        "Overlays (admission rate, SAT, completion) are averages over the segment members that report them; "
        "they describe the segments, they did not form them.", SMALL))

    s.append(Paragraph("4.&nbsp;&nbsp;What we have for clustering &mdash; and the gaps", H2))
    s.append(Paragraph(
        "<b>Strong (&gt;95% of the degree-granting universe):</b> size, control, degree level, tuition, net price, "
        "Pell share, and &mdash; after the HD2023 join &mdash; state, region, urbanicity, coordinates.", BODY))
    s.append(Paragraph("<b>Thin or missing (flagged for the client conversation):</b>", BODY))
    gaps = [
        "<b>Selectivity is thin</b> &mdash; admission rate 62%, SAT 42%. This is structural, not an error: "
        "open-admission and 2-year schools are exempt from the IPEDS admissions survey. Kept as an overlay.",
        "<b><font face='Courier'>sc_act_mid</font> is empty (0% populated)</b> in this vintage &mdash; dropped.",
        "<b>Student funding is a single proxy (Pell share).</b> Worth adding: % with federal loans, average "
        "aid amount &mdash; to make &ldquo;student funding&rdquo; a real dimension rather than one variable.",
        "<b>No outcomes beyond completion/retention</b> (earnings and median debt are empty in recent Scorecard "
        "vintages, as the merge report notes).",
    ]
    for g in gaps:
        s.append(Paragraph("&bull;&nbsp;&nbsp;" + g, ParagraphStyle("g", parent=BODY, leftIndent=10, spaceAfter=3)))

    s.append(Paragraph("5.&nbsp;&nbsp;Suggested next steps", H2))
    for x in [
        "Cluster <b>within</b> 2-year and 4-year separately &mdash; the sector split dominates, and finer, more "
        "actionable sub-segments emerge inside each.",
        "Add the funding variables above so the &ldquo;student funding&rdquo; dimension is more than Pell.",
        "Confirm the intended grain with the client: CEEB is the <i>score-recipient</i> (can be finer than an "
        "institution), while Scorecard reports at the institution level &mdash; the merge resolves to institution grain.",
    ]:
        s.append(Paragraph("&bull;&nbsp;&nbsp;" + x, ParagraphStyle("s", parent=BODY, leftIndent=10, spaceAfter=3)))

    s.append(Spacer(1, 8))
    s.append(Paragraph(
        "Backing data: <font face='Courier'>college_cluster_profiles_fine_" + STAMP + ".csv</font> "
        "(the table above) and <font face='Courier'>college_clustering_coverage_" + STAMP + ".csv</font> "
        "(per-feature coverage). Full per-college assignments and an interactive map are in the project dashboard.",
        SMALL))

    SimpleDocTemplate(out, pagesize=letter, topMargin=0.7*inch, bottomMargin=0.7*inch,
                      leftMargin=0.75*inch, rightMargin=0.75*inch).build(s)
    print("wrote", out)


def make_dict_workbook():
    out = os.path.join(DOCS, f"DATA_DICTIONARIES_{STAMP}.xlsx")
    sheets = {
        "modeling_dataset": os.path.join(CSV, "data_dictionary_modeling_dataset.csv"),
        "schools_org_enriched": os.path.join(DOCS, "data_dictionary_schools_org_enriched.csv"),
    }
    with pd.ExcelWriter(out, engine="openpyxl") as w:
        for name, path in sheets.items():
            df = pd.read_csv(path)
            df.to_excel(w, sheet_name=name, index=False)
            ws = w.sheets[name]
            for i, col in enumerate(df.columns, 1):
                width = min(max(len(str(col)), df[col].astype(str).str.len().quantile(0.9)), 60)
                ws.column_dimensions[get_column_letter(i)].width = width + 2
            ws.freeze_panes = "A2"
    print("wrote", out)


if __name__ == "__main__":
    make_pdf()
    make_dict_workbook()
