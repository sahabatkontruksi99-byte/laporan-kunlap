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
st.caption("Unggah file PDF DRP bulanan. Sistem akan mengekstrak narasi riil dari hasil lapangan tiap desa.")

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

    # Pisahkan blok kunjungan lapangan
    blocks = re.split(r"Deskripsi kegiatan:\s*\(Kunjungan Lapangan\)", full_text)
    kunlap_entries = []
    
    hasil_per_desa = {}
    topik_fokus = set()

    for b in blocks[1:]:
        loc_match = re.search(r"Lokasi:\s*([^\n\r]+)", b)
        date_match = re.search(r"Hari/Tanggal:\s*[A-Za-z]+,\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4})", b)
        
        desa = "Desa Dampingan"
        if loc_match:
            parts = [p.strip() for p in loc_match.group(1).split("/") if p.strip()]
            if parts:
                desa = parts[-1].title()
                
        tgl_str = ""
        if date_match:
            tgl_str = date_match.group(1)
        else:
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

        # Ambil kalimat Output/Hasil nyata dari teks PDF
        outputs = re.findall(r"Output/Hasil:\s*([^\n\r]+(?:\n[^\n\r]+)*?)(?=(?:Pukul|\Z))", b)
        if outputs:
            clean_output = " ".join([o.replace("\n", " ").strip() for o in outputs])
            if desa not in hasil_per_desa:
                hasil_per_desa[desa] = clean_output
            else:
                hasil_per_desa[desa] += " " + clean_output

        b_low = b.lower()
        if "rkp" in b_low or "rpjm" in b_low:
            topik_fokus.add("rkpdes")
        if "monev" in b_low or "apbdes" in b_low:
            topik_fokus.add("monev")
        if "stunting" in b_low or "ehdw" in b_low:
            topik_fokus.add("stunting")

    # Susun Narasi Riil
    narasi = build_real_narrative(info, kunlap_entries, hasil_per_desa, topik_fokus)
    return info, kunlap_entries, narasi

def build_real_narrative(info, kunlap_entries, hasil_per_desa, topik_fokus):
    kec = info["kecamatan"].title()
    total_hari = len(kunlap_entries)
    
    # 1. TUJUAN
    tujuan_list = [
        f"Kegiatan pendampingan dan monitoring lapangan selama {total_hari} hari kerja di wilayah Kecamatan {kec} dilaksanakan dalam rangka mendukung tata kelola pemerintahan desa yang akuntabel dan transparan."
    ]
    if "rkpdes" in topik_fokus:
        tujuan_list.append("Pendampingan difokuskan pada fasilitasi penyusunan Rencana Kerja Pemerintah Desa (RKPDes) melalui pencermatan pagu indikatif, penelaahan dokumen RPJM Desa, serta penyusunan skala prioritas kegiatan desa.")
    if "monev" in topik_fokus:
        tujuan_list.append("Selain itu, kegiatan bertujuan melaksanakan Monitoring dan Evaluasi (Monev) APBDes guna memastikan kesesuaian antara realisasi serapan anggaran, volume fisik kegiatan (opname), serta kelengkapan SPJ.")
    if "stunting" in topik_fokus:
        tujuan_list.append("Pendampingan juga mencakup penguatan pencegahan stunting melalui evaluasi data KPM dan aplikasi eHDW.")
    tujuan = " ".join(tujuan_list)

    # 2. HASIL KUNJUNGAN (Mengambil intisari riil per desa)
    hasil_paragraphs = []
    for desa, desc in list(hasil_per_desa.items())[:6]:  # Ambil sampel desa representatif dari PDF
        # Ambil maksimal 2 kalimat awal dari output riil agar padat
        sentences = [s.strip() for s in desc.split(".") if len(s.strip()) > 15]
        ringkasan = ". ".join(sentences[:2]) + "." if sentences else desc
        hasil_paragraphs.append(f"Di Desa {desa}: {ringkasan}")
    
    hasil = "\n\n".join(hasil_paragraphs) if hasil_paragraphs else "Pelaksanaan kegiatan lapangan berjalan tertib sesuai agenda kerja."

    # 3. TINDAK LANJUT
    rtl = (
        "Sebagai tindak lanjut hasil kunjungan lapangan, Tim Penyusun RKPDes di masing-masing desa diarahkan untuk menuntaskan "
        "draf dokumen perencanaan berdasarkan pagu indikatif dan prioritas kebutuhan warga. Terhadap hasil evaluasi serapan anggaran "
        "dan monev fisik, pemerintah desa bersama TPK didorong untuk segera melengkapi kekurangan bukti administrasi SPJ perpajakan "
        "serta merapikan prasasti proyek sebagai kesiapan pencairan anggaran tahap selanjutnya."
    )

    # 4. REKOMENDASI
    rekomendasi = (
        "Pemerintah desa agar terus meningkatkan kualitas perencanaan pembangunan desa berbasis data riil dan musyawarah partisipatif.\n"
        "Tim Penyusun RKPDes perlu memastikan seluruh usulan kegiatan telah melalui proses verifikasi dan pencermatan RPJM Desa secara cermat.\n"
        "Pemerintah desa dan TPK agar mempercepat penyelesaian administrasi SPJ belanja serta realisasi fisik yang belum tuntas 100%.\n"
        "Kelengkapan dokumen administrasi keuangan desa harus terus ditertibkan guna kelancaran evaluasi dan pengajuan tahap berikutnya.\n"
        "Meningkatkan koordinasi rutin antara pemerintah desa, kecamatan, dan Tenaga Pendamping Profesional demi terwujudnya tata kelola desa yang baik."
    )

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
    with st.spinner("Membaca rincian Output dan Kegiatan tiap desa dari PDF..."):
        info, entries, auto_narrative = parse_drp_pdf(uploaded_file)

    st.success(f"Laporan diproses untuk: **{info['nama']}** | Terdeteksi **{len(entries)} Hari Kunjungan Lapangan**")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📋 Matriks Kunjungan Terdeteksi")
        st.dataframe(entries, use_container_width=True)

    with col2:
        st.subheader("📝 Narasi Riil Hasil Ekstraksi PDF")
        txt_tujuan = st.text_area("Tujuan Kunjungan Lapangan", auto_narrative["tujuan"], height=130)
        txt_hasil = st.text_area("Hasil Kunjungan Lapangan (Otomatis per Desa)", auto_narrative["hasil"], height=200)
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
