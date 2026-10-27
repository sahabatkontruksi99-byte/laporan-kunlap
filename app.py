import streamlit as st
from pypdf import PdfReader
import re
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
import io

st.set_page_config(page_title="Generator Laporan KUNLAP", page_icon="📄", layout="wide")

st.title("📄 Generator Laporan Kunjungan Lapangan (KUNLAP)")
st.caption("Unggah file PDF Daily Report (DRP) bulanan untuk mengunduh laporan KUNLAP (.docx) otomatis dengan narasi yang menyesuaikan.")

uploaded_file = st.file_uploader("Pilih Berkas PDF DRP", type=["pdf"])

def parse_drp_pdf(pdf_file):
    reader = PdfReader(pdf_file)
    full_text = ""
    for page in reader.pages:
        txt = page.extract_text()
        if txt:
            full_text += txt + "\n"
            
    # Ekstraksi Identitas
    nik_m = re.search(r"N[I|1]K\s*:\s*([0-9]+)", full_text)
    nama_m = re.search(r"Nama\s*:\s*([A-Z\s]+)", full_text)
    kec_m = re.search(r"Kecamatan\s*:\s*([A-Za-z0-9\s]+)", full_text)
    kab_m = re.search(r"Kabupaten/Kota\s*:\s*([A-Za-z0-9\s]+)", full_text)
    prov_m = re.search(r"Provinsi\s*:\s*([A-Za-z0-9\s]+)", full_text)
    pos_m = re.search(r"Posisi\s*:\s*([A-Za-z0-9\s]+)", full_text)
    per_m = re.search(r"Periode:\s*([A-Za-z0-9\s\(\)\-\/]+)", full_text)
    
    info = {
        "nik": nik_m.group(1).strip() if nik_m else "3524193107940002",
        "nama": nama_m.group(1).strip() if nama_m else "MOHAMMAD AFIFUDDIN",
        "kecamatan": kec_m.group(1).strip() if kec_m else "BALEN",
        "kabupaten": kab_m.group(1).strip() if kab_m else "BOJONEGORO",
        "provinsi": prov_m.group(1).strip() if prov_m else "JAWA TIMUR",
        "posisi": pos_m.group(1).strip() if pos_m else "PD",
        "periode": per_m.group(1).strip() if per_m else "Juli 2026"
    }

    # Pisahkan blok laporan kunjungan lapangan
    blocks = re.split(r"Deskripsi kegiatan:\s*\(Kunjungan Lapangan\)", full_text)
    kunlap_entries = []
    
    # Kategori topik untuk narasi dinamis
    topik_desa = {
        "rkpdes": set(),
        "monev": set(),
        "stunting": set(),
        "bumdes": set()
    }
    
    for b in blocks[1:]:
        # Ambil lokasi
        loc_match = re.search(r"Lokasi:\s*([^\n\r]+)", b)
        date_match = re.search(r"Hari/Tanggal:\s*[A-Za-z]+,\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})", b)
        
        desa = "Desa Dampingan"
        if loc_match:
            parts = [p.strip() for p in loc_match.group(1).split("/") if p.strip()]
            if parts:
                desa = parts[-1].title()
                
        # Format tanggal
        tgl_str = ""
        if date_match:
            tgl_str = date_match.group(1)
        else:
            # Pola alternatif DD/MM/YY
            alt_date = re.search(r"(\d{2}/\d{2}/\d{2})", b)
            if alt_date:
                dp = alt_date.group(1).split("/")
                tgl_str = f"{int(dp[0])}-{dp[1]}-20{dp[2]}"
            else:
                tgl_str = "-"

        kunlap_entries.append({
            "tanggal": tgl_str,
            "kecamatan": info["kecamatan"].title(),
            "desa": desa
        })
        
        # Deteksi isi narasi berdasarkan kata kunci di blok aktivitas
        b_lower = b.lower()
        if "rkp" in b_lower or "rpjm" in b_lower:
            topik_desa["rkpdes"].add(desa)
        if "monev" in b_lower or "apbdes" in b_lower or "opname" in b_lower:
            topik_desa["monev"].add(desa)
        if "stunting" in b_lower or "ehdw" in b_lower or "kpm" in b_lower:
            topik_desa["stunting"].add(desa)
        if "bumdes" in b_lower or "bum desa" in b_lower:
            topik_desa["bumdes"].add(desa)

    # Susun Narasi Dinamis
    narasi = generate_dynamic_narrative(info, topik_desa)
    
    return info, kunlap_entries, narasi

def generate_dynamic_narrative(info, topik):
    kec = info["kecamatan"].title()
    
    # 1. Narasi Tujuan
    tujuan_parts = [
        f"Kegiatan pendampingan dan monitoring dilaksanakan dalam rangka mendukung tata kelola pemerintahan desa yang efektif, transparan, dan akuntabel di wilayah Kecamatan {kec}."
    ]
    if topik["rkpdes"]:
        tujuan_parts.append(
            f"Fokus pendampingan diarahkan pada fasilitasi penyusunan Rencana Kerja Pemerintah Desa (RKPDes) melalui pencermatan pagu indikatif, penelaahan dokumen RPJM Desa, serta penyusunan skala prioritas pembangunan desa partisipatif."
        )
    if topik["monev"]:
        tujuan_parts.append(
            f"Selain itu, kegiatan bertujuan untuk melaksanakan Monitoring dan Evaluasi (Monev) realisasi APBDes guna memastikan keselarasan antara serapan anggaran, kualitas capaian fisik lapangan (opname), serta ketertiban administrasi pertanggungjawaban (SPJ)."
        )
    if topik["stunting"]:
        tujuan_parts.append("Pendampingan juga difokuskan pada penguatan konvergensi pencegahan stunting melalui optimalisasi peran Kader Pembangunan Manusia (KPM) dan pelaporan aplikasi eHDW.")
    tujuan = " ".join(tujuan_parts)

    # 2. Narasi Hasil Kunjungan
    hasil_parts = []
    if topik["rkpdes"]:
        desa_rkp = ", Desa ".join(list(topik["rkpdes"])[:4])
        hasil_parts.append(
            f"Hasil pendampingan perencanaan di Desa {desa_rkp} dan sekitarnya menunjukkan bahwa Tim Penyusun RKPDes telah memahami tahapan kerja, melakukan sinkronisasi dengan dokumen RPJM Desa, serta menyusun draf awal daftar usulan prioritas kegiatan tahun anggaran mendatang."
        )
    if topik["monev"]:
        desa_monev = ", Desa ".join(list(topik["monev"])[:5])
        hasil_parts.append(
            f"Pelaksanaan Monitoring dan Evaluasi APBDes di desa-desa dampingan (antara lain Desa {desa_monev}) membuktikan bahwa pekerjaan infrastruktur fisik secara umum telah rampung sesuai volume dan gambar rencana. Administrasi pembukuan kas dan kelengkapan SPJ terkelola dengan tertib, meski terdapat catatan perbaikan minor terkait kelengkapan bukti transaksi belanja dan pemeliharaan papan transparansi kegiatan."
        )
    if topik["stunting"]:
        desa_stunting = ", Desa ".join(topik["stunting"])
        hasil_parts.append(
            f"Terkait bidang kesehatan dan penanganan stunting di Desa {desa_stunting}, telah dilakukan pemutakhiran data sekunder layanan sasaran ibu hamil dan balita pada aplikasi eHDW serta penyiapan scorecard sebagai bahan musyawarah Rembug Stunting desa."
        )
    if topik["bumdes"]:
        hasil_parts.append(
            "Di sektor ekonomi, telah dilakukan identifikasi awal kelengkapan indikator legalitas dan tata kelola usaha BUMDes sebagai tindak lanjut koordinasi pemeringkatan kelembagaan desa."
        )
    hasil = "\n\n".join(hasil_parts)

    # 3. Langkah Tindak Lanjut
    rtl_parts = []
    if topik["rkpdes"]:
        rtl_parts.append("Tim Penyusun RKPDes diinstruksikan untuk melanjutkan proses penyusunan dokumen rancangan RKPDes berpedoman pada pagu indikatif dan musyawarah penggalian aspirasi warga.")
    if topik["monev"]:
        rtl_parts.append("Pemerintah desa bersama Tim Pelaksana Kegiatan (TPK) diminta segera menindaklanjuti catatan evaluasi monev dengan melengkapi dokumen lampiran SPJ, administrasi perpajakan, serta memasang prasasti proyek fisik yang telah selesai 100%.")
    if topik["stunting"]:
        rtl_parts.append("Mendorong KPM desa untuk merampungkan rekapitulasi data layanan 1.000 HPK guna mematangkan agenda Rembug Stunting tingkat desa.")
    rtl = " ".join(rtl_parts)

    # 4. Rekomendasi
    rek_list = [
        "Pemerintah desa agar terus memperkuat kualitas perencanaan pembangunan melalui penyusunan RKPDes yang partisipatif, berbasis data, dan selaras dengan arah prioritas penggunaan dana desa.",
        "Tim Penyusun RKPDes perlu memastikan seluruh usulan kegiatan telah melalui proses pencermatan dan penetapan skala prioritas yang objektif.",
        "Pemerintah desa agar mempercepat penyelesaian Laporan Realisasi Semester Pertama dan pelunasan kewajiban pajak belanja sebagai syarat penyaluran anggaran tahap berikutnya.",
        "Tim Pelaksana Kegiatan (TPK) wajib menjaga kerapian dokumentasi progres pekerjaan dan transparansi publik melalui papan informasi proyek di lokasi kegiatan.",
        "Koordinasi terpadu antara pemerintah desa, jajaran kecamatan, serta jajaran Tenaga Pendamping Profesional perlu terus dioptimalkan secara berkala."
    ]
    rekomendasi = "\n".join(rek_list)

    return {
        "tujuan": tujuan,
        "hasil": hasil,
        "rtl": rtl,
        "rekomendasi": rekomendasi
    }

def create_docx(info, kunlap_entries, custom_text):
    doc = Document()
    for s in doc.sections:
        s.top_margin = Inches(1.0)
        s.bottom_margin = Inches(1.0)
        s.left_margin = Inches(1.0)
        s.right_margin = Inches(1.0)

    # Judul
    p_title = doc.add_paragraph()
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r1 = p_title.add_run("LAPORAN KUNJUNGAN LAPANGAN BULANAN\n")
    r1.bold = True
    r1.font.size = Pt(12)
    r2 = p_title.add_run("PENDAMPING DESA\n")
    r2.bold = True
    r2.font.size = Pt(12)
    r3 = p_title.add_run(f"Bulan {info['periode']}\n")
    r3.bold = True
    r3.font.size = Pt(12)

    # Identitas
    doc.add_paragraph("Identitas")
    t_id = doc.add_table(rows=7, cols=3)
    t_id.alignment = WD_TABLE_ALIGNMENT.CENTER
    id_data = [
        ("N I K", ":", info["nik"]),
        ("Nama Lengkap", ":", info["nama"]),
        ("Kecamatan", ":", info["kecamatan"]),
        ("Kabupaten/Kota", ":", info["kabupaten"]),
        ("Provinsi", ":", info["provinsi"]),
        ("Posisi", ":", info["posisi"]),
        ("Jabatan", ":", "PENDAMPING DESA")
    ]
    for r_idx, (k, col, val) in enumerate(id_data):
        row = t_id.rows[r_idx]
        row.cells[0].paragraphs[0].add_run(k)
        row.cells[1].paragraphs[0].add_run(col)
        row.cells[2].paragraphs[0].add_run(val)
        row.cells[0].width = Inches(1.8)
        row.cells[1].width = Inches(0.2)
        row.cells[2].width = Inches(4.5)

    doc.add_paragraph("\nWaktu Pelaksanaan Kunjungan Lapangan")

    # Tabel Kunjungan
    table = doc.add_table(rows=2 + len(kunlap_entries), cols=4)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    h_cells = table.rows[0].cells
    h_cells[0].text = "Hari ke"
    h_cells[1].text = "Waktu (Tgl/Bln/Thn)"
    h_cells[2].text = "Lokasi Kunjungan"
    h_cells[2].merge(h_cells[3])
    
    sub_cells = table.rows[1].cells
    sub_cells[0].text = "1"
    sub_cells[1].text = "2"
    sub_cells[2].text = "Kecamatan"
    sub_cells[3].text = "Desa"
    
    for idx, item in enumerate(kunlap_entries):
        r_cells = table.rows[2 + idx].cells
        r_cells[0].text = f"Hari ke {idx + 1}"
        r_cells[1].text = item["tanggal"]
        r_cells[2].text = item["kecamatan"]
        r_cells[3].text = item["desa"]

    for row in table.rows:
        for cell in row.cells:
            tcPr = cell._tc.get_or_add_tcPr()
            tcBorders = parse_xml(r'''
                <w:tcBorders {} >
                    <w:top w:val="single" w:sz="4" w:space="0" w:color="auto"/>
                    <w:left w:val="single" w:sz="4" w:space="0" w:color="auto"/>
                    <w:bottom w:val="single" w:sz="4" w:space="0" w:color="auto"/>
                    <w:right w:val="single" w:sz="4" w:space="0" w:color="auto"/>
                </w:tcBorders>
            '''.format(nsdecls('w')))
            tcPr.append(tcBorders)

    p_tot = doc.add_paragraph()
    p_tot.add_run(f"\nTotal Hari Kunjungan Lapangan Bulan {info['periode']} : {len(kunlap_entries)} Hari").bold = True

    # Bagian Narasi
    doc.add_paragraph("Tujuan Kunjungan Lapangan").runs[0].bold = True
    p_tujuan = doc.add_paragraph(custom_text["tujuan"])
    p_tujuan.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph("Hasil Kunjungan Lapangan").runs[0].bold = True
    for part in custom_text["hasil"].split("\n\n"):
        if part.strip():
            p_h = doc.add_paragraph(part.strip())
            p_h.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph("Langkah Tindak Lanjut Penanganan Masalah :").runs[0].bold = True
    p_rtl = doc.add_paragraph(custom_text["rtl"])
    p_rtl.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    doc.add_paragraph("Rekomendasi :").runs[0].bold = True
    for rek in custom_text["rekomendasi"].split("\n"):
        if rek.strip():
            p_rek = doc.add_paragraph(rek.strip(), style='List Bullet')
            p_rek.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    # Tanda Tangan
    doc.add_paragraph("\n")
    p_sign = doc.add_paragraph()
    p_sign.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p_sign.add_run(f"Bojonegoro, 31 {info['periode']}\nPenyusun Laporan,\n\n\n\n\n")
    r_nama = p_sign.add_run(f"{info['nama']}")
    r_nama.bold = True
    r_nama.underline = True

    bio = io.BytesIO()
    doc.save(bio)
    bio.seek(0)
    return bio

if uploaded_file is not None:
    with st.spinner("Mengekstraksi narasi dan tabel dari PDF DRP..."):
        info, entries, auto_narrative = parse_drp_pdf(uploaded_file)

    st.success(f"Laporan diproses untuk: **{info['nama']}** | Terdeteksi **{len(entries)} Hari Kunjungan Lapangan**")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📋 Matriks Kunjungan Terdeteksi")
        st.dataframe(entries, use_container_width=True)

    with col2:
        st.subheader("📝 Narasi Otomatis (Hasil Analisis PDF)")
        txt_tujuan = st.text_area("Tujuan Kunjungan Lapangan", auto_narrative["tujuan"], height=130)
        txt_hasil = st.text_area("Hasil Kunjungan Lapangan", auto_narrative["hasil"], height=180)
        txt_rtl = st.text_area("Langkah Tindak Lanjut", auto_narrative["rtl"], height=120)
        txt_rek = st.text_area("Rekomendasi", auto_narrative["rekomendasi"], height=140)

    custom_text = {
        "tujuan": txt_tujuan,
        "hasil": txt_hasil,
        "rtl": txt_rtl,
        "rekomendasi": txt_rek
    }

    docx_bytes = create_docx(info, entries, custom_text)

    st.markdown("---")
    st.download_button(
        label="📥 Unduh Dokumen KUNLAP (.docx)",
        data=docx_bytes,
        file_name=f"KUNLAP_{info['nama']}_{info['periode']}.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        type="primary"
    )
