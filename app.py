import streamlit as st
from pypdf import PdfReader
import re
import datetime
import io
import html

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

# ----------------- TAMPILAN MODERN CSS -----------------
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    .header-card {
        background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%);
        color: #FFFFFF !important;
        padding: 22px 20px;
        border-radius: 14px;
        margin-bottom: 22px;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.25);
    }
    .header-card h2 {
        color: #FFFFFF !important;
        margin: 0 0 6px 0;
        font-weight: 700;
        font-size: 1.4rem;
    }
    .header-card p {
        color: #E0E7FF !important;
        margin: 0;
        font-size: 0.90rem;
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
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.35);
        font-size: 1rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header-card">
    <h2>📋 Generator Laporan Kunjungan Lapangan (KUNLAP)</h2>
    <p>Otomatisasi laporan dinas berbasis Permendes PDT No. 3 Tahun 2025 untuk jenjang PLD, PD, dan TAPM secara instan.</p>
</div>
""", unsafe_allow_html=True)

# ----------------- ATURAN KLUSTER TEMATIK SESUAI PERMENDES 3/2025 -----------------
KLUSTER_ATURAN = {
    "Akuntabilitas Keuangan & Monev DD": [
        "apbdes", "p-apbdes", "rapbdes", "dana desa", "dd tahap", "silpa", 
        "rkd", "siskeudes", "serapan", "spj", "monev dd", "opname", "pajak"
    ],
    "Perencanaan Desa & Tata Kelola Regulasi": [
        "rkpdes", "rpjmdes", "musdes", "perdes", "perangkat desa", 
        "bpd", "penjaringan", "regulasi", "pemberdayaan", "kelembagaan"
    ],
    "Konvergensi Penanganan Stunting & eHDW": [
        "stunting", "ehdw", "ehdw learning", "kpm", "posyandu", "gizi", "ibu hamil"
    ],
    "Pengembangan Ekonomi & BUM Desa": [
        "bumdes", "bum desa", "mbg", "makan bergizi gratis", "badan hukum", "usaha desa", "pasar desa"
    ],
    "Pendataan Desa, SDGs & Perlinsos": [
        "sdgs", "pendataan", "idm", "perlinsos", "bansos", "samin", "budaya", "monografi"
    ]
}

# ----------------- LANGKAH 1 & 2: INPUT PENGGUNA -----------------
st.markdown("##### ⚙️ Langkah 1: Pengaturan Jenjang & Tanggal")
c_set1, c_set2 = st.columns(2)
with c_set1:
    jenjang_selected = st.selectbox(
        "Jenjang Jabatan Tenaga Pendamping:",
        ["PLD", "PD", "TAPM"],
        index=0
    )
with c_set2:
    today = datetime.date.today()
    tgl_cetak = st.date_input("Tanggal Cetak Dokumen:", today)

st.markdown("##### 📁 Langkah 2: Unggah Berkas DRP")
col_up1, col_up2 = st.columns(2)
with col_up1:
    uploaded_pdf = st.file_uploader("PDF DRP Bulanan", type=["pdf"])
with col_up2:
    uploaded_ttd = st.file_uploader("Foto Tanda Tangan (Opsional: PNG/JPG)", type=["png", "jpg", "jpeg"])

# ----------------- FUNGSI PARSING & LOGIKA TEMATIK -----------------
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

def deteksi_kluster(text):
    text_low = text.lower()
    for kluster, keywords in KLUSTER_ATURAN.items():
        if any(kw in text_low for kw in keywords):
            return kluster
    return "Tata Kelola & Fasilitasi Desa"

def bersihkan_uraian(raw_body):
    # Hapus judul aktivitas di awal
    c = re.sub(
        r"^(?:Koordinasi Pendampingan|Pembekalan \(IST\/OJT\)|Regulasi Tentang Desa|Peningkatan Kapasitas PD\/PLD|Fasilitasi Desa)[\.\s]*", 
        "", raw_body.strip(), flags=re.IGNORECASE
    )
    # Hapus frasa pembuka catatan harian (misal: "Hari ini kami...", "Pada hari Rabu...")
    c = re.sub(r"^(?:Hari ini[^\.]*?,\s*|Pada hari[^\.]*?,\s*|Pada tanggal[^\.]*?,\s*)", "", c, flags=re.IGNORECASE)
    c = re.sub(r"\s+", " ", c).strip()
    
    # Ambil 1-2 kalimat inti tanpa memotong angka rupiah
    sentences = [s.strip() for s in re.split(r'(?<!\d)\.(?!\d)\s*', c) if len(s.strip()) > 15]
    if sentences:
        ringkasan = ". ".join(sentences[:2]) + "."
        return ringkasan
    return c[:200] + "..." if len(c) > 200 else c

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

    # Identitas kecamatan: Kosong/strip jika TAPM, wajib terisi jika PLD / PD
    if selected_role == "TAPM" or not kec_val:
        kec_terpilih = "-"
    else:
        kec_terpilih = kec_val

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

    # Ambil bagian tabel kunjungan lapangan
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
    hasil_tabel = []
    kluster_ditemukan = set()

    for idx, (tgl_raw, raw_loc, body) in enumerate(matches):
        parts = [clean_word(p) for p in raw_loc.split("/") if clean_word(p)]
        
        # Ekstraksi lokasi sesuai hierarki
        if len(parts) >= 4:
            row_kec = parts[2].title()
            row_desa = parts[3].title()
        elif len(parts) == 3:
            row_kec = parts[2].title()
            row_desa = "-"
        else:
            row_kec = info["kabupaten"].title() if selected_role == "TAPM" else info["kecamatan"].title()
            row_desa = parts[-1].title() if parts else "-"

        # Format Tanggal
        if tgl_raw:
            tgl_clean = tgl_raw.replace("$", "").strip()
            t_parts = re.split(r"[\/\-]", tgl_clean)
            row_tgl = f"{int(t_parts[0])}-{t_parts[1].zfill(2)}-{'20'+t_parts[2] if len(t_parts[2])==2 else t_parts[2]}" if len(t_parts) == 3 else tgl_clean
        else:
            row_tgl = f"Kunjungan-{idx+1}"

        kunlap_entries.append({
            "tanggal": row_tgl,
            "kecamatan": row_kec,
            "desa": row_desa
        })

        kluster = deteksi_kluster(body)
        kluster_ditemukan.add(kluster)
        ringkasan_capaian = bersihkan_uraian(body)

        lokasi_teks = f"{row_desa}<br/>(Kec. {row_kec})" if row_desa != "-" else f"Kec. {row_kec}"
        hasil_tabel.append({
            "no": str(idx + 1),
            "waktu_lokasi": f"{row_tgl}<br/>{lokasi_teks}",
            "bidang": kluster,
            "capaian": ringkasan_capaian
        })

    # Pembentukan Narasi Cepat Berbasis Peran (Permendes 3/2025)
    total_hari = len(kunlap_entries)
    daftar_kluster_str = ", ".join(list(kluster_ditemukan)[:3]) if kluster_ditemukan else "tata kelola administrasi dan pembangunan desa"

    if selected_role == "PLD":
        wilayah_narasi = f"Desa dampingan di wilayah Kecamatan {info['kecamatan'].title()}"
        tujuan_tek = (
            f"Pelaksanaan pendampingan lapangan selama {total_hari} hari kerja pada periode {info['periode']} di {wilayah_narasi} "
            f"dilaksanakan dalam rangka memenuhi mandat tugas Pendamping Lokal Desa (PLD) sesuai Permendes PDT Nomor 3 Tahun 2025, "
            f"khususnya dalam memfasilitasi pendataan desa, perencanaan partisipatif (RKPDes/APBDes), pendampingan KPMD/kader stunting, "
            f"serta penguatan akuntabilitas tata kelola pemerintahan desa dan BUM Desa berskala lokal."
        )
        tujuan_fokus = (
            f"Secara operasional di tingkat desa dampingan, fokus kerja bulan ini diarahkan pada agenda: {daftar_kluster_str}. "
            f"Pendampingan memastikan partisipasi aktif masyarakat dan tertib administrasi SPJ kegiatan pembangunan di tingkat desa berjalan optimal."
        )
        rtl_tek = (
            "1. Melakukan pendampingan intensif kepada Pemerintah Desa dalam percepatan penginputan data Siskeudes dan kelengkapan SPJ realisasi kegiatan.\n"
            "2. Mengawal Kader Pembangunan Manusia (KPM) dalam pemutakhiran data berkala pada aplikasi eHDW serta tindak lanjut pembelajaran eHDW Learning.\n"
            "3. Mendampingi pengurus BUM Desa dalam penataan administrasi pelaporan keuangan unit usaha dan persiapan musyawarah desa pertanggungjawaban.\n"
            "4. Mengikuti koordinasi berkala bersama Pendamping Desa (PD) dan Pemerintah Desa guna sinkronisasi data capaian pembangunan bulanan."
        )
        rek_tek = (
            "Pemerintah Desa agar segera menuntaskan penyusunan dokumen laporan realisasi kegiatan fisik dan SPJ secara tertib waktu.\n"
            "Kader desa (KPM dan Kader Posyandu) didorong lebih proaktif dalam memperbarui data sasaran stunting tingkat dusun.\n"
            "Pengurus BUM Desa agar melengkapi pencatatan transaksi pembukuan dan memvalidasi inventaris aset usaha desa.\n"
            "Meningkatkan koordinasi rutin antara BPD, RT/RW, dan Pemerintah Desa untuk menjamin musyawarah perencanaan desa berjalan partisipatif."
        )
    elif selected_role == "PD":
        wilayah_narasi = f"Kecamatan {info['kecamatan'].title()}"
        tujuan_tek = (
            f"Pelaksanaan supervisi dan pendampingan lapangan selama {total_hari} hari kerja pada periode {info['periode']} di wilayah {wilayah_narasi} "
            f"diselenggarakan berdasarkan amanat Permendes PDT Nomor 3 Tahun 2025 bagi Pendamping Desa (PD) untuk mengoordinasikan percepatan penyaluran, "
            f"perencanaan, pemanfaatan, serta rekapitulasi pelaporan Dana Desa di tingkat kecamatan, memfasilitasi kerja sama antar-desa, dan melakukan mentoring berjenjang kepada PLD."
        )
        tujuan_fokus = (
            f"Fokus pendampingan kecamatan bulan ini mencakup agenda strategis: {daftar_kluster_str}. "
            f"Langkah ini ditujukan untuk meminimalisasi hambatan serapan anggaran serta menjamin keselarasan program desa dengan prioritas nasional."
        )
        rtl_tek = (
            "1. Mempercepat asistensi penyusunan dokumen Perdes Perubahan APBDes dan rekonsiliasi serapan Dana Desa di tingkat kecamatan.\n"
            "2. Melakukan mentoring teknis kepada seluruh Pendamping Lokal Desa (PLD) dalam monitoring progres pengisian aplikasi eHDW dan Monev DD.\n"
            "3. Memfasilitasi kesiapan kelembagaan BUM Desa Bersama dan pemetaan kerja sama antar-desa bidang ekonomi.\n"
            "4. Mengoordinasikan hasil evaluasi monev kecamatan kepada TAPM Kabupaten untuk penanganan anomali penatausahaan keuangan desa."
        )
        rek_tek = (
            "Kasi PMD Kecamatan dan Pemerintah Desa agar meningkatkan akselerasi verifikasi proposal pencairan dan evaluasi LPJ APBDes.\n"
            "Pendamping Lokal Desa (PLD) agar mengintensifkan fasilitasi lapangan terhadap desa yang mengalami keterlambatan penyerapan anggaran.\n"
            "Pemerintah Desa didorong mengalokasikan mandatory spending pencegahan stunting dan ketahanan pangan secara proporsional.\n"
            "Memperkuat harmonisasi koordinasi lintas sektor antara Forkopimcam, TPP Kecamatan, dan asosiasi kepala desa."
        )
    else: # TAPM
        wilayah_narasi = f"Kabupaten {info['kabupaten'].title()}"
        tujuan_tek = (
            f"Pelaksanaan kunjungan kerja dan supervisi monitoring lapangan selama {total_hari} hari kerja pada periode {info['periode']} di wilayah penugasan {wilayah_narasi} "
            f"dilaksanakan dalam rangka memenuhi tugas Tenaga Ahli Pemberdayaan Masyarakat (TAPM) sesuai Permendes PDT Nomor 3 Tahun 2025 dalam mendukung sinergitas program Organisasi "
            f"Perangkat Daerah (OPD) kabupaten/kota, percepatan dokumen penyaluran Dana Desa, pengendalian pelaksanaan tugas PD dan PLD, serta advokasi kebijakan SDGs Desa."
        )
        tujuan_fokus = (
            f"Secara operasional, penugasan berfokus pada pengawalan kluster prioritas: {daftar_kluster_str}. "
            f"Pengendalian berjenjang ini memastikan seluruh regulasi, akuntabilitas anggaran, dan kemitraan strategis desa terlaksana secara transparan dan akuntabel."
        )
        rtl_tek = (
            "1. Mendorong percepatan penyelesaian regulasi desa dan sinkronisasi berkas pencairan Dana Desa tahap berjalan bersama Dinas PMD Kabupaten.\n"
            "2. Melakukan supervisi dan verifikasi berkala terhadap penginputan data pada aplikasi Monev DD guna mitigasi keterlambatan salur.\n"
            "3. Mengawal validasi data kesiapan BUM Desa dalam mendukung program kemitraan ketahanan pangan dan Program Makan Bergizi Gratis (MBG).\n"
            "4. Melaksanakan pembinaan berjenjang dan peningkatan kapasitas bagi Tenaga Pendamping Profesional (PD dan PLD) di zona dampingan."
        )
        rek_tek = (
            "Pemerintah Desa agar segera menindaklanjuti hasil rekomendasi monitoring lapangan dan menuntaskan SPJ kegiatan fisik 100%.\n"
            "Dinas PMD dan Tim Pembina Kabupaten agar memperkuat fasilitasi verifikasi berkas permohonan badan hukum BUM Desa.\n"
            "TPP di tingkat kecamatan (PD) agar aktif memitigasi anomali pelaporan Siskeudes dan mengawal kepatuhan mandatory prioritas dana desa.\n"
            "Memperkokoh forum koordinasi tripartit antara TAPM Kabupaten, Pemerintah Daerah, dan Tenaga Pendamping Lapangan secara berkelanjutan."
        )

    tujuan_final = f"{tujuan_tek}\n\n{tujuan_fokus}"

    narasi = {
        "tujuan": tujuan_final,
        "hasil_tabel": hasil_tabel,
        "rtl": rtl_tek,
        "rekomendasi": rek_tek
    }

    return info, kunlap_entries, narasi

# ----------------- GENERATOR DOKUMEN PDF REPORTLAB -----------------
def generate_pdf_report(info, entries, custom_data, tgl_cetak, jenjang_pilihan, ttd_bytes):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=2.0 * cm,
        bottomMargin=2.0 * cm
    )

    styles = getSampleStyleSheet()
    
    style_title = ParagraphStyle('DocTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=15, alignment=TA_CENTER)
    style_heading = ParagraphStyle('SectionHeading', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=14, spaceBefore=10, spaceAfter=4)
    style_body = ParagraphStyle('BodyJustify', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=13.5, alignment=TA_JUSTIFY, firstLineIndent=22, spaceAfter=6)
    style_bullet = ParagraphStyle('BulletText', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=13, alignment=TA_JUSTIFY, leftIndent=14, firstLineIndent=-10, spaceAfter=3.5)
    
    style_cell = ParagraphStyle('TableCell', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=11.5)
    style_cell_center = ParagraphStyle('TableCellCenter', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=11.5, alignment=TA_CENTER)
    style_cell_bold = ParagraphStyle('TableCellBold', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8.5, leading=11.5, alignment=TA_CENTER)

    elements = []

    jenjang_map = {
        "PLD": ("PLD", "PENDAMPING LOKAL DESA"),
        "PD": ("PD", "PENDAMPING DESA"),
        "TAPM": ("TAPM", "TENAGA AHLI PEMBERDAYAAN MASYARAKAT")
    }
    posisi_val, jabatan_val = jenjang_map.get(jenjang_pilihan, ("PLD", "PENDAMPING LOKAL DESA"))

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
    t_id = Table(id_data, colWidths=[3.2 * cm, 0.4 * cm, 13.8 * cm])
    t_id.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.5),
        ('TOPPADDING', (0,0), (-1,-1), 1.5),
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

    t_kunlap = Table(t_data, colWidths=[2.3 * cm, 3.4 * cm, 5.2 * cm, 6.5 * cm], repeatRows=2)
    t_kunlap.setStyle(TableStyle([
        ('SPAN', (2, 0), (3, 0)),
        ('SPAN', (0, -1), (3, -1)),
        ('ALIGN', (0, 0), (-1, 1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.black),
        ('BOX', (0, 0), (-1, -2), 0.5, colors.black),
        ('BOX', (0, -1), (-1, -1), 0.5, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 2.2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.2),
    ]))
    elements.append(t_kunlap)
    elements.append(Spacer(1, 8))

    # C. Tujuan
    elements.append(Paragraph("C. Tujuan Kunjungan Lapangan", style_heading))
    for p in custom_data["tujuan"].split("\n\n"):
        if p.strip():
            elements.append(Paragraph(safe_text(p.strip()), style_body))

    # D. Matriks Capaian Hasil Kunjungan Lapangan
    elements.append(Paragraph("D. Hasil Kunjungan Lapangan (Matriks Capaian)", style_heading))
    
    t_hasil_rows = [
        [
            Paragraph("No", style_cell_bold),
            Paragraph("Waktu & Lokasi", style_cell_bold),
            Paragraph("Fokus Agenda / Bidang Tugas", style_cell_bold),
            Paragraph("Output / Capaian Lapangan", style_cell_bold)
        ]
    ]

    for row in custom_data["hasil_tabel"]:
        t_hasil_rows.append([
            Paragraph(safe_text(row["no"]), style_cell_center),
            Paragraph(row["waktu_lokasi"], style_cell),
            Paragraph(safe_text(row["bidang"]), style_cell),
            Paragraph(safe_text(row["capaian"]), style_cell)
        ])

    t_hasil = Table(t_hasil_rows, colWidths=[1.0 * cm, 3.8 * cm, 4.4 * cm, 8.2 * cm], repeatRows=1)
    t_hasil.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t_hasil)
    elements.append(Spacer(1, 8))

    # E. Tindak Lanjut
    elements.append(Paragraph("E. Langkah Tindak Lanjut Penanganan Masalah :", style_heading))
    for line in custom_data["rtl"].split("\n"):
        c_line = line.strip()
        if c_line:
            elements.append(Paragraph(safe_text(c_line), style_bullet))

    # F. Rekomendasi
    elements.append(Paragraph("F. Rekomendasi :", style_heading))
    for line in custom_data["rekomendasi"].split("\n"):
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

# ----------------- EKSEKUSI UI STREAMLIT -----------------
if uploaded_pdf is not None:
    pdf_bytes = uploaded_pdf.getvalue()
    
    with st.spinner("Memproses data DRP secara instan..."):
        info, entries, auto_data = parse_drp_pdf(pdf_bytes, jenjang_selected)

    st.success(f"✅ Data DRP Terbaca: **{info['nama']}** | Jenjang: **{jenjang_selected}** | **{len(entries)} Hari Kunjungan**")

    st.markdown("##### 📝 Langkah 3: Pratinjau & Penyesuaian")
    tab1, tab2, tab3 = st.tabs(["📋 Matriks Kunjungan", "📊 Matriks Hasil (Tabel D)", "✍️ Narasi Tujuan, RTL & Rekomendasi"])

    with tab1:
        st.dataframe(entries, use_container_width=True)

    with tab2:
        st.info("💡 Matriks Capaian Hasil Lapangan di bawah ini akan dirender langsung ke dalam Tabel Bagian D di dokumen PDF.")
        st.dataframe(auto_data["hasil_tabel"], use_container_width=True)

    with tab3:
        txt_tujuan = st.text_area("C. Tujuan Kunjungan Lapangan", auto_data["tujuan"], height=130)
        txt_rtl = st.text_area("E. Langkah Tindak Lanjut Penanganan Masalah", auto_data["rtl"], height=120)
        txt_rek = st.text_area("F. Rekomendasi", auto_data["rekomendasi"], height=120)

    custom_report_data = {
        "tujuan": txt_tujuan,
        "hasil_tabel": auto_data["hasil_tabel"],
        "rtl": txt_rtl,
        "rekomendasi": txt_rek
    }

    ttd_bytes = uploaded_ttd.getvalue() if uploaded_ttd is not None else None
    download_filename = f"KUNLAP_{jenjang_selected}_{info['bulan_str']}_{info['tahun_str']}.pdf"

    st.markdown("---")
    if st.button("🚀 Buat Dokumen PDF KUNLAP", type="primary"):
        with st.spinner("Menyusun PDF resmi A4..."):
            try:
                pdf_output = generate_pdf_report(
                    info, entries, custom_report_data, tgl_cetak, jenjang_selected, ttd_bytes
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
