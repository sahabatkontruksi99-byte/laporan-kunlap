import streamlit as st
from pypdf import PdfReader
import re
import datetime
import io
import html
import json
import os
import time
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

# ----------------- GAYA CSS -----------------
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
    <h2>📋 Generator Laporan KUNLAP</h2>
    <p>Ekstraksi berkas DRP cepat dan penyusunan narasi resmi kedinasan.</p>
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

# ----------------- FUNGSI PARSER & AI CEPAT -----------------
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
    api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY"))
    if not api_key:
        raise ValueError("API Key belum disetel di Secrets Streamlit Cloud.")

    client = genai.Client(api_key=api_key)
    
    # OPTIMASI 1: Ambil hanya inti kegiatan (maksimal 90 karakter per hari) agar input sangat ringan
    kegiatan_ringkas = []
    for k in kegiatan_list:
        # Ambil kalimat pertama saja
        inti = k['uraian'].split('.')[0].strip()[:90]
        kegiatan_ringkas.append(f"- {k['kecamatan']}/{k['desa']}: {inti}")
    
    kegiatan_teks = "\n".join(kegiatan_ringkas)

    prompt = f"""
    Susun narasi resmi Laporan KUNLAP Kemendesa secara ringkas, padat, dan cepat.
    Jabatan: {role} | Wilayah: Kab. {info['kabupaten']} | Periode: {info['periode']}

    Daftar agenda singkat:
    {kegiatan_teks}

    Format WAJIB JSON valid (singkat & padat, langsung inti capaian):
    {{
        "tujuan": "1 paragraf tujuan makro dan teknis.",
        "hasil": "- Capaian 1\\n- Capaian 2\\n- Capaian 3",
        "rtl": "1. Tindak lanjut 1\\n2. Tindak lanjut 2\\n3. Tindak lanjut 3",
        "rekomendasi": "- Rekomendasi 1\\n- Rekomendasi 2\\n- Rekomendasi 3"
    }}
    """

    # OPTIMASI 2: Pasang batas token agar AI tidak membuang waktu membuat teks berlebihan
    response = client.models.generate_content(
        model="gemini-3.8-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            max_output_tokens=800,  # <-- Membatasi panjang teks agar prosesnya super cepat
            temperature=0.2         # Suhu rendah membuat respon lebih cepat dan konsisten
        )
    )
    return json.loads(response.text)

# ----------------- PEMBUATAN DOKUMEN PDF -----------------
def generate_pdf_report(info, entries, custom_text, tgl_cetak, jenjang_pilihan, ttd_bytes):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=2.0 * cm, rightMargin=2.0 * cm, topMargin=2.0 * cm, bottomMargin=2.0 * cm
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

# ----------------- LOGIKA ALUR APLIKASI -----------------
if uploaded_pdf is not None:
    pdf_bytes = uploaded_pdf.getvalue()
    info, entries, raw_kegiatan = parse_drp_pdf(pdf_bytes, jenjang_selected)

    st.success(f"✅ Berkas Terbaca: **{info['nama']}** | **{len(entries)} Hari Kunjungan**")

    # Siapkan draft narasi awal cepat (default)
    if "narasi_draft" not in st.session_state or st.session_state.get("file_aktif") != uploaded_pdf.name:
        st.session_state["file_aktif"] = uploaded_pdf.name
        st.session_state["narasi_draft"] = {
            "tujuan": f"Pelaksanaan kunjungan kerja dan pembinaan lapangan selama {len(entries)} hari kerja pada periode {info['periode']} di wilayah penugasan guna meningkatkan akuntabilitas tata kelola pemerintahan desa serta percepatan program prioritas nasional.",
            "hasil": "- Terlaksananya monitoring dan evaluasi penatausahaan keuangan desa.\n- Terfasilitasinya koordinasi kelembagaan dan pembinaan administrasi pemerintahan desa.",
            "rtl": "1. Mengawal tindak lanjut rekomendasi hasil pembinaan desa.\n2. Melakukan asistensi pelaporan dan verifikasi berkas pertanggungjawaban.",
            "rekomendasi": "- Pemerintah desa agar menyelesaikan kelengkapan dokumen administrasi tepat waktu.\n- Meningkatkan koordinasi berkala antar stakeholder desa dan pendamping."
        }

    st.markdown("##### 📝 Langkah 3: Pratinjau & Penyesuaian Narasi")
    
    # Tombol Pemicu AI Manual
    c_btn1, c_btn2 = st.columns([1.5, 2.5])
    with c_btn1:
        if st.button("✨ Buat Narasi Otomatis dengan AI"):
            with st.spinner("🤖 Menyusun narasi resmi kedinasan via Gemini AI..."):
                try:
                    hasil_ai = generate_narasi_ai(raw_kegiatan, jenjang_selected, info)
                    st.session_state["narasi_draft"] = hasil_ai
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal memanggil AI: {e}")

    tab1, tab2 = st.tabs(["📋 Matriks Kunjungan", "✍️ Narasi Laporan"])
    
    with tab1:
        st.dataframe(entries, use_container_width=True)

    with tab2:
        draft = st.session_state["narasi_draft"]
        txt_tujuan = st.text_area("C. Tujuan Kunjungan Lapangan", draft.get("tujuan", ""), height=140)
        txt_hasil = st.text_area("D. Hasil Kunjungan Lapangan", draft.get("hasil", ""), height=190)
        txt_rtl = st.text_area("E. Langkah Tindak Lanjut", draft.get("rtl", ""), height=120)
        txt_rek = st.text_area("F. Rekomendasi", draft.get("rekomendasi", ""), height=120)

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
                st.error(f"Gagal membuat PDF: {e}")
