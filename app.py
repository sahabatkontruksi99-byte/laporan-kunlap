import streamlit as st
from pypdf import PdfReader
import re
import datetime
import io
import html

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
    <h2>📋 Generator Laporan KUNLAP</h2>
    <p>Pilih jenjang, tanggal cetak, dan unggah berkas DRP untuk membuat dokumen PDF resmi siap cetak.</p>
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

# ----------------- FUNGSI PARSER PDF -----------------
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

    # Identitas kecamatan: kosongkan jika jabatan TAPM atau memang tidak ada isinya di DRP
    if selected_role == "TAPM" or not kec_val:
        kec_terpilih = "-"
    else:
        kec_terpilih = kec_val

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

    # Ambil bagian tabel kunjungan lapangan secara spesifik
    kunlap_section_match = re.search(
        r"DAFTAR LAPORAN KUNJUNGAN LAPANGAN(.*?)(?:Total Laporan Kunjungan Lapangan|DATA CUTI|\Z)", 
        full_text, 
        re.DOTALL
    )
    kunlap_raw_text = kunlap_section_match.group(1) if kunlap_section_match else full_text

    # Ekstraksi setiap item kunjungan lapangan
    item_pattern = re.compile(
        r"(?:(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})\s+.*?)?Deskripsi kegiatan:\s*\(Kunjungan Lapangan\)\s*Lokasi:\s*([^\n\r]+)(.*?)(?=(?:\d+\s+\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}|Deskripsi kegiatan:|\Z|DATA CUTI))",
        re.DOTALL
    )
    
    matches = item_pattern.findall(kunlap_raw_text)
    kunlap_entries = []
    uraian_kegiatan_list = []

    for idx, (tgl_raw, raw_loc, body) in enumerate(matches):
        # Bersihkan string lokasi
        parts = [clean_word(p) for p in raw_loc.split("/") if clean_word(p)]
        
        # Parsing dinamis: JAWA TIMUR / BOJONEGORO / KECAMATAN / DESA
        if len(parts) >= 4:
            row_kec = parts[2].title()
            row_desa = parts[3].title()
        elif len(parts) == 3:
            row_kec = parts[2].title()
            row_desa = "-"
        else:
            row_kec = info["kabupaten"].title()
            row_desa = parts[-1].title() if parts else "-"

        # Parsing tanggal
        if tgl_raw:
            tgl_clean = tgl_raw.replace("$", "").strip()
            t_parts = re.split(r"[\/\-]", tgl_clean)
            if len(t_parts) == 3:
                d, m, y = t_parts
                row_tgl = f"{int(d)}-{m.zfill(2)}-{'20'+y if len(y)==2 else y}"
            else:
                row_tgl = tgl_clean
        else:
            b_date = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", body)
            row_tgl = f"Kunjungan-{idx+1}" if not b_date else f"{b_date.group(1)}-{b_date.group(2)}-{b_date.group(3)}"

        kunlap_entries.append({
            "tanggal": row_tgl,
            "kecamatan": row_kec,
            "desa": row_desa
        })

       # Bersihkan pembuka bergaya catatan harian agar langsung masuk ke substansi hasil
        body_clean = re.sub(
            r"^(?:Koordinasi Pendampingan|Pembekalan \(IST\/OJT\)|Regulasi Tentang Desa|Peningkatan Kapasitas PD\/PLD)[\.\s]*", 
            "", body.strip(), flags=re.IGNORECASE
        )
        # Hapus frasa pembuka waktu seperti "Hari ini...", "Pada hari Rabu...", dsb.
        body_clean = re.sub(r"^(?:Hari ini[^\.]*?,\s*|Pada hari[^\.]*?,\s*)", "", body_clean, flags=re.IGNORECASE)
        body_clean = re.sub(r"\s+", " ", body_clean).strip()
        
        # Ambil kalimat penting pertama dan kedua untuk representasi substansi
        sentences = [s.strip() for s in re.split(r'(?<!\d)\.(?!\d)\s*', body_clean) if len(s.strip()) > 20]
        if sentences:
            ringkasan_teks = ". ".join(sentences[:2]) + "."
            lokasi_label = f"Kecamatan {row_kec}" if row_desa == "-" else f"Desa {row_desa} ({row_kec})"
            uraian_kegiatan_list.append((lokasi_label, ringkasan_teks))

    total_hari = len(kunlap_entries)
    wilayah_tugas = f"Kabupaten {info['kabupaten'].title()}" if selected_role == "TAPM" else f"Kecamatan {info['kecamatan'].title()}"

    # Pembentukan Paragraf Substantif & Panjang untuk Tujuan
    tujuan_p1 = (
        f"Pelaksanaan kunjungan kerja dan pendampingan lapangan selama {total_hari} hari kerja pada periode {info['periode']} "
        f"di wilayah penugasan {wilayah_tugas} diselenggarakan dalam rangka memperkuat kapasitas kelembagaan desa, "
        f"meningkatkan akuntabilitas tata kelola keuangan, serta mendorong percepatan pelaksanaan program prioritas nasional "
        f"dan daerah sesuai amanat regulasi Kementerian Desa, Pembangunan Daerah Tertinggal, dan Transmigrasi."
    )
    tujuan_p2 = (
        f"Secara operasional, pendampingan ditujukan untuk memastikan konvergensi program penanganan kemiskinan dan penurunan stunting "
        f"berbasis eHDW terakomodasi secara terukur dalam perencanaan desa (RKPDes dan APBDes), memfasilitasi legalitas serta kelembagaan "
        f"BUM Desa guna menyambut kemitraan strategis pasokan pangan (MBG), serta melakukan pembinaan intensif dan verifikasi berjenjang "
        f"terhadap penyaluran maupun pelaporan Dana Desa pada aplikasi Monev DD guna meminimalisasi risiko kendala administratif dan hukum di lapangan."
    )
    tujuan = f"{tujuan_p1}\n\n{tujuan_p2}"

    # Pembentukan Paragraf Panjang untuk Hasil
    hasil_list = []
    for loc, act in uraian_kegiatan_list[:6]:
        hasil_list.append(f"Pada agenda kerja di {loc}, pendampingan menghasilkan: {act}")

    if hasil_list:
        hasil_p1 = " ".join(hasil_list[:3])
        hasil_p2 = " ".join(hasil_list[3:]) if len(hasil_list) > 3 else (
            "Selain itu, seluruh evaluasi progres penyaluran Dana Desa tahap berjalan, pemutakhiran data eHDW, serta administrasi "
            "pelaporan pertanggungjawaban telah terverifikasi secara berjenjang bersama jajaran pendamping dan perangkat desa setempat."
        )
        hasil = f"{hasil_p1}\n\n{hasil_p2}"
    else:
        hasil = (
            "Terlaksananya fasilitasi koordinasi lintas sektoral, pendampingan penyusunan dokumen perencanaan desa, "
            "asistensi penginputan pelaporan pada platform Monev DD, serta verifikasi kelengkapan pertanggungjawaban administratif di seluruh lokasi binaan secara akuntabel."
        )

    rtl = (
        "1. Mendorong pemerintah desa dampingan untuk mempercepat penetapan regulasi desa terkait APBDes/P-APBDes dan menuntaskan SPJ kegiatan fisik maupun non-fisik secara tertib.\n"
        "2. Mengawal pemutakhiran data secara berkelanjutan pada sistem aplikasi eHDW dan eHDW Learning bersama Kader Pembangunan Manusia (KPM) serta perangkat desa terkait.\n"
        "3. Mengintensifkan asistensi percepatan penginputan serta perbaikan anomali data penyerapan Dana Desa pada sistem Monev DD guna memastikan kelancaran penyaluran alokasi tahap berikutnya.\n"
        "4. Menindaklanjuti fasilitasi kelembagaan dan kelengkapan dokumen badan hukum BUM Desa guna mengoptimalkan peluang kemitraan usaha produktif di tingkat wilayah."
    )

    rekomendasi = (
        "Pemerintah Desa agar segera menindaklanjuti hasil monitoring lapangan dengan menyelesaikan kelengkapan bukti administrasi SPJ serta realisasi kegiatan secara tepat waktu.\n"
        "BPD dan Pemerintah Desa diharapkan memperkuat harmonisasi dalam pembahasan rancangan peraturan desa guna menjaga tertib regulasi dan akuntabilitas penatausahaan anggaran.\n"
        "Kader desa (KPM dan operator) didorong untuk terus aktif memanfaatkan platform eHDW Learning guna peningkatan kapasitas data berbasis elektronik.\n"
        "Tenaga Pendamping Profesional di seluruh tingkatan agar terus meningkatkan sinergi koordinasi dengan jajaran Forkopimcam dan dinas terkait guna kelancaran pembinaan desa."
    )

    narasi = {
        "tujuan": tujuan,
        "hasil": hasil,
        "rtl": rtl,
        "rekomendasi": rekomendasi
    }
    return info, kunlap_entries, narasi

# ----------------- GENERATOR PDF REPORTLAB -----------------
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
        'SectionHeading', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=14, spaceBefore=10, spaceAfter=4
    )
    style_body = ParagraphStyle(
        'BodyJustifyIndent',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14.5,
        alignment=TA_JUSTIFY,
        firstLineIndent=28.35, # Indentasi alinea 1 cm
        spaceAfter=7
    )
    style_bullet = ParagraphStyle(
        'BulletJustify',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        alignment=TA_JUSTIFY,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=4
    )
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

    # Judul Dokumen
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

    # B. Matriks Waktu Pelaksanaan
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
    for p in custom_text["hasil"].split("\n\n"):
        if p.strip():
            elements.append(Paragraph(safe_text(p.strip()), style_body))

    # E. Tindak Lanjut
    elements.append(Paragraph("E. Langkah Tindak Lanjut Penanganan Masalah :", style_heading))
    for p in custom_text["rtl"].split("\n"):
        if p.strip():
            elements.append(Paragraph(safe_text(p.strip()), style_body))

    # F. Rekomendasi
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

    sign_block.append(Paragraph(f"<u>{safe_text(info['nama'])}</u>", style_sign_name))
    elements.append(KeepTogether(sign_block))

    doc.build(elements)
    buffer.seek(0)
    return buffer

# ----------------- LANGKAH 3: INTERAKSI UI -----------------
if uploaded_pdf is not None:
    pdf_bytes = uploaded_pdf.getvalue()
    with st.spinner("Membaca dan memproses laporan DRP..."):
        info, entries, auto_narrative = parse_drp_pdf(pdf_bytes, jenjang_selected)

    st.success(f"✅ Berhasil memproses data: **{info['nama']}** | **{len(entries)} Hari Kunjungan**")

    st.markdown("##### 📝 Langkah 3: Pratinjau & Penyesuaian Narasi")
    tab1, tab2 = st.tabs(["📋 Matriks Kunjungan", "✍️ Narasi Laporan"])
    
    with tab1:
        st.dataframe(entries, use_container_width=True)

    with tab2:
        txt_tujuan = st.text_area("C. Tujuan Kunjungan Lapangan", auto_narrative["tujuan"], height=160)
        txt_hasil = st.text_area("D. Hasil Kunjungan Lapangan", auto_narrative["hasil"], height=200)
        txt_rtl = st.text_area("E. Langkah Tindak Lanjut", auto_narrative["rtl"], height=140)
        txt_rek = st.text_area("F. Rekomendasi", auto_narrative["rekomendasi"], height=140)

    custom_text = {
        "tujuan": txt_tujuan,
        "hasil": txt_hasil,
        "rtl": txt_rtl,
        "rekomendasi": txt_rek
    }

    # Pembacaan aman buffer byte tanda tangan
    ttd_bytes = uploaded_ttd.getvalue() if uploaded_ttd is not None else None
    download_filename = f"KUNLAP_{jenjang_selected}_{info['bulan_str']}_{info['tahun_str']}.pdf"

    st.markdown("---")
    if st.button("🚀 Buat Dokumen PDF KUNLAP", type="primary"):
        with st.spinner("Menyusun format PDF resmi..."):
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
                st.error(f"Terjadi kesalahan saat menyusun PDF: {e}")
