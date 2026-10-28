import streamlit as st
from pypdf import PdfReader
import re
import datetime
import io
import html
import os

# ReportLab untuk menghasilkan PDF resmi
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

# ----------------- STILING CSS -----------------
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
    <h2>📋 Generator Laporan KUNLAP Mandiri (Standar Permendes 3/2025)</h2>
    <p>Ekstraksi otomatis DRP dengan logika kluster tematik instan, tanpa jeda loading dan bebas kalimat terpotong.</p>
</div>
""", unsafe_allow_html=True)

# ----------------- INPUT PENGGUNA -----------------
st.markdown("##### ⚙️ Langkah 1: Pengaturan Awal")
c_set1, c_set2 = st.columns(2)
with c_set1:
    jenjang_selected = st.selectbox(
        "Jenjang Jabatan Tenaga Pendamping:",
        ["TAPM", "PD", "PLD"],
        index=0
    )
with c_set2:
    today = datetime.date.today()
    tgl_cetak = st.date_input("Tanggal Cetak Dokumen:", today)

st.markdown("##### 📁 Langkah 2: Unggah Berkas")
col_up1, col_up2 = st.columns(2)
with col_up1:
    uploaded_pdf = st.file_uploader("Unggah PDF DRP Bulanan", type=["pdf"])
with col_up2:
    uploaded_ttd = st.file_uploader("Foto Tanda Tangan (Opsional: PNG/JPG)", type=["png", "jpg", "jpeg"])

# ----------------- FUNGSI PARSER DASAR -----------------
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
    full_text = "".join([page.extract_text() or "" for page in reader.pages])

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

    # TAPM bertugas di tingkat kabupaten, kecamatan dikosongkan
    kec_terpilih = "-" if selected_role == "TAPM" or not kec_val else kec_val

    per_m = re.search(r"Periode:\s*([A-Za-z]+)\s*(\d{4})", full_text, flags=re.IGNORECASE)
    bln_txt = per_m.group(1).title() if per_m else "Oktober"
    thn_txt = per_m.group(2) if per_m else "2026"

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
            row_tgl = f"{int(t_parts[0]):02d}-{int(t_parts[1]):02d}-{'20'+t_parts[2] if len(t_parts[2])==2 else t_parts[2]}" if len(t_parts) == 3 else tgl_clean
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
            "uraian": body_clean
        })

    return info, kunlap_entries, kegiatan_lengkap

# ----------------- MESIN KLUSTER TEMATIK (GAYA SEPTEMBER) -----------------
def generate_laporan_tematik(kegiatan_list, role, info):
    full_corpus = " ".join([k["uraian"].lower() for k in kegiatan_list])
    
    desa_list = list(dict.fromkeys([k["desa"] for k in kegiatan_list if k["desa"] != "-"]))
    kec_list = list(dict.fromkeys([k["kecamatan"] for k in kegiatan_list if k["kecamatan"] != "-"]))
    
    desa_sample = ", ".join(desa_list[:4]) if desa_list else "desa-desa dampingan"
    kec_sample = ", ".join(kec_list[:3]) if kec_list else info["kabupaten"]

    has_stunting = any(w in full_corpus for w in ["stunting", "ehdw", "kpm", "gizi"])
    has_bumdes = any(w in full_corpus for w in ["bumdes", "bum desa", "mbg", "makan bergizi"])
    has_keuangan = any(w in full_corpus for w in ["apbdes", "silpa", "monev dd", "dana desa", "siskeudes"])
    has_regulasi = any(w in full_corpus for w in ["perangkat desa", "bpd", "rkpdes", "perdes", "musdes"])
    has_budaya = any(w in full_corpus for w in ["monografi", "samin", "budaya"])

    tujuan_items = []
    hasil_items = []
    rtl_items = []
    rek_items = []

    if role == "TAPM":
        # C. TUJUAN TAPM
        if has_keuangan:
            tujuan_items.append(f"Melaksanakan koordinasi bersama Pemerintah Kecamatan dan Desa (seperti di {kec_sample}) guna memfasilitasi pencermatan realisasi APBDes TA 2026, evaluasi serapan anggaran, serta penyelesaian SilPA TA 2025.")
        if has_regulasi or has_budaya:
            tujuan_items.append(f"Memfasilitasi dan mengadvokasi regulasi penataan kelembagaan desa, pembentukan panitia pengisian BPD periode 2027-2035 di Kecamatan {kec_sample}, serta penggalian potensi lokal kearifan budaya desa.")
        if has_bumdes:
            tujuan_items.append("Mendampingi pemetaan potensi dan kesiapan kelembagaan BUM Desa dan BUM Desa Bersama dalam mendukung Program Prioritas Nasional Makan Bergizi Gratis (MBG).")
        if has_stunting:
            tujuan_items.append(f"Melakukan supervisi penganggaran konvergensi stunting pada penyusunan R-APBDes TA 2027 serta pemutakhiran data akun eHDW Learning bersama KPM di {desa_sample}.")
        tujuan_items.append("Memberikan bimbingan teknis (OJT) dan supervisi berjenjang kepada Pendamping Desa (PD) dan PLD terkait optimalisasi pelaporan realisasi pemanfaatan Dana Desa pada aplikasi resmi Monev DD.")

        # D. HASIL TAPM
        if has_keuangan:
            hasil_items.append(f"Terfasilitasinya evaluasi progres APBDes TA 2026 se-wilayah kecamatan dampingan dan terbangunnya komitmen percepatan kegiatan fisik tertunda SilPA 2025 pada desa dampingan ({desa_sample}).")
        if has_bumdes:
            hasil_items.append("Terpetakannya kesiapan dan validasi data unit usaha BUM Desa se-Kabupaten Bojonegoro dalam mendukung rantai pasok penyediaan pangan Program Makan Bergizi Gratis (MBG).")
        if has_regulasi:
            hasil_items.append(f"Tersosialisasikannya tahapan teknis pengisian keanggotaan BPD periode 2027-2035 di wilayah {kec_sample} serta terasistensinya regulasi penjaringan perangkat desa agar akuntabel dan tertib aturan.")
        if has_stunting:
            hasil_items.append("Terfasilitasinya pemenuhan mandatory spending penanganan stunting pada draf R-APBDes 2027 serta tersinkronisasinya data laporan eHDW bersama KPM.")
        hasil_items.append("Meningkatnya kapasitas manajerial TPP (PD/PLD) melalui forum rakor berkala serta terverifikasinya pemutakhiran data input serapan anggaran pada laman monevdd.kemendesa.go.id.")

        # E. TINDAK LANJUT TAPM
        rtl_items.append("Mengarahkan seluruh TPP (PD dan PLD) untuk mengawal percepatan penetapan Perdes Perubahan APBDes 2026 serta penyusunan R-APBDes 2027 tepat waktu.")
        rtl_items.append("Mengintensifkan supervisi dan validasi data kelengkapan dokumen badan hukum BUM Desa dan kesiapan mitra ketahanan pangan MBG.")
        rtl_items.append("Melakukan pengawalan berkala terhadap pemutakhiran data realisasi fisik dan penyerapan anggaran secara mandiri pada aplikasi Monev DD.")

        # F. REKOMENDASI TAPM
        rek_items.append("Bagi Pemerintah Desa diharapkan mempercepat penyelesaian administrasi SPJ kegiatan fisik 100% dan penatausahaan aset desa guna kelancaran penyusunan anggaran tahun berikutnya.")
        rek_items.append("Bagi Tenaga Pendamping Profesional (PD/PLD) diimbau untuk terus meningkatkan intensitas koordinasi dengan Kasi PMD Kecamatan, memperkuat monitoring lapangan, serta aktif mengawal kepatuhan pelaporan digital desa.")

    elif role == "PD":
        # C. TUJUAN PD
        tujuan_items.append(f"Memfasilitasi percepatan penyusunan dan penetapan dokumen perencanaan dan penganggaran desa (RKPDes/APBDes) di wilayah Kecamatan {kec_sample}.")
        if has_stunting:
            tujuan_items.append("Mendampingi Kader Pembangunan Manusia (KPM) dalam pemutakhiran data stunting bulanan dan aktivasi instrumen eHDW di tingkat desa.")
        if has_bumdes:
            tujuan_items.append("Mengoordinasikan pengembangan kelembagaan BUM Desa serta penguatan unit usaha bersama antar-desa.")
        tujuan_items.append("Melakukan pendampingan pengadministrasian penyaluran Dana Desa serta mentoring teknis kepada Pendamping Lokal Desa (PLD).")

        # D. HASIL PD
        hasil_items.append(f"Terfasilitasinya sinkronisasi dokumen R-APBDes dan pengadministrasian penatausahaan APBDes di desa-desa Kecamatan {kec_sample}.")
        if has_stunting:
            hasil_items.append("Tersusunnya laporan konvergensi stunting desa dan terverifikasinya data sasaran penerima manfaat pada sistem eHDW.")
        if has_bumdes:
            hasil_items.append("Terverifikasinya profil usaha dan kelengkapan dokumen administrasi operasional BUM Desa.")
        hasil_items.append("Terekapitulasi dan terlaporkannya progres serapan Dana Desa serta terselenggaranya pendampingan rutin PLD secara berkala.")

        # E. RTL PD
        rtl_items.append("Mengawal desa dampingan agar menuntaskan penetapan Perdes APBDes tepat waktu.")
        rtl_items.append("Melakukan asistensi input pelaporan realisasi Dana Desa ke aplikasi Siskeudes dan Monev DD.")
        rtl_items.append("Meningkatkan frekuensi mentoring pendampingan kepada PLD dan KPM di desa dampingan.")

        # F. REKOMENDASI PD
        rek_items.append("Pemerintah Desa agar menjaga ketepatan waktu dalam siklus pelaporan keuangan dan penyelesaian administrasi pertanggungjawaban fisik.")
        rek_items.append("PLD dan lembaga desa diharapkan memperkokoh koordinasi tripartit bersama pihak kecamatan guna memitigasi kendala lapangan secara dini.")

    else: # PLD
        # C. TUJUAN PLD
        tujuan_items.append(f"Melakukan pendampingan langsung kepada Pemerintah Desa dan BPD di {desa_sample} dalam fasilitasi tata kelola pemerintahan dan perencanaan pembangunan lokal desa.")
        if has_stunting:
            tujuan_items.append("Mendampingi KPM dan kader posyandu dalam pencatatan dan pelaporan data penanganan stunting melalui aplikasi eHDW.")
        if has_keuangan:
            tujuan_items.append("Mendampingi kaur dan pelaksana kegiatan anggaran dalam tertib administrasi penatausahaan buku kas dan bukti SPJ fisik desa.")
        tujuan_items.append("Mencatat dan melaporkan kegiatan pendampingan harian secara aktif ke dalam Sistem Informasi Desa (SID/DRP).")

        # D. HASIL PLD
        hasil_items.append(f"Terfasilitasinya musyawarah desa, penyusunan draf perencanaan, dan tertib administrasi tata kelola pemerintahan di {desa_sample}.")
        if has_stunting:
            hasil_items.append("Terlaksananya pemutakhiran data pengukuran stunting dan terfasilitasinya koordinasi KPM bersama kader kesehatan desa.")
        if has_keuangan:
            hasil_items.append("Tertibnya kelengkapan dokumen pencairan anggaran dan terasistensinya pelaporan realisasi kegiatan pembangunan skala lokal desa.")
        hasil_items.append("Terinputnya seluruh catatan aktivitas dan pelaporan harian pada aplikasi DRP secara berkala.")

        # E. RTL PLD
        rtl_items.append("Mengawal tindak lanjut catatan evaluasi administrasi dan penyelesaian SPJ di desa dampingan.")
        rtl_items.append("Mendampingi kader desa dalam pemutakhiran data SDGs Desa dan eHDW.")
        rtl_items.append("Melakukan koordinasi intensif dengan Pendamping Desa (PD) terkait progres kegiatan lapangan.")

        # F. REKOMENDASI PLD
        rek_items.append("Pemerintah Desa agar konsisten mengedepankan prinsip transparansi dan pelibatan masyarakat dalam setiap tahapan pembangunan desa.")
        rek_items.append("Kader desa dan pengurus kelembagaan desa agar aktif memperbarui data sasaran program kerja secara berkala.")

    return {
        "tujuan": "\n".join([f"➤ {item}" for item in tujuan_items]),
        "hasil": "\n".join([f"➤ {item}" for item in hasil_items]),
        "rtl": "\n".join([f"➤ {item}" for item in rtl_items]),
        "rekomendasi": "\n".join([f"➤ {item}" for item in rek_items])
    }

# ----------------- GENERATOR PDF RESMI (PERSIS SEPTEMBER) -----------------
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
    style_bullet = ParagraphStyle('BulletText', parent=styles['Normal'], fontName='Helvetica', fontSize=9.5, leading=14, alignment=TA_JUSTIFY, leftIndent=15, firstLineIndent=-12, spaceAfter=6)
    style_cell = ParagraphStyle('TableCell', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12)
    style_cell_center = ParagraphStyle('TableCellCenter', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12, alignment=TA_CENTER)
    style_cell_bold = ParagraphStyle('TableCellBold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=12, alignment=TA_CENTER)

    elements = []

    jenjang_map = {
        "TAPM": ("TAPM", f"TAPM KABUPATEN {info['kabupaten'].upper()}"),
        "PD": ("PD", f"PENDAMPING DESA KECAMATAN {info['kecamatan'].upper()}"),
        "PLD": ("PLD", f"PENDAMPING LOKAL DESA KECAMATAN {info['kecamatan'].upper()}")
    }
    posisi_val, subheader_val = jenjang_map.get(jenjang_pilihan, ("TAPM", f"TAPM KABUPATEN {info['kabupaten'].upper()}"))

    # Judul Dokumen (Persis September)
    elements.append(Paragraph("LAPORAN KUNJUNGAN LAPANGAN BULANAN", style_title))
    elements.append(Paragraph(subheader_val, style_title))
    elements.append(Paragraph(f"Bulan {safe_text(info['bulan_str'])}, Tahun {safe_text(info['tahun_str'])}", style_title))
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
        [Paragraph("Jabatan", style_cell), Paragraph(":", style_cell_center), Paragraph(posisi_val, style_cell)],
    ]
    t_id = Table(id_data, colWidths=[3.2 * cm, 0.4 * cm, 13.4 * cm])
    t_id.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.5),
        ('TOPPADDING', (0,0), (-1,-1), 1.5),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(t_id)
    elements.append(Spacer(1, 8))

    # B. Matriks Kunjungan (Tabel 4 Kolom Rapi)
    elements.append(Paragraph("B. Waktu Pelaksanaan Kunjungan Lapangan", style_heading))
    t_data = [
        [Paragraph("Hari ke", style_cell_bold), Paragraph("Waktu<br/>(Tgl/Bln/Thn)", style_cell_bold), Paragraph("Lokasi Kunjungan", style_cell_bold), ""],
        [Paragraph("1", style_cell_center), Paragraph("2", style_cell_center), Paragraph("Kecamatan", style_cell_center), Paragraph("Desa", style_cell_center)]
    ]

    for idx, e in enumerate(entries):
        desa_label = "" if e["desa"] == "-" else safe_text(e["desa"])
        t_data.append([
            Paragraph(f"Hari ke {idx + 1}", style_cell_center),
            Paragraph(safe_text(e["tanggal"]), style_cell_center),
            Paragraph(safe_text(e["kecamatan"]), style_cell_center),
            Paragraph(desa_label, style_cell_center)
        ])

    t_data.append([
        Paragraph(f"<b>Total Hari Kunjungan Lapangan Bulan {safe_text(info['bulan_str'])} Tahun {safe_text(info['tahun_str'])} : {len(entries)} Hari</b>", style_cell_bold),
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

    # C. Tujuan Kunjungan Lapangan
    elements.append(Paragraph("C. Tujuan Kunjungan Lapangan :", style_heading))
    for line in custom_text["tujuan"].split("\n"):
        c_line = line.strip()
        if c_line:
            elements.append(Paragraph(safe_text(c_line), style_bullet))
    elements.append(Spacer(1, 4))

    # D. Hasil Kunjungan Lapangan (Gaya Tematik September)
    elements.append(Paragraph("D. Hasil Kunjungan Lapangan :", style_heading))
    for line in custom_text["hasil"].split("\n"):
        c_line = line.strip()
        if c_line:
            elements.append(Paragraph(safe_text(c_line), style_bullet))
    elements.append(Spacer(1, 4))

    # E. Tindak Lanjut Penanganan Masalah
    elements.append(Paragraph("E. Langkah Tindak Lanjut Penanganan Masalah :", style_heading))
    for line in custom_text["rtl"].split("\n"):
        c_line = line.strip()
        if c_line:
            elements.append(Paragraph(safe_text(c_line), style_bullet))
    elements.append(Spacer(1, 4))

    # F. Rekomendasi
    elements.append(Paragraph("F. Rekomendasi :", style_heading))
    for line in custom_text["rekomendasi"].split("\n"):
        c_line = line.strip()
        if c_line:
            elements.append(Paragraph(safe_text(c_line), style_bullet))

    # Blok Tanda Tangan
    elements.append(Spacer(1, 14))
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

# ----------------- LOGIKA ALUR WEB STREAMLIT -----------------
if uploaded_pdf is not None:
    pdf_bytes = uploaded_pdf.getvalue()
    with st.spinner("Membaca berkas DRP..."):
        info, entries, raw_kegiatan = parse_drp_pdf(pdf_bytes, jenjang_selected)

    st.success(f"✅ Berkas DRP Terbaca: **{info['nama']}** | **{len(entries)} Hari Kunjungan**")

    # Generate narasi tematik instan begitu PDF terbaca (0.1 detik, tanpa AI lemot)
    if "tematik_draft" not in st.session_state or st.session_state.get("file_aktif") != uploaded_pdf.name:
        st.session_state["file_aktif"] = uploaded_pdf.name
        st.session_state["tematik_draft"] = generate_laporan_tematik(raw_kegiatan, jenjang_selected, info)

    draft = st.session_state["tematik_draft"]

    st.markdown("##### 📝 Langkah 3: Pratinjau & Penyesuaian Narasi Laporan")
    tab1, tab2 = st.tabs(["📋 Matriks Kunjungan (Tabel B)", "✍️ Narasi Resmi (Bagian C, D, E, F)"])

    with tab1:
        st.dataframe(entries, use_container_width=True)

    with tab2:
        txt_tujuan = st.text_area("C. Tujuan Kunjungan Lapangan", draft.get("tujuan", ""), height=160)
        txt_hasil = st.text_area("D. Hasil Kunjungan Lapangan", draft.get("hasil", ""), height=180)
        txt_rtl = st.text_area("E. Langkah Tindak Lanjut Penanganan Masalah", draft.get("rtl", ""), height=140)
        txt_rek = st.text_area("F. Rekomendasi", draft.get("rekomendasi", ""), height=130)

    custom_text = {
        "tujuan": txt_tujuan,
        "hasil": txt_hasil,
        "rtl": txt_rtl,
        "rekomendasi": txt_rek
    }

    ttd_bytes = uploaded_ttd.getvalue() if uploaded_ttd is not None else None
    download_filename = f"KUNLAP_{jenjang_selected}_{info['bulan_str']}_{info['tahun_str']}.pdf"

    st.markdown("---")
    if st.button("🚀 Cetak PDF KUNLAP Resmi (Standar September)", type="primary"):
        with st.spinner("Menyusun PDF resmi..."):
            try:
                pdf_output = generate_pdf_report(
                    info, entries, custom_text, tgl_cetak, jenjang_selected, ttd_bytes
                )
                st.download_button(
                    label="📥 Unduh PDF Laporan KUNLAP",
                    data=pdf_output,
                    file_name=download_filename,
                    mime="application/pdf",
                    use_container_width=True
                )
            except Exception as e:
                st.error(f"Gagal menyusun PDF: {e}")
