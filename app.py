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

st.set_page_config(page_title="Generator Laporan KUNLAP", page_icon="📄", layout="wide")

st.title("📄 Generator Laporan Kunjungan Lapangan (KUNLAP)")
st.caption("Unggah PDF DRP bulanan, tentukan jenjang, tanggal cetak, dan tanda tangan digital.")

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

def parse_drp_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    full_text = ""
    for page in reader.pages:
        txt = page.extract_text()
        if txt:
            full_text += txt + "\n"
            
    # Ekstraksi Identitas
    nik_m = re.search(r"N\s*[I|1]\s*K\s*:\s*([0-9]{16})", full_text)
    nama_m = re.search(r"Nama\s*:\s*([A-Z\s]+?)(?=(?:\n|N\s*[I|1]\s*K|Posisi))", full_text)
    kec_m = re.search(r"Kecamatan\s*:\s*([A-Za-z\s]+?)(?=(?:\n|Desa))", full_text)
    kab_m = re.search(r"Kabupaten/Kota\s*:\s*([A-Za-z\s]+?)(?=(?:\n|Kecamatan))", full_text)
    prov_m = re.search(r"Provinsi\s*:\s*([A-Za-z\s]+?)(?=(?:\n|Kabupaten))", full_text)
    pos_m = re.search(r"Posisi\s*:\s*([A-Za-z0-9]+)", full_text)
    
    per_m = re.search(r"Periode:\s*([A-Za-z]+)\s*(\d{4})", full_text)
    if per_m:
        bln_txt = per_m.group(1).title()
        thn_txt = per_m.group(2)
    else:
        bln_txt = "Juli"
        thn_txt = "2026"

    info = {
        "nik": nik_m.group(1).strip() if nik_m else "3524193107940002",
        "nama": clean_word(nama_m.group(1)) if nama_m else "MOHAMMAD AFIFUDDIN",
        "kecamatan": clean_word(kec_m.group(1)) if kec_m else "BALEN",
        "kabupaten": clean_word(kab_m.group(1)) if kab_m else "BOJONEGORO",
        "provinsi": clean_word(prov_m.group(1)) if prov_m else "JAWA TIMUR",
        "posisi_raw": clean_word(pos_m.group(1)) if pos_m else "PD",
        "bulan_str": bln_txt,
        "tahun_str": thn_txt,
        "periode": f"{bln_txt} Tahun {thn_txt}"
    }

    # Parsing Kunjungan Lapangan
    blocks = re.split(r"Deskripsi kegiatan:\s*\(Kunjungan Lapangan\)", full_text)
    kunlap_entries = []
    hasil_per_desa = {}

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

        # Ambil Output/Hasil Riil
        outputs = re.findall(r"Output/Hasil:\s*(.+?)(?=(?:Pukul|\Z))", b, flags=re.DOTALL)
        if outputs:
            clean_output = " ".join([re.sub(r"\s+", " ", o).strip() for o in outputs])
            clean_output = re.sub(r"\d{1,2}[\.:]\d{2}\s*WIB.*$", "", clean_output).strip()
            if desa not in hasil_per_desa and clean_output:
                hasil_per_desa[desa] = clean_output

    kec = info["kecamatan"].title()
    tujuan = (
        "Kegiatan pendampingan dan monitoring dilaksanakan dalam rangka mendukung penyelenggaraan pemerintahan "
        "desa yang efektif, akuntabel, dan sesuai dengan ketentuan peraturan perundang-undangan. Pendampingan difokuskan "
        "pada fasilitasi penyusunan Rencana Kerja Pemerintah Desa (RKPDes) Tahun Anggaran 2027 melalui pencermatan pagu indikatif, "
        "penelaahan dokumen RPJM Desa, penyusunan skala prioritas pembangunan, serta penguatan kapasitas Tim Penyusun RKPDes "
        "agar proses perencanaan desa berjalan partisipatif, terarah, dan sesuai kebutuhan masyarakat.\n\n"
        f"Selain itu, kegiatan juga bertujuan untuk melaksanakan Monitoring dan Evaluasi (Monev) APBDes Tahap I pada desa-desa "
        f"di Kecamatan {kec} guna memastikan kesesuaian antara realisasi anggaran, capaian fisik kegiatan, serta kelengkapan "
        "administrasi pertanggungjawaban. Kegiatan monitoring ini merupakan bagian dari upaya pembinaan dan pengawasan "
        "terhadap pengelolaan keuangan desa agar pelaksanaan pembangunan desa dapat berjalan secara transparan, akuntabel, dan tepat sasaran."
    )

    hasil_list = []
    for desa, desc in list(hasil_desa.items())[:3]:
        sentences = [s.strip() for s in desc.split(".") if len(s.strip()) > 15]
        ringkasan = ". ".join(sentences[:2]) + "." if sentences else desc
        hasil_list.append(f"Hasil pendampingan di Desa {desa} menunjukkan bahwa {ringkasan.lower() if ringkasan.startswith('Ter') else ringkasan}")
    
    hasil = "\n\n".join(hasil_list) if hasil_list else (
        "Hasil pendampingan dan monitoring membuktikan bahwa secara umum pelaksanaan kegiatan pembangunan fisik "
        "telah sesuai dengan dokumen perencanaan dan progres pekerjaan di lapangan. Administrasi pertanggungjawaban "
        "kegiatan juga telah tersedia dengan cukup baik dengan beberapa catatan penyempurnaan lampiran SPJ."
    )

    rtl = (
        "Sebagai tindak lanjut hasil pendampingan penyusunan RKPDes, Tim Penyusun RKPDes di masing-masing desa diarahkan "
        "untuk melanjutkan proses penyusunan dokumen perencanaan dengan mengacu pada hasil pencermatan RPJM Desa, pagu indikatif, "
        "serta prioritas kebutuhan masyarakat yang telah disepakati. Pendampingan lanjutan akan dilakukan untuk memastikan dokumen "
        "RKPDes tersusun sesuai tahapan dan ketentuan yang berlaku.\n\n"
        "Terhadap hasil evaluasi serapan anggaran, pemerintah desa didorong untuk segera menindaklanjuti berbagai kendala teknis "
        "yang telah teridentifikasi sehingga pelaksanaan kegiatan pembangunan dan pemberdayaan masyarakat dapat berjalan lebih optimal.\n\n"
        "Berdasarkan hasil monitoring APBDes Tahap I, pemerintah desa diminta untuk segera melengkapi kekurangan dokumen administrasi "
        "dan pertanggungjawaban kegiatan, khususnya terkait lampiran SPJ dan dokumen pendukung lainnya."
    )

    rekomendasi = (
        "Pemerintah desa agar terus meningkatkan kualitas perencanaan pembangunan melalui penyusunan RKPDes yang berbasis data, kebutuhan masyarakat, serta selaras dengan RPJM Desa dan arah kebijakan pembangunan nasional maupun daerah.\n"
        "Tim Penyusun RKPDes perlu memastikan bahwa seluruh usulan kegiatan yang dimasukkan dalam dokumen perencanaan telah melalui proses verifikasi, pencermatan, dan penetapan skala prioritas secara objektif dan partisipatif.\n"
        "Pemerintah desa agar mempercepat realisasi kegiatan yang masih belum optimal sehingga target penyerapan anggaran dapat tercapai sesuai jadwal yang telah ditetapkan.\n"
        "Kelengkapan administrasi dan pertanggungjawaban keuangan desa perlu menjadi perhatian utama, mengingat dokumen tersebut merupakan syarat penting dalam proses pengawasan, audit, maupun pengajuan pencairan anggaran tahap berikutnya.\n"
        "Hasil monitoring dan evaluasi hendaknya dijadikan bahan pembelajaran dan perbaikan berkelanjutan guna meningkatkan efektivitas pelaksanaan pembangunan desa, kualitas pelayanan kepada masyarakat, serta akuntabilitas pengelolaan keuangan desa.\n"
        "Pendampingan dan koordinasi antara pemerintah desa, kecamatan, serta tenaga pendamping profesional perlu terus ditingkatkan agar pelaksanaan pembangunan dan pengelolaan pemerintahan desa berjalan sesuai prinsip tata kelola yang baik (good governance)."
    )

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
    # Lebar kertas A4 = 21 cm. Margin 2.0 cm kiri-kanan -> lebar efektif konten = 17.0 cm
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
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        alignment=TA_CENTER
    )
    
    style_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        spaceBefore=8,
        spaceAfter=4
    )
    
    style_body = ParagraphStyle(
        'BodyJustify',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        alignment=TA_JUSTIFY,
        spaceAfter=6
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

    style_cell = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12
    )

    style_cell_center = ParagraphStyle(
        'TableCellCenter',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        alignment=TA_CENTER
    )

    style_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        alignment=TA_CENTER
    )

    elements = []

    # Map Jabatan
    jenjang_map = {
        "PD": ("PD", "PENDAMPING DESA"),
        "PLD": ("PLD", "PENDAMPING LOKAL DESA"),
        "TAPM": ("TAPM", "TENAGA AHLI PEMBERDAYAAN MASYARAKAT")
    }
    posisi_val, jabatan_val = jenjang_map.get(jenjang_pilihan, ("PD", "PENDAMPING DESA"))

    # Judul Header
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
    # Total lebar = 3.2 + 0.3 + 13.5 = 17.0 cm (pas dengan margin)
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
        "",
        "",
        ""
    ])

    # Total lebar kolom = 2.5 + 3.5 + 5.0 + 6.0 = 17.0 cm
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
    for p in custom_text["rtl"].split("\n\n"):
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

# ----------------- ANTARMUKA STREAMLIT -----------------
col_up1, col_up2 = st.columns([1, 1])
with col_up1:
    uploaded_pdf = st.file_uploader("1. Unggah PDF DRP Bulanan", type=["pdf"])
with col_up2:
    uploaded_ttd = st.file_uploader("2. Unggah Gambar Tanda Tangan (Opsional: PNG/JPG)", type=["png", "jpg", "jpeg"])

if uploaded_pdf is not None:
    with st.spinner("Mengekstrak dan merapikan data dari PDF DRP..."):
        info, entries, auto_narrative = parse_drp_pdf(uploaded_pdf)

    st.success(f"Berhasil membaca data: **{info['nama']}** | Total Kunjungan: **{len(entries)} Hari**")

    st.markdown("### ⚙️ Pengaturan Cetak Dokumen")
    c_set1, c_set2 = st.columns(2)
    with c_set1:
        jenjang_selected = st.selectbox(
            "Pilih Jenjang Jabatan:",
            ["PD", "PLD", "TAPM"],
            index=0 if info["posisi_raw"].upper() == "PD" else (1 if info["posisi_raw"].upper() == "PLD" else 2)
        )
    with c_set2:
        tahun_val = int(info["tahun_str"]) if info["tahun_str"].isdigit() else 2026
        bln_dict_rev = {
            "januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6,
            "juli": 7, "agustus": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12
        }
        bulan_num = bln_dict_rev.get(info["bulan_str"].lower(), 7)
        _, last_day = calendar.monthrange(tahun_val, bulan_num)
        default_date = datetime.date(tahun_val, bulan_num, last_day)
        
        tgl_cetak = st.date_input("Pilih Tanggal Cetak Laporan:", default_date)

    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("📋 Matriks Kunjungan")
        st.dataframe(entries, use_container_width=True)

    with col2:
        st.subheader("📝 Narasi Laporan (Bisa Disesuaikan)")
        txt_tujuan = st.text_area("C. Tujuan Kunjungan Lapangan", auto_narrative["tujuan"], height=130)
        txt_hasil = st.text_area("D. Hasil Kunjungan Lapangan", auto_narrative["hasil"], height=160)
        txt_rtl = st.text_area("E. Langkah Tindak Lanjut", auto_narrative["rtl"], height=110)
        txt_rek = st.text_area("F. Rekomendasi (Pisahkan Baris)", auto_narrative["rekomendasi"], height=140)

    custom_text = {
        "tujuan": txt_tujuan,
        "hasil": txt_hasil,
        "rtl": txt_rtl,
        "rekomendasi": txt_rek
    }

    ttd_bytes = uploaded_ttd.read() if uploaded_ttd is not None else None

    # Tombol Eksekusi Pembuatan PDF
    st.markdown("---")
    if st.button("🚀 Proses & Buat PDF Laporan", type="primary"):
        with st.spinner("Menyusun PDF resmi..."):
            try:
                pdf_output = generate_pdf_report(
                    info, entries, custom_text, tgl_cetak, jenjang_selected, ttd_bytes
                )
                st.download_button(
                    label="📥 Klik Di Sini untuk Mengunduh PDF KUNLAP",
                    data=pdf_output,
                    file_name=f"KUNLAP_{jenjang_selected}_{info['nama']}_{info['bulan_str']}_{info['tahun_str']}.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Gagal menyusun PDF: {e}")
