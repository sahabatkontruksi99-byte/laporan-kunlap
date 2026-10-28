import streamlit as st
from pypdf import PdfReader
import re
import datetime
import io
import html
import json
import os
from google import genai
from google.genai import types

# ReportLab untuk membuat PDF murni
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT

st.set_page_config(
    page_title="KUNLAP Generator - Kemendesa",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ----------------- INJEKSI CSS MODERN -----------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    .header-card {
        background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%);
        color: #FFFFFF !important;
        padding: 20px 16px;
        border-radius: 14px;
        margin-bottom: 20px;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25);
    }
    .header-card h2 {
        color: #FFFFFF !important;
        margin: 0 0 6px 0;
        font-weight: 700;
        font-size: 1.35rem;
    }
    .header-card p {
        color: #E0E7FF !important;
        margin: 0;
        font-size: 0.88rem;
        line-height: 1.4;
    }
    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
        color: #FFFFFF !important;
        font-weight: 600;
        padding: 12px 20px;
        border-radius: 12px;
        border: none;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header-card">
    <h2>📋 Generator Laporan KUNLAP (AI-Powered)</h2>
    <p>Ekstraksi otomatis berkas DRP dengan perapian narasi dinas resmi berbasis Gemini AI.</p>
</div>
""", unsafe_allow_html=True)

# ----------------- LANGKAH 1 & 2: INPUT PENGGUNA -----------------
st.markdown("##### ⚙️ Langkah 1: Pengaturan Awal")
c_set1, c_set2 = st.columns(2)
with c_set1:
    jenjang_selected = st.selectbox(
        "Jenjang Jabatan:",
        ["TAPM", "PD", "PLD"],
        index=0
    )
with c_set2:
    today = datetime.date.today()
    tgl_cetak = st.date_input("Tanggal Cetak Dokumen:", today)

st.markdown("##### 📁 Langkah 2: Unggah Berkas")
col_up1, col_up2 = st.columns(2)
with col_up1:
    uploaded_pdf = st.file_uploader("PDF DRP Bulanan", type=["pdf"])
with col_up2:
    uploaded_ttd = st.file_uploader("Foto Tanda Tangan (Opsional: PNG/JPG)", type=["png", "jpg", "jpeg"])

# ----------------- FUNGSI PARSER & AI -----------------
def clean_word(txt):
    if not txt:
        return ""
    txt = re.sub(r"[\$#\*\(\)]", "", txt)
    for junk in ["IDENTITAS", "TPP", "LOKASI", "PENUGASAN", "Nama", "NIK", "Posisi", "Jabatan", "Desa", "Kecamatan", "Kabupaten", "Provinsi"]:
        txt = re.sub(rf"\b{junk}\b", "", txt, flags=re.IGNORECASE)
    return txt.strip(": -")

def safe_text(txt):
    if not txt:
        return ""
    return html.escape(str(txt).strip())

def generate_narasi_ai(kegiatan_list, role, info):
    # Mengambil key dari secrets Streamlit Cloud
    api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))
    if not api_key:
        raise ValueError("API Key belum disetel di Secrets Streamlit Cloud.")

    client = genai.Client(api_key=api_key)
    
    kegiatan_teks = "\n".join([
        f"- Kunjungan tgl {k['tanggal']} di {k['kecamatan']} ({k['desa']}): {k['uraian']}" 
        for k in kegiatan_list
    ])

    prompt = f"""
    Anda adalah seorang penyusun laporan resmi Tenaga Pendamping Profesional Kementerian Desa (Kemendesa).
    Susun narasi resmi Laporan Kunjungan Lapangan Bulanan (KUNLAP) untuk jenjang jabatan: {role}.
    Wilayah Penugasan: Kabupaten {info['kabupaten']}, Provinsi {info['provinsi']}.
    Periode Pelaporan: {info['periode']}.

    Berikut catatan log aktivitas riil kunjungan lapangan yang telah dilaksanakan:
    ---
    {kegiatan_teks}
    ---

    Instruksi Penulisan:
    1. Gaya bahasa HARUS baku, formal kedinasan, padat, dan mengalir profesional. Hindari gaya buku harian seperti 'Hari ini kami...', 'Pada hari Rabu...', dsb.
    2. Bagian TUJUAN: Buat 1 sampai 2 paragraf padat yang merangkum maksud pendampingan makro serta isu-isu teknis yang dikawal (stunting, eHDW, APBDes, BUMDes, monev DD).
    3. Bagian HASIL: Buat dalam bentuk poin-poin tematik ringkas (gunakan tanda strip '- ' di awal tiap baris) yang merangkum capaian riil per bidang/desa, jangan ada kalimat terpotong.
    4. Bagian TINDAK LANJUT: Buat 3-4 langkah aksi konkret berurutan (1., 2., dst).
    5. Bagian REKOMENDASI: Buat 3-4 rekomendasi operasional menggunakan tanda strip '- ' di awal baris.

    Output HARUS berupa JSON valid tanpa teks pengantar:
    {{
        "tujuan": "paragraf tujuan...",
        "hasil": "- Capaian bidang 1...\\n- Capaian bidang 2...",
        "rtl": "1. Langkah satu...\\n2. Langkah dua...",
        "rekomendasi": "- Rekomendasi satu...\\n- Rekomendasi dua..."
    }}
    """

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    return json.loads(response.text)

@st.cache_data(show_spinner=False)
def parse_drp_pdf(pdf_bytes, selected_role):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = ""
    for page in reader.pages:
        txt = page.extract_text()
        if txt:
            full_text += txt + "\n"

    def extract_field(pattern, text):
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            val = re.split(r"\n|Posisi|Jabatan|LOKASI|NIK|Provinsi|Kabupaten|Kecamatan|Desa", val)[0]
            return clean_word(val)
        return ""

    nama_val = extract_field(r"Nama\s*:\s*([^\n\r]+)", full_text)
    nik_val = extract_field(r"N\s*[I|1]\s*K\s*:\s*([0-9\s]+)", full_text).replace(" ", "")
    kec_val = extract_field(r"Kecamatan\s*:\s*([^\n\r]+)", full_text)
    kab_val = extract_field(r"Kabupaten(?:/Kota)?\s*:\s*([^\n\r]+)", full_text)
    prov_val = extract_field(r"Provinsi\s*:\s*([^\n\r]+)", full_text)

    # Kosongkan kecamatan untuk jenjang TAPM
    kec_terpilih = "-" if selected_role == "TAPM" or not kec_val else kec_val

    per_m = re.search(r"Periode:\s*([A-Za-z]+)\s*(\d{4})", full_text, flags=re.IGNORECASE)
    if per_m:
        bln_txt = per_m.group(1).title()
        thn_txt = per_m.group(2)
    else:
        bln_txt = "Oktober"
        thn_txt = "2026"

    info = {
        "nik": nik_val if nik_val else "-",
        "nama": nama_val if nama_val else "Nama Tenaga Pendamping",
        "kecamatan": kec_terpilih,
        "kabupaten": kab_val if kab_val else "BOJONEGORO",
        "provinsi": prov_val if prov_val else "JAWA TIMUR",
        "bulan_str": bln_txt,
        "tahun_str": thn_txt,
        "periode": f"{bln_txt} Tahun {thn_txt}"
    }

    kunlap_section_match = re.search(
        r"DAFTAR LAPORAN KUNJUNGAN LAPANGAN(.*?)(?:Total Laporan Kunjungan Lapangan|DATA CUTI|\Z)", 
        full_text, 
        re.DOTALL
    )
    kunlap_raw_text = kunlap_section_match.group(1) if kunlap_section_match else full_text

    item_pattern = re.compile(
        r"(?:(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\s+.*?)?Deskripsi kegiatan:\s*\(Kunjungan Lapangan\)\s*Lokasi:\s*([^\n\r]+)(.*?)(?=(?:\d+\s+\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|Deskripsi kegiatan:|\Z|DATA CUTI))",
        re.DOTALL
    )
    
    matches = item_pattern.findall(kunlap_raw_text)
    kunlap_entries = []
    kegiatan_lengkap = []

    for idx, (tgl_raw, raw_loc, body) in enumerate(matches):
        parts = [clean_word(p) for p in raw_loc.split("/") if clean_word(p)]
        if len(parts) >= 4:
            row_kec = parts[2].title()
            row_desa = parts[3].title()
        elif len(parts) == 3:
            row_kec = parts[2].title()
            row_desa = "-"
        else:
            row_kec = info["kabupaten"].title()
            row_desa = parts[-1].title() if parts else "-"

        if tgl_raw:
            tgl_clean = tgl_raw.replace("$", "").strip()
            t_parts = re.split(r"[\/\-]", tgl_clean)
            if len(t_parts) == 3:
                d, m, y = t_parts
                row_tgl = f"{int(d)}-{m.zfill(2)}-{'20'+y if len(y)==2 else y}"
            else:
                row_tgl = tgl_clean
        else:
            row_tgl = f"Kunjungan-{idx+1}"

        kunlap_entries.append({
            "tanggal": row_tgl,
            "kecamatan": row_kec,
            "desa": row_desa
        })

        body_clean = re.sub(r"\s+", " ", body).strip()
        kegiatan_lengkap.append({
            "tanggal": row_tgl,
            "kecamatan": row_kec,
            "desa": row_desa,
            "uraian": body_clean[:450]
        })

    return info, kunlap_entries, kegiatan_lengkap

# ----------------- GENERATOR PDF RESMI -----------------
def generate_pdf_report(info, entries, custom_text, tgl_cetak, jenjang_pilihan, ttd_bytes):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=2.0 * cm,
        rightMargin=2.0 * cm,
        topMargin=2.0 * cm,
        bottomMargin=2.0 * cm
    )

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle('DocTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=15, alignment=TA_CENTER)
    style_heading = ParagraphStyle('SectionHeading', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=14, spaceBefore=10, spaceAfter=4)
    style_body = ParagraphStyle('BodyJustifyIndent', parent=styles['Normal'], fontName='Helvetica', fontSize=9.5, leading=14.5, alignment=TA_JUSTIFY, firstLineIndent=28.35, spaceAfter=7)
    style_bullet = ParagraphStyle('BulletJustify', parent=styles['Normal'], fontName='Helvetica', fontSize=9.5, leading=13.5, alignment=TA_JUSTIFY, leftIndent=15, firstLineIndent=-10, spaceAfter=4)
    style_cell = ParagraphStyle('TableCell', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12)
    style_cell_center = ParagraphStyle('TableCellCenter', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12, alignment=TA_CENTER)
    style_cell_bold = ParagraphStyle('TableCellBold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=12, alignment=TA_CENTER)

    elements = []

    jenjang_map = {
        "TAPM": ("TAPM", "TENAGA AHLI PEMBERDAYAAN MASYARAKAT"),
        "PD": ("PD", "PENDAMPING DESA"),
        "PLD": ("PLD", "PENDAMPING LOKAL DESA")
    }
    posisi_val, jabatan_val = jenjang_map.get(jenjang_pilihan, ("TAPM", "TENAGA AHLI PEMBERDAYAAN MASYARAKAT"))

    # Judul
    elements.append(Paragraph("LAPORAN KUNJUNGAN LAPANGAN BULANAN", style_title))
    elements.append(Paragraph(jabatan_val, style_title))
    elements.append(Paragraph(f"Bulan {safe_text(info['periode'])}", style_title))
    elements.append(Spacer(1, 10))

    # A. Identitas
    elements.append(Paragraph("A. Identitas", style_heading))
    kecamatan_tampil = "-" if jenjang_pilihan == "TAPM" else safe_text(info["kecamatan"])
    id_data = [
        [Paragraph("NIK", style_cell), Paragraph(":", style_cell_center), Paragraph(safe_text(info["nik"]), style_cell)],
        [Paragraph("Nama Lengkap", style_cell), Paragraph(":", style_cell_center), Paragraph(safe_text(info["nama"]), style_cell)],
        [Paragraph("Kecamatan", style_cell), Paragraph(":", style_cell_center), Paragraph(kecamatan_tampil, style_cell)],
        [Paragraph("Kabupaten/Kota", style_cell), Paragraph(":", style_cell_center), Paragraph(safe_text(info["kabupaten"]), style_cell)],
        [Paragraph("Provinsi", style_cell), Paragraph(":", style_cell_center), Paragraph(safe_text(info["provinsi"]), style_cell)],
        [Paragraph("Posisi", style_cell), Paragraph(":", style_cell_center), Paragraph(posisi_val, style_cell)],
        [Paragraph("Jabatan", style_cell), Paragraph(":", style_cell_center), Paragraph(jabatan_val, style_cell)],
    ]
    t_id = Table(id_data, colWidths=[3.2 * cm, 0.4 * cm, 13.4 * cm])
    t_id.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.5),
        ('TOPPADDING', (0,0), (-1,-1), 1.5),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(t_id)
    elements.append(Spacer(1, 6))

    # B. Matriks Kunjungan
    elements.append(Paragraph("B. Waktu Pelaksanaan Kunjungan Lapangan", style_heading))
    t_data = [
        [Paragraph("Hari ke", style_cell_bold), Paragraph("Waktu<br/>(Tgl/Bln/Thn)", style_cell_bold), Paragraph("Lokasi Kunjungan", style_cell_bold), ""],
        [Paragraph("1", style_cell_center), Paragraph("2", style_cell_center), Paragraph("Kecamatan", style_cell_center), Paragraph("Desa", style_cell_center)]
    ]

    for idx, e in enumerate(entries):
        t_data.append([
            Paragraph(f"Hari ke {idx + 1}", style_cell_center),
            Paragraph(safe_text(e["tanggal"]), style_cell_center),
            Paragraph(safe_text(e["kecamatan"]), style_cell_center),
            Paragraph(safe_text(e["desa"]), style_cell_center)
        ])

    t_data.append([
        Paragraph(f"<b>Total Hari Kunjungan Lapangan Bulan {safe_text(info['periode'])} : {len(entries)} Hari</b>", style_cell_bold),
        "", "", ""
    ])

    t_kunlap = Table(t_data, colWidths=[2.5 * cm, 3.5 * cm, 5.0 * cm, 6.0 * cm], repeatRows=2)
    t_kunlap.setStyle(TableStyle([
        ('SPAN', (2, 0), (3, 0)),
        ('SPAN', (0, -1), (3, -1)),
        ('ALIGN', (0, 0), (-1, 1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.black),
        ('BOX', (0, 0), (-1, -2), 0.5, colors.black),
        ('BOX', (0, -1), (-1, -1), 0.5, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    elements.append(t_kunlap)
    elements.append(Spacer(1, 10))

    # C. Tujuan
    elements.append(Paragraph("C. Tujuan Kunjungan Lapangan", style_heading))
    for p in custom_text["tujuan"].split("\n\n"):
        if p.strip():
            elements.append(Paragraph(safe_text(p.strip()), style_body))

    # D. Hasil
    elements.append(Paragraph("D. Hasil Kunjungan Lapangan", style_heading))
    for line in custom_text["hasil"].split("\n"):
        c_line = line.strip().lstrip("-•* ")
        if c_line:
            elements.append(Paragraph(f"• {safe_text(c_line)}", style_bullet))

    # E. Tindak Lanjut
    elements.append(Paragraph("E. Langkah Tindak Lanjut Penanganan Masalah :", style_heading))
    for line in custom_text["rtl"].split("\n"):
        c_line = line.strip()
        if c_line:
            elements.append(Paragraph(safe_text(c_line), style_bullet))

    # F. Rekomendasi
    elements.append(Paragraph("F. Rekomendasi :", style_heading))
    for line in custom_text["rekomendasi"].split("\n"):
        c_line = line.strip().lstrip("-•* ")
        if c_line:
            elements.append(Paragraph(f"• {safe_text(c_line)}", style_bullet))

    # Tanda Tangan
    elements.append(Spacer(1, 12))
    bln_indonesia = ["", "Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    tgl_cetak_str = f"{safe_text(info['kabupaten']).title()}, {tgl_cetak.day} {bln_indonesia[tgl_cetak.month]} {tgl_cetak.year}"
    
    style_sign = ParagraphStyle('SignRight', parent=styles['Normal'], fontName='Helvetica', fontSize=9.5, leading=13.5, alignment=TA_RIGHT)
    style_sign_name = ParagraphStyle('SignName', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9.5, leading=13.5, alignment=TA_RIGHT)

    sign_block = [
        Paragraph(tgl_cetak_str, style_sign),
        Paragraph("Penyusun Laporan,", style_sign)
    ]
    
    if ttd_bytes is not None:
        sign_block.append(Spacer(1, 4))
        img = RLImage(io.BytesIO(ttd_bytes), width=4.0 * cm, height=2.0 * cm)
        img.hAlign = 'RIGHT'
        sign_block.append(img)
        sign_block.append(Spacer(1, 4))
    else:
        sign_block.append(Spacer(1, 40))

    sign_block.append(Paragraph(f"<u>{safe_text(info['nama'])}</u>", style_sign_name))
    elements.append(KeepTogether(sign_block))

    doc.build(elements)
    buffer.seek(0)
    return buffer

# ----------------- EKSEKUSI UI -----------------
if uploaded_pdf is not None:
    pdf_bytes = uploaded_pdf.getvalue()
    with st.spinner("Membaca berkas DRP..."):
        info, entries, raw_kegiatan = parse_drp_pdf(pdf_bytes, jenjang_selected)

    st.success(f"✅ Data Terbaca: **{info['nama']}** | **{len(entries)} Hari Kunjungan**")

    # Inisialisasi state untuk narasi agar tidak memanggil AI berulang kali
    if "ai_narrative" not in st.session_state or st.session_state.get("last_uploaded") != uploaded_pdf.name:
        with st.spinner("🤖 Gemini AI sedang menyusun narasi resmi laporan kedinasan..."):
            try:
                st.session_state["ai_narrative"] = generate_narasi_ai(raw_kegiatan, jenjang_selected, info)
                st.session_state["last_uploaded"] = uploaded_pdf.name
            except Exception as e:
                st.error(f"Gagal memproses via AI: {e}. Menggunakan fallback.")
                st.session_state["ai_narrative"] = {
                    "tujuan": "Pelaksanaan kunjungan kerja dalam rangka fasilitasi dan pendampingan tata kelola desa.",
                    "hasil": "- Terlaksananya monitoring realisasi program kerja desa.",
                    "rtl": "1. Melakukan tindak lanjut evaluasi.",
                    "rekomendasi": "- Pemerintah desa agar mempercepat penyusunan administrasi pertanggungjawaban."
                }

    narrative = st.session_state["ai_narrative"]

    st.markdown("##### 📝 Langkah 3: Pratinjau & Penyesuaian Narasi")
    tab1, tab2 = st.tabs(["📋 Matriks Kunjungan", "✍️ Narasi Laporan"])
    
    with tab1:
        st.dataframe(entries, use_container_width=True)

    with tab2:
        txt_tujuan = st.text_area("C. Tujuan Kunjungan Lapangan", narrative.get("tujuan", ""), height=150)
        txt_hasil = st.text_area("D. Hasil Kunjungan Lapangan", narrative.get("hasil", ""), height=200)
        txt_rtl = st.text_area("E. Langkah Tindak Lanjut", narrative.get("rtl", ""), height=130)
        txt_rek = st.text_area("F. Rekomendasi", narrative.get("rekomendasi", ""), height=130)

    custom_text = {
        "tujuan": txt_tujuan,
        "hasil": txt_hasil,
        "rtl": txt_rtl,
        "rekomendasi": txt_rek
    }

    ttd_bytes = uploaded_ttd.getvalue() if uploaded_ttd is not None else None
    download_filename = f"KUNLAP_{jenjang_selected}_{info['bulan_str']}_{info['tahun_str']}.pdf"

    st.markdown("---")
    if st.button("🚀 Buat Dokumen PDF KUNLAP", type="primary"):
        with st.spinner("Menyusun PDF resmi..."):
            try:
                pdf_output = generate_pdf_report(
                    info, entries, custom_text, tgl_cetak, jenjang_selected, ttd_bytes
                )
                st.download_button(
                    label="📥 Unduh PDF Sekarang",
                    data=pdf_output,
                    file_name=download_filename,
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Gagal menyusun PDF: {e}")
