import streamlit as st
from pypdf import PdfReader
import re
import datetime
import calendar
import io
import html
from PIL import Image

# ReportLab untuk membuat PDF murni
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as RLImage, KeepTogether
)
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT, TA_LEFT

# Konfigurasi Halaman & Responsif HP
st.set_page_config(
    page_title="KUNLAP Generator - Kemendesa",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ----------------- INJEKSI CSS MODERN & RESPONSIF -----------------
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

    .stFileUploader, .stSelectbox, .stDateInput, .stTextArea {
        background: transparent !important;
        padding: 0 !important;
        border: none !important;
        margin-bottom: 14px;
    }

    .stButton > button {
        width: 100%;
        background: linear-gradient(135deg, #2563EB 0%, #1D4ED8 100%) !important;
        color: #FFFFFF !important;
        font-weight: 600;
        padding: 12px 20px;
        border-radius: 12px;
        border: none;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.35);
        font-size: 1rem;
    }

    @media (max-width: 768px) {
        .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-top: 1rem !important;
        }
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header-card">
    <h2>📋 Generator Laporan KUNLAP</h2>
    <p>Pilih jenjang, tanggal cetak, dan unggah berkas DRP untuk membuat dokumen PDF resmi siap cetak.</p>
</div>
""", unsafe_allow_html=True)

# ----------------- LANGKAH 1: PENGATURAN AWAL -----------------
st.markdown("##### ⚙️ Langkah 1: Pengaturan Awal")
c_set1, c_set2 = st.columns(2)
with c_set1:
    jenjang_selected = st.selectbox(
        "Jenjang Jabatan:",
        ["PD", "PLD", "TAPM"],
        index=0
    )
with c_set2:
    today = datetime.date.today()
    tgl_cetak = st.date_input("Tanggal Cetak Dokumen:", today)

# ----------------- LANGKAH 2: UNGGAH BERKAS -----------------
st.markdown("##### 📁 Langkah 2: Unggah Berkas")
col_up1, col_up2 = st.columns(2)
with col_up1:
    uploaded_pdf = st.file_uploader("PDF DRP Bulanan", type=["pdf"])
with col_up2:
    uploaded_ttd = st.file_uploader("Foto Tanda Tangan (Opsional: PNG/JPG)", type=["png", "jpg", "jpeg"])

# ----------------- FUNGSI EKSTRAKSI DATA PDF -----------------
def clean_word(txt):
    if not txt:
        return ""
    for junk in ["IDENTITAS", "TPP", "LOKASI", "PENUGASAN", "Nama", "NIK", "Posisi", "Jabatan", "Desa", "Kecamatan", "Kabupaten", "Provinsi"]:
        txt = re.sub(rf"\b{junk}\b", "", txt, flags=re.IGNORECASE)
    return txt.strip(": -")

def safe_text(txt):
    if not txt:
        return ""
    return html.escape(str(txt).strip())

@st.cache_data(show_spinner=False)
def parse_drp_pdf(pdf_bytes):
    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = ""
    for page in reader.pages:
        txt = page.extract_text()
        if txt:
            full_text += txt + "\n"

    # Ekstraksi Nama & Identitas Riil Langsung dari Berkas PDF
    def extract_field(pattern, text):
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            val = m.group(1).strip()
            # Putus jika menabrak label berikutnya
            val = re.split(r"\n|Posisi|Jabatan|LOKASI|NIK|Provinsi|Kabupaten|Kecamatan|Desa", val)[0]
            return clean_word(val)
        return ""

    nama_val = extract_field(r"Nama\s*:\s*([^\n\r]+)", full_text)
    nik_val = extract_field(r"N\s*[I|1]\s*K\s*:\s*([0-9\s]+)", full_text).replace(" ", "")
    kec_val = extract_field(r"Kecamatan\s*:\s*([^\n\r]+)", full_text)
    kab_val = extract_field(r"Kabupaten(?:/Kota)?\s*:\s*([^\n\r]+)", full_text)
    prov_val = extract_field(r"Provinsi\s*:\s*([^\n\r]+)", full_text)
    
    per_m = re.search(r"Periode:\s*([A-Za-z]+)\s*(\d{4})", full_text, flags=re.IGNORECASE)
    if per_m:
        bln_txt = per_m.group(1).title()
        thn_txt = per_m.group(2)
    else:
        bln_txt = "Juli"
        thn_txt = "2026"

    info = {
        "nik": nik_val if nik_val else "-",
        "nama": nama_val if nama_val else "Nama Tenaga Pendamping",
        "kecamatan": kec_val if kec_val else "-",
        "kabupaten": kab_val if kab_val else "-",
        "provinsi": prov_val if prov_val else "-",
        "bulan_str": bln_txt,
        "tahun_str": thn_txt,
        "periode": f"{bln_txt} Tahun {thn_txt}"
    }

    blocks = re.split(r"Deskripsi kegiatan:\s*\(Kunjungan Lapangan\)", full_text)
    kunlap_entries = []
    hasil_per_desa = {}
    
    topik_ditemukan = {
        "rkpdes": set(),
        "monev": set(),
        "stunting": set(),
        "bumdes": set(),
        "indeks_desa": set()
    }

    bulan_dict = {
        "januari": "01", "februari": "02", "maret": "03", "april": "04",
        "mei": "05", "juni": "06", "juli": "07", "agustus": "08",
        "september": "09", "oktober": "10", "november": "11", "desember": "12"
    }

    for b in blocks[1:]:
        loc_match = re.search(r"Lokasi:\s*([^\n\r]+)", b)
        date_str_match = re.search(r"Hari/Tanggal:\s*[A-Za-z]+,\s*(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", b)
        alt_date = re.search(r"(\d{2})/(\d{2})/(\d{2})", b)
        
        if date_str_match:
            d = str(int(date_str_match.group(1)))
            bln = bulan_dict.get(date_str_match.group(2).lower(), "07")
            thn = date_str_match.group(3)
            tgl_formatted = f"{d}-{bln}-{thn}"
        elif alt_date:
            d = str(int(alt_date.group(1)))
            bln = alt_date.group(2)
            thn = "20" + alt_date.group(3)
            tgl_formatted = f"{d}-{bln}-{thn}"
        else:
            tgl_formatted = "-"

        desa = "Desa Dampingan"
        if loc_match:
            parts = [clean_word(p) for p in loc_match.group(1).split("/") if clean_word(p)]
            if parts:
                desa = parts[-1].title()

        kunlap_entries.append({
            "tanggal": tgl_formatted,
            "kecamatan": info["kecamatan"].title(),
            "desa": desa
        })

        b_low = b.lower()
        if "rkp" in b_low or "rpjm" in b_low:
            topik_ditemukan["rkpdes"].add(desa)
        if "monev" in b_low or "apbdes" in b_low or "opname" in b_low:
            topik_ditemukan["monev"].add(desa)
        if "stunting" in b_low or "ehdw" in b_low or "kpm" in b_low:
            topik_ditemukan["stunting"].add(desa)
        if "bumdes" in b_low or "bum desa" in b_low:
            topik_ditemukan["bumdes"].add(desa)
        if "indeks desa" in b_low or "idm" in b_low:
            topik_ditemukan["indeks_desa"].add(desa)

        outputs = re.findall(r"Output/Hasil:\s*(.+?)(?=(?:Pukul|\Z))", b, flags=re.DOTALL)
        if outputs:
            clean_output = " ".join([re.sub(r"\s+", " ", o).strip() for o in outputs])
            clean_output = re.sub(r"\d{1,2}[\.:]\d{2}\s*WIB.*$", "", clean_output).strip()
            if desa not in hasil_per_desa and clean_output:
                hasil_per_desa[desa] = clean_output

    kec = info["kecamatan"].title()
    total_hari = len(kunlap_entries)
    
    tujuan_paras = [
        f"Kegiatan pendampingan dan monitoring lapangan selama {total_hari} hari kerja pada periode {info['periode']} "
        f"di wilayah Kecamatan {kec} dilaksanakan dalam rangka mendukung efektivitas tata kelola pemerintahan desa, akuntabilitas pengelolaan sumber daya desa, serta kepatuhan terhadap peraturan perundang-undangan yang berlaku."
    ]
    
    fokus_tujuan = []
    if topik_ditemukan["rkpdes"]:
        fokus_tujuan.append("fasilitasi tahapan penyusunan Rencana Kerja Pemerintah Desa (RKPDes) melalui pencermatan pagu indikatif, pengkajian ulang dokumen RPJM Desa, serta penentuan skala prioritas program tahun mendatang")
    if topik_ditemukan["monev"]:
        fokus_tujuan.append("pelaksanaan Monitoring dan Evaluasi (Monev) pengelolaan APBDes guna memastikan kesesuaian antara penyerapan anggaran dengan realisasi fisik pekerjaan di lapangan serta ketertiban administrasi pertanggungjawaban (SPJ)")
    if topik_ditemukan["indeks_desa"]:
        fokus_tujuan.append("pendampingan pemutakhiran data Indeks Desa guna merefleksikan status perkembangan desa")
    if topik_ditemukan["stunting"]:
        fokus_tujuan.append("penguatan kapasitas Kader Pembangunan Manusia (KPM) dalam pemutakhiran data gizi dan layanan stunting melalui aplikasi eHDW")
    if topik_ditemukan["bumdes"]:
        fokus_tujuan.append("evaluasi kelembagaan dan fasilitasi pemeringkatan Badan Usaha Milik Desa (BUM Desa)")

    if fokus_tujuan:
        tujuan_paras.append(
            f"Fokus kegiatan pendampingan bulan ini diarahkan pada beberapa agenda strategis, meliputi: {'; '.join(fokus_tujuan)}."
        )
    tujuan = "\n\n".join(tujuan_paras)

    hasil_list = []
    for desa, desc in list(hasil_per_desa.items())[:4]:
        sentences = [s.strip() for s in desc.split(".") if len(s.strip()) > 15]
        ringkasan = ". ".join(sentences[:2]) + "." if sentences else desc
        hasil_list.append(f"Hasil pendampingan di Desa {desa} menunjukkan bahwa {ringkasan.lower() if ringkasan.startswith('Ter') else ringkasan}")
    
    hasil = "\n\n".join(hasil_list) if hasil_list else "Kegiatan pendampingan lapangan terlaksana dengan tertib sesuai target penugasan."

    rtl_items = []
    if topik_ditemukan["rkpdes"]:
        rtl_items.append("Mengarahkan Tim Penyusun RKPDes untuk segera merampungkan draf dokumen rancangan berdasarkan pagu indikatif.")
    if topik_ditemukan["monev"]:
        rtl_items.append("Mendorong pemerintah desa dan TPK untuk melengkapi kekurangan dokumen SPJ perpajakan serta merapikan prasasti proyek.")
    if not rtl_items:
        rtl_items.append("Melakukan pendampingan lanjutan terhadap penyelesaian administrasi desa dan evaluasi capaian kegiatan.")
    rtl = " ".join(rtl_items)

    rek_items = [
        "Pemerintah desa agar terus meningkatkan kualitas perencanaan pembangunan desa berbasis data riil dan musyawarah partisipatif.",
        "Tim Penyusun RKPDes perlu memastikan seluruh usulan kegiatan telah melalui proses verifikasi dan pencermatan RPJM Desa secara cermat.",
        "Pemerintah desa dan TPK agar mempercepat penyelesaian administrasi SPJ belanja serta realisasi fisik yang belum tuntas 100%.",
        "Kelengkapan dokumen administrasi keuangan desa harus terus ditertibkan guna kelancaran evaluasi dan pengajuan tahap berikutnya.",
        "Meningkatkan koordinasi rutin antara pemerintah desa, kecamatan, dan Tenaga Pendamping Profesional demi terwujudnya tata kelola desa yang baik."
    ]
    rekomendasi = "\n".join(rek_items)

    narasi = {
        "tujuan": tujuan,
        "hasil": hasil,
        "rtl": rtl,
        "rekomendasi": rekomendasi
    }
    return info, kunlap_entries, narasi

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
    
    style_title = ParagraphStyle(
        'DocTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=15, alignment=TA_CENTER
    )
    style_heading = ParagraphStyle(
        'SectionHeading', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=14, spaceBefore=8, spaceAfter=4
    )
    style_body = ParagraphStyle(
        'BodyJustify', parent=styles['Normal'], fontName='Helvetica', fontSize=9.5, leading=13.5, alignment=TA_JUSTIFY, spaceAfter=6
    )
    style_bullet = ParagraphStyle(
        'BulletJustify', parent=styles['Normal'], fontName='Helvetica', fontSize=9.5, leading=13.5, alignment=TA_JUSTIFY, leftIndent=15, firstLineIndent=-10, spaceAfter=4
    )
    style_cell = ParagraphStyle('TableCell', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12)
    style_cell_center = ParagraphStyle('TableCellCenter', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12, alignment=TA_CENTER)
    style_cell_bold = ParagraphStyle('TableCellBold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=12, alignment=TA_CENTER)

    elements = []

    jenjang_map = {
        "PD": ("PD", "PENDAMPING DESA"),
        "PLD": ("PLD", "PENDAMPING LOKAL DESA"),
        "TAPM": ("TAPM", "TENAGA AHLI PEMBERDAYAAN MASYARAKAT")
    }
    posisi_val, jabatan_val = jenjang_map.get(jenjang_pilihan, ("PD", "PENDAMPING DESA"))

    elements.append(Paragraph("LAPORAN KUNJUNGAN LAPANGAN BULANAN", style_title))
    elements.append(Paragraph(jabatan_val, style_title))
    elements.append(Paragraph(f"Bulan {safe_text(info['periode'])}", style_title))
    elements.append(Spacer(1, 10))

    # A. Identitas
    elements.append(Paragraph("A. Identitas", style_heading))
    id_data = [
        [Paragraph("NIK", style_cell), Paragraph(":", style_cell), Paragraph(safe_text(info["nik"]), style_cell)],
        [Paragraph("Nama Lengkap", style_cell), Paragraph(":", style_cell), Paragraph(safe_text(info["nama"]), style_cell)],
        [Paragraph("Kecamatan", style_cell), Paragraph(":", style_cell), Paragraph(safe_text(info["kecamatan"]), style_cell)],
        [Paragraph("Kabupaten/Kota", style_cell), Paragraph(":", style_cell), Paragraph(safe_text(info["kabupaten"]), style_cell)],
        [Paragraph("Provinsi", style_cell), Paragraph(":", style_cell), Paragraph(safe_text(info["provinsi"]), style_cell)],
        [Paragraph("Posisi", style_cell), Paragraph(":", style_cell), Paragraph(posisi_val, style_cell)],
        [Paragraph("Jabatan", style_cell), Paragraph(":", style_cell), Paragraph(jabatan_val, style_cell)],
    ]
    t_id = Table(id_data, colWidths=[3.2 * cm, 0.3 * cm, 13.5 * cm])
    t_id.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ('TOPPADDING', (0,0), (-1,-1), 1),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(t_id)
    elements.append(Spacer(1, 6))

    # B. Waktu Pelaksanaan Kunjungan Lapangan
    elements.append(Paragraph("B. Waktu Pelaksanaan Kunjungan Lapangan", style_heading))
    t_data = [
        [
            Paragraph("Hari ke", style_cell_bold),
            Paragraph("Waktu<br/>(Tgl/Bln/Thn)", style_cell_bold),
            Paragraph("Lokasi Kunjungan", style_cell_bold),
            ""
        ],
        [
            Paragraph("1", style_cell_center),
            Paragraph("2", style_cell_center),
            Paragraph("Kecamatan", style_cell_center),
            Paragraph("Desa", style_cell_center)
        ]
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
        ('BOX', (0, -1), (-1, -1), 0.5, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    elements.append(t_kunlap)
    elements.append(Spacer(1, 10))

    # C, D, E, F
    elements.append(Paragraph("C. Tujuan Kunjungan Lapangan", style_heading))
    for p in custom_text["tujuan"].split("\n\n"):
        if p.strip():
            elements.append(Paragraph(safe_text(p.strip()), style_body))

    elements.append(Paragraph("D. Hasil Kunjungan Lapangan", style_heading))
    for p in custom_text["hasil"].split("\n\n"):
        if p.strip():
            elements.append(Paragraph(safe_text(p.strip()), style_body))

    elements.append(Paragraph("E. Langkah Tindak Lanjut Penanganan Masalah :", style_heading))
    for p in custom_text["rtl"].split("\n\n"):
        if p.strip():
            elements.append(Paragraph(safe_text(p.strip()), style_body))

    elements.append(Paragraph("F. Rekomendasi :", style_heading))
    for p in custom_text["rekomendasi"].split("\n"):
        if p.strip():
            elements.append(Paragraph(f"• {safe_text(p.strip())}", style_bullet))

    # Tanda Tangan
    elements.append(Spacer(1, 12))
    sign_block = []
    
    bln_indonesia = [
        "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
        "Juli", "Agustus", "September", "Oktober", "November", "Desember"
    ]
    tgl_cetak_str = f"{safe_text(info['kabupaten']).title()}, {tgl_cetak.day} {bln_indonesia[tgl_cetak.month]} {tgl_cetak.year}"
    
    style_sign = ParagraphStyle('SignRight', parent=styles['Normal'], fontName='Helvetica', fontSize=9.5, leading=13.5, alignment=TA_RIGHT)
    style_sign_name = ParagraphStyle('SignName', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9.5, leading=13.5, alignment=TA_RIGHT)

    sign_block.append(Paragraph(tgl_cetak_str, style_sign))
    sign_block.append(Paragraph("Penyusun Laporan,", style_sign))
    
    if ttd_bytes is not None:
        sign_block.append(Spacer(1, 4))
        img_io = io.BytesIO(ttd_bytes)
        img = RLImage(img_io, width=4.0 * cm, height=2.0 * cm)
        img.hAlign = 'RIGHT'
        sign_block.append(img)
        sign_block.append(Spacer(1, 4))
    else:
        sign_block.append(Spacer(1, 40))

    # Nama riil pelapor di bawah garis tanda tangan
    sign_block.append(Paragraph(f"<u>{safe_text(info['nama'])}</u>", style_sign_name))
    elements.append(KeepTogether(sign_block))

    doc.build(elements)
    buffer.seek(0)
    return buffer

# ----------------- LANGKAH 3: PRATINJAU & EKSEKUSI CETAK -----------------
if uploaded_pdf is not None:
    pdf_bytes = uploaded_pdf.getvalue()
    with st.spinner("Memproses data laporan..."):
        info, entries, auto_narrative = parse_drp_pdf(pdf_bytes)

    st.success(f"✅ Data Terbaca: **{info['nama']}** | **{len(entries)} Hari Kunjungan**")

    st.markdown("##### 📝 Langkah 3: Pratinjau & Penyesuaian")
    tab1, tab2 = st.tabs(["📋 Matriks Kunjungan", "✍️ Narasi Laporan"])
    
    with tab1:
        st.dataframe(entries, use_container_width=True)

    with tab2:
        txt_tujuan = st.text_area("C. Tujuan Kunjungan Lapangan", auto_narrative["tujuan"], height=120)
        txt_hasil = st.text_area("D. Hasil Kunjungan Lapangan", auto_narrative["hasil"], height=150)
        txt_rtl = st.text_area("E. Langkah Tindak Lanjut", auto_narrative["rtl"], height=100)
        txt_rek = st.text_area("F. Rekomendasi", auto_narrative["rekomendasi"], height=130)

    custom_text = {
        "tujuan": txt_tujuan,
        "hasil": txt_hasil,
        "rtl": txt_rtl,
        "rekomendasi": txt_rek
    }

    ttd_bytes = uploaded_ttd.read() if uploaded_ttd is not None else None

    # Nama berkas unduhan tanpa nama orang: KUNLAP_[JENJANG]_[BULAN]_[TAHUN].pdf
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
