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
    <p>Ekstraksi otomatis DRP dengan logika kluster tematik instan, narasi berbobot, dan bingkai border resmi.</p>
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

# ----------------- MESIN KLUSTER TEMATIK LEBIH MENDALAM & BERBOBOT -----------------
def generate_laporan_tematik(kegiatan_list, role, info):
    full_corpus = " ".join([k["uraian"].lower() for k in kegiatan_list])
    
    desa_list = list(dict.fromkeys([k["desa"] for k in kegiatan_list if k["desa"] != "-"]))
    kec_list = list(dict.fromkeys([k["kecamatan"] for k in kegiatan_list if k["kecamatan"] != "-"]))
    
    desa_sample = ", ".join(desa_list[:4]) if desa_list else "desa-desa dampingan"
    kec_sample = ", ".join(kec_list[:4]) if kec_list else info["kabupaten"]

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
        # C. TUJUAN TAPM (Lebih mendalam & berbobot)
        if has_keuangan:
            tujuan_items.append(
                f"Melaksanakan koordinasi teknis bersama Pemerintah Kecamatan (Kasi PMD) dan jajaran Pemerintah Desa (antara lain di Kecamatan {kec_sample}) "
                f"guna memfasilitasi penelaahan realisasi penyerapan APBDes TA 2026, evaluasi serapan Dana Desa tahap berjalan, penertiban administrasi pembukuan Siskeudes, "
                f"serta penyusunan langkah percepatan penuntasan kegiatan fisik tertunda akibat sisa lebih perhitungan anggaran (SilPA) TA 2025."
            )
        if has_regulasi or has_budaya:
            tujuan_items.append(
                f"Memfasilitasi asistensi regulasi dan advokasi kebijakan terkait penataan kelembagaan desa, tahapan persiapan pembentukan panitia pengisian keanggotaan "
                f"Badan Permusyawaratan Desa (BPD) periode 2027–2035 di wilayah {kec_sample}, serta pelaksanaan visitasi lapangan guna penggalian data kearifan lokal "
                f"dan pelestarian nilai budaya masyarakat adat/komunitas lokal (Suku Samin Sedulur Sikep di Margomulyo) dalam rangka penyusunan Monografi Desa Budaya."
            )
        if has_bumdes:
            tujuan_items.append(
                "Mendampingi identifikasi potensi, penataan tata kelola operasional, dan validasi kelengkapan legalitas badan hukum BUM Desa / BUM Desa Bersama "
                "se-Kabupaten Bojonegoro guna memastikan kesiapan kelembagaan ekonomi desa sebagai pemasok komoditas pangan lokal dalam mendukung Program Prioritas Nasional Makan Bergizi Gratis (MBG)."
            )
        if has_stunting:
            tujuan_items.append(
                f"Melakukan supervisi teknis penganggaran konvergensi pencegahan stunting pada tahapan penyusunan dokumen R-APBDes TA 2027, memastikan terpenuhinya alokasi mandatory spending, "
                f"serta memfasilitasi pendampingan Kader Pembangunan Manusia (KPM) dalam pemutakhiran data capaian layanan bulanan melalui instrumen eHDW dan eHDW Learning di {desa_sample}."
            )
        tujuan_items.append(
            f"Memberikan bimbingan teknis (On the Job Training/OJT), supervisi berjenjang, dan koordinasi berkala per zona wilayah kepada Pendamping Desa (PD) dan Pendamping Lokal Desa (PLD) "
            f"terkait percepatan pelaporan realisasi Dana Desa pada aplikasi resmi Kementerian Desa (monevdd.kemendesa.go.id) serta penguatan kapasitas pelaksanaan tugas pokok pendampingan."
        )

        # D. HASIL TAPM (Komprehensif & terukur)
        if has_keuangan:
            hasil_items.append(
                f"Terfasilitasinya evaluasi komprehensif terhadap progres pelaksanaan dan penatausahaan APBDes TA 2026 se-wilayah kecamatan dampingan, serta terbangunnya komitmen bersama "
                f"dengan kepala desa dan perangkat desa terkait percepatan penyelesaian pekerjaan fisik dan pertanggungjawaban administrasi sisa kegiatan SilPA TA 2025 pada desa-desa dampingan ({desa_sample})."
            )
        if has_bumdes:
            hasil_items.append(
                "Terpetakannya profil, portofolio unit usaha, dan kesiapan rantai pasok kelembagaan BUM Desa di Kabupaten Bojonegoro, serta tersinkronisasinya data potensi produk pangan unggulan desa "
                "dengan arahan Direktorat Jenderal PEID Kemendesa PDT guna mendukung pemenuhan bahan pangan bagi Satuan Pelayanan Pemenuhan Gizi (SPPG) pada Program Makan Bergizi Gratis (MBG)."
            )
        if has_regulasi:
            hasil_items.append(
                f"Tersosialisasikannya tahapan pembentukan panitia pengisian keanggotaan BPD periode 2027–2035 secara tertib aturan di wilayah {kec_sample}, serta terasistensinya kepatuhan perundang-undangan "
                f"dalam mekanisme seleksi penjaringan dan penyaringan perangkat desa guna menjaga integritas dan akuntabilitas tata kelola pemerintahan desa."
            )
        if has_stunting:
            hasil_items.append(
                f"Terakomodasinya alokasi anggaran penanganan dan pencegahan stunting terintegrasi pada rancangan APBDes TA 2027 sesuai pedoman prioritas penggunaan Dana Desa, serta terverifikasinya pembaruan data scorecards "
                f"layanan sasaran 1.000 Hari Pertama Kehidupan (HPK) pada aplikasi eHDW oleh KPM di desa dampingan."
            )
        hasil_items.append(
            "Meningkatnya kapasitas profesional dan kesamaan persepsi kerja TPP (PD dan PLD) di zona dampingan melalui forum koordinasi rutin, serta terverifikasinya kelengkapan penginputan data serapan, capaian output, "
            "dan bukti dukung kegiatan pemanfaatan Dana Desa 2026 secara akurat pada laman monevdd.kemendesa.go.id."
        )

        # E. TINDAK LANJUT TAPM
        rtl_items.append(
            "Mengoordinasikan dan mengarahkan seluruh jajaran TPP (PD dan PLD) untuk mengawal percepatan penetapan Peraturan Desa tentang APBDes Perubahan TA 2026 dan penyusunan draf R-APBDes TA 2027 tepat waktu."
        )
        rtl_items.append(
            "Mengintensifkan supervisi dan validasi berkas pendaftaran badan hukum BUM Desa pada portal resmi Kemendesa, serta memetakan kesiapan kemitraan operasional unit usaha pangan desa bersama dinas terkait."
        )
        rtl_items.append(
            "Melaksanakan pendampingan klinis dan asistensi berkala kepada para pendamping lapangan guna memastikan seluruh transaksi penyerapan anggaran dan dokumentasi fisik terunggah secara tuntas pada aplikasi Monev DD."
        )
        rtl_items.append(
            "Mengawal tindak lanjut rekomendasi visitasi penulisan Monografi Desa Budaya sebagai bagian dari dokumentasi pelestarian nilai kearifan lokal di wilayah Kabupaten Bojonegoro."
        )

        # F. REKOMENDASI TAPM
        rek_items.append(
            "Bagi Pemerintah Desa diharapkan senantiasa menjaga komitmen kepatuhan regulasi, mempercepat penyelesaian fisik dan administrasi SPJ kegiatan secara lengkap 100%, serta memfasilitasi optimalisasi peran kader desa (KPM dan kelembagaan masyarakat)."
        )
        rek_items.append(
            "Bagi Tenaga Pendamping Profesional (PD dan PLD) diimbau untuk meningkatkan frekuensi pendampingan lapangan, proaktif membangun komunikasi koordinatif dengan Kasi PMD Kecamatan, serta rutin memperbarui pelaporan pada Sistem Informasi Desa (SID/DRP) secara tepat waktu."
        )
        rek_items.append(
            "Bagi Dinas PMD dan Tim Pembina Tingkat Kabupaten disarankan untuk memperkuat fasilitasi verifikasi regulasi perdes dan mempercepat rekonsiliasi data serapan keuangan desa guna kelancaran penyaluran alokasi Dana Desa tahap selanjutnya."
        )

    elif role == "PD":
        # C. TUJUAN PD
        tujuan_items.append(
            f"Melaksanakan fasilitasi dan pendampingan terpadu kepada Pemerintah Desa di wilayah Kecamatan {kec_sample} dalam rangka percepatan penyusunan, pembahasan, "
            f"dan penetapan dokumen perencanaan pembangunan desa (RKPDes) dan dokumen penganggaran (APBDes/P-APBDes) agar selaras dengan prioritas nasional dan regulasi daerah."
        )
        if has_stunting:
            tujuan_items.append(
                "Mendampingi Kader Pembangunan Manusia (KPM) dalam proses pengumpulan data, pencatatan layanan ibu hamil dan baduta, pemutakhiran indikator pemantauan berkala, serta aktivasi pelaporan scorecard melalui aplikasi eHDW di tingkat desa."
            )
        if has_bumdes:
            tujuan_items.append(
                "Mengoordinasikan penguatan tata kelola kelembagaan, kelengkapan administrasi pembukuan, pendaftaran status badan hukum, serta penjajakan kerja sama usaha BUM Desa / BUM Desa Bersama antar-desa."
            )
        tujuan_items.append(
            "Melakukan fasilitasi percepatan pemenuhan dokumen persyaratan pencairan Dana Desa, penelaahan laporan pertanggungjawaban (SPJ), serta memberikan mentoring teknis operasional pendampingan kepada Pendamping Lokal Desa (PLD)."
        )

        # D. HASIL PD
        hasil_items.append(
            f"Terfasilitasinya sinkronisasi dan evaluasi draf dokumen APBDes di desa-desa wilayah Kecamatan {kec_sample}, sehingga alokasi pembiayaan program prioritas desa dan penatausahaan administrasi Siskeudes dapat berjalan tertib dan tepat waktu."
        )
        if has_stunting:
            hasil_items.append(
                "Tersusunnya laporan konvergensi pencegahan stunting tingkat desa, terverifikasinya data sasaran penerima bantuan intervensi gizi, serta terinputnya laporan triwulan pemantauan pada server aplikasi eHDW."
            )
        if has_bumdes:
            hasil_items.append(
                "Terverifikasinya profil usaha dan kelengkapan dokumen pendirian/pendaftaran badan hukum BUM Desa, serta terpetakannya potensi kerja sama usaha produktif desa di wilayah kecamatan."
            )
        hasil_items.append(
            "Terekapitulasi dan terverifikasinya progres penyaluran serta pemanfaatan Dana Desa di tingkat kecamatan, serta terlaksananya bimbingan dan pendampingan kerja rutin kepada PLD dalam menjalankan tugas fasilitasi desa."
        )

        # E. RTL PD
        rtl_items.append(
            "Mengawal pemerintah desa binaan untuk menuntaskan evaluasi dan penetapan Perdes APBDes Perubahan serta mempercepat penyusunan rancangan APBDes tahun anggaran berikutnya."
        )
        rtl_items.append(
            "Melakukan asistensi intensif kepada kaur keuangan dan operator desa dalam penginputan data penatausahaan pada Siskeudes dan sistem Monev DD."
        )
        rtl_items.append(
            "Meningkatkan frekuensi mentoring tatap muka bersama PLD dan kelembagaan desa guna memitigasi kendala administrasi lapangan secara lebih dini."
        )

        # F. REKOMENDASI PD
        rek_items.append(
            "Pemerintah Desa agar konsisten menjaga ketepatan waktu dalam siklus pelaporan keuangan, tertib melengkapi bukti fisik pertanggungjawaban (SPJ), dan memperkuat koordinasi internal bersama BPD."
        )
        rek_items.append(
            "Pemerintah Kecamatan dan Tim Pendamping agar mempererat sinergi koordinatif dalam verifikasi dokumen kelayakan pencairan anggaran guna menjamin kelancaran realisasi program pembangunan di desa."
        )

    else: # PLD
        # C. TUJUAN PLD
        tujuan_items.append(
            f"Melaksanakan pendampingan intensif dan melekat kepada Pemerintah Desa, Badan Permusyawaratan Desa (BPD), dan unsur masyarakat di {desa_sample} "
            f"dalam memfasilitasi tahapan musyawarah perencanaan desa, tertib administrasi pemerintahan desa, dan akuntabilitas pelaksanaan kegiatan pembangunan skala lokal desa."
        )
        if has_stunting:
            tujuan_items.append(
                "Mendampingi Kader Pembangunan Manusia (KPM) dan kader posyandu dalam pemantauan 5 paket layanan konvergensi stunting, pencatatan kehadiran sasaran, dan penginputan data pengukuran berkala pada instrumen eHDW."
            )
        if has_keuangan:
            tujuan_items.append(
                "Mendampingi pelaksana kegiatan anggaran (PKA) dan bendahara/kaur keuangan desa dalam penyiapan kelengkapan berkas administrasi SPJ, buku kas pembantu, serta pelaporan fisik hasil pelaksanaan kegiatan."
            )
        tujuan_items.append(
            "Mencatat seluruh rekam jejak aktivitas pendampingan, permasalahan lapangan, serta capaian hasil fasilitasi ke dalam aplikasi laporan harian Sistem Informasi Desa (SID/DRP) secara aktif dan mandiri."
        )

        # D. HASIL PLD
        hasil_items.append(
            f"Terfasilitasinya musyawarah desa, tersusunnya draf dokumen perencanaan desa partisipatif, serta terasistensinya ketertiban tata kelola administrasi pemerintahan desa di {desa_sample}."
        )
        if has_stunting:
            hasil_items.append(
                "Terlaksananya pemutakhiran data pemantauan stunting bulanan, meningkatnya pemahaman KPM dalam pengoperasian aplikasi eHDW, serta tersinkronisasinya data balita stunting bersama tenaga kesehatan desa."
            )
        if has_keuangan:
            hasil_items.append(
                "Tertibnya pemberkasan administrasi pencairan anggaran, tersusunnya dokumen pembukuan SPJ kegiatan pembangunan fisik, dan terverifikasinya kesesuaian progres capaian lapangan di desa dampingan."
            )
        hasil_items.append(
            "Terlaporkannya seluruh rangkaian log aktivitas pendampingan desa secara rutin dan akuntabel pada aplikasi DRP Kemendesa sebagai bukti pemenuhan indikator kinerja harian."
        )

        # E. RTL PLD
        rtl_items.append(
            "Mengawal pemenuhan catatan perbaikan berkas administrasi pertanggungjawaban keuangan dan kelengkapan dokumen pendukung kegiatan fisik di desa."
        )
        rtl_items.append(
            "Mendampingi KPM dan kader desa dalam finalisasi pemutakhiran data SDGs Desa dan scorecard stunting triwulanan."
        )
        rtl_items.append(
            "Melaporkan secara berkala progres pendampingan dan kendala krusial desa kepada Pendamping Desa (PD) di tingkat kecamatan."
        )

        # F. REKOMENDASI PLD
        rek_items.append(
            "Pemerintah Desa agar senantiasa mengedepankan prinsip transparansi publik, keterbukaan informasi anggaran, serta partisipasi aktif warga dalam setiap tahapan pengambilan keputusan di desa."
        )
        rek_items.append(
            "Lembaga kemasyarakatan desa dan kader pemberdayaan diharapkan terus merawat keterpaduan koordinasi guna memastikan program pembangunan terlaksana tepat sasaran dan berkesinambungan."
        )

    return {
        "tujuan": "\n".join([f"➤ {item}" for item in tujuan_items]),
        "hasil": "\n".join([f"➤ {item}" for item in hasil_items]),
        "rtl": "\n".join([f"➤ {item}" for item in rtl_items]),
        "rekomendasi": "\n".join([f"➤ {item}" for item in rek_items])
    }

# ----------------- FUNGSI BORDER HALAMAN (PERSIS CONTOH SEPTEMBER) -----------------
def draw_page_decorations(canvas, doc):
    canvas.saveState()
    # 1. Garis Kotak Bingkai Halaman Luar (Page Border Frame)
    margin = 0.85 * cm
    canvas.setStrokeColor(colors.black)
    canvas.setLineWidth(1.2)
    canvas.rect(margin, margin, doc.pagesize[0] - 2 * margin, doc.pagesize[1] - 2 * margin)
    
    # 2. Garis bingkai dalam tipis (Double Border khas berkas dinas)
    inner_margin = margin + 2.5
    canvas.setLineWidth(0.5)
    canvas.rect(inner_margin, inner_margin, doc.pagesize[0] - 2 * inner_margin, doc.pagesize[1] - 2 * inner_margin)
    canvas.restoreState()

# ----------------- GENERATOR PDF RESMI -----------------
def generate_pdf_report(info, entries, custom_text, tgl_cetak, jenjang_pilihan, ttd_bytes):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.6 * cm,
        rightMargin=1.6 * cm,
        topMargin=1.6 * cm,
        bottomMargin=1.6 * cm
    )

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle('DocTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=15, alignment=TA_CENTER)
    style_heading = ParagraphStyle('SectionHeading', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=14, spaceBefore=8, spaceAfter=4)
    style_bullet = ParagraphStyle('BulletText', parent=styles['Normal'], fontName='Helvetica', fontSize=9.5, leading=14, alignment=TA_JUSTIFY, leftIndent=15, firstLineIndent=-12, spaceAfter=5)
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
    elements.append(Spacer(1, 8))

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
    t_id = Table(id_data, colWidths=[3.2 * cm, 0.4 * cm, 14.0 * cm])
    t_id.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1.5),
        ('TOPPADDING', (0,0), (-1,-1), 1.5),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(t_id)
    elements.append(Spacer(1, 6))

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

    t_kunlap = Table(t_data, colWidths=[2.5 * cm, 3.5 * cm, 5.5 * cm, 6.1 * cm], repeatRows=2)
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
    elements.append(Spacer(1, 8))

    # C. Tujuan Kunjungan Lapangan
    elements.append(Paragraph("C. Tujuan Kunjungan Lapangan :", style_heading))
    for line in custom_text["tujuan"].split("\n"):
        c_line = line.strip()
        if c_line:
            elements.append(Paragraph(safe_text(c_line), style_bullet))
    elements.append(Spacer(1, 4))

    # D. Hasil Kunjungan Lapangan
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

    # Build dengan callback dekorasi bingkai border halaman
    doc.build(elements, onFirstPage=draw_page_decorations, onLaterPages=draw_page_decorations)
    buffer.seek(0)
    return buffer

# ----------------- LOGIKA ALUR WEB STREAMLIT -----------------
if uploaded_pdf is not None:
    pdf_bytes = uploaded_pdf.getvalue()
    with st.spinner("Membaca berkas DRP..."):
        info, entries, raw_kegiatan = parse_drp_pdf(pdf_bytes, jenjang_selected)

    st.success(f"✅ Berkas DRP Terbaca: **{info['nama']}** | **{len(entries)} Hari Kunjungan**")

    # Inisialisasi tematik otomatis instan
    if "tematik_draft" not in st.session_state or st.session_state.get("file_aktif") != uploaded_pdf.name:
        st.session_state["file_aktif"] = uploaded_pdf.name
        st.session_state["tematik_draft"] = generate_laporan_tematik(raw_kegiatan, jenjang_selected, info)

    draft = st.session_state["tematik_draft"]

    st.markdown("##### 📝 Langkah 3: Pratinjau & Penyesuaian Narasi Laporan")
    tab1, tab2 = st.tabs(["📋 Matriks Kunjungan (Tabel B)", "✍️ Narasi Resmi (Bagian C, D, E, F)"])

    with tab1:
        st.dataframe(entries, use_container_width=True)

    with tab2:
        txt_tujuan = st.text_area("C. Tujuan Kunjungan Lapangan", draft.get("tujuan", ""), height=180)
        txt_hasil = st.text_area("D. Hasil Kunjungan Lapangan", draft.get("hasil", ""), height=200)
        txt_rtl = st.text_area("E. Langkah Tindak Lanjut Penanganan Masalah", draft.get("rtl", ""), height=150)
        txt_rek = st.text_area("F. Rekomendasi", draft.get("rekomendasi", ""), height=140)

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
