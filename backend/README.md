# WasteFlow AI Intelligence Backend

Implementasi resmi **AI Intelligence Layer** untuk WasteFlow berbasis spesifikasi `WasteFlow_AI_Intelligence_Specification_v1.pdf`.

Modul ini berfungsi sebagai lapisan interpretasi operasional pasca-optimasi solver linier (PuLP), yang didukung oleh Google Gemini API (menggunakan SDK resmi `google-genai`), validasi skema Pydantic v2, dan **6-Layer Guardrail Validation**.

---

## 🏗️ Struktur Arsitektur

```text
backend/
├── app/
│   ├── ai/
│   │   ├── errors.py              # Hirarki error terstruktur (kode error + HTTP status + retryable)
│   │   ├── gemini_client.py       # Wrapper Google Gen AI SDK + MockAIClient eksplisit
│   │   ├── prompts.py             # System & task prompt (v1) dengan pemisahan instruksi & data
│   │   ├── input_schema.py        # Kontrak Pydantic payload input (strict, extra="forbid")
│   │   ├── output_schema.py       # Kontrak Pydantic response terstruktur AI
│   │   ├── payload_builder.py     # Builder allow-list payload & evidence catalog
│   │   ├── evidence_validator.py  # Validator bukti faktual (evidence keys)
│   │   └── validator.py           # 6-Layer Guardrails (Eligibility, Payload, Schema, Evidence, Numeric, Policy)
│   ├── integration/
│   │   └── run_provider.py        # Seam integrasi (RunSnapshotProvider + auth hook) ke sistem utama
│   ├── core/
│   │   ├── config.py              # Konfigurasi aplikasi & environment
│   │   └── database.py            # SQLite/PostgreSQL engine & session
│   ├── models/
│   │   ├── optimization_run.py    # Tabel snapshot run solver (mode standalone/dev)
│   │   └── ai_analysis.py         # Tabel histori & audit analisis AI (Spec 7.3)
│   ├── services/
│   │   └── ai_service.py          # Alur orkestrasi, retry korektif, & persistensi AI
│   ├── api/v1/
│   │   ├── ai.py                  # Endpoint POST analysis, GET history, & GET detail
│   │   └── runs.py                # Endpoint dev untuk seed optimization run
│   └── main.py                    # Entrypoint aplikasi FastAPI
├── docs/
│   └── INTEGRATION.md             # Panduan lengkap integrasi ke backend PuLP & frontend Next.js
├── tests/                         # 51 unit/integration tests + 15-case evaluation runner
├── requirements.txt               # Dependensi Python
├── .env.example                   # Contoh konfigurasi environment
└── .gitignore                     # Proteksi agar .env dan *.db tidak ter-commit
```

---

## 🛡️ 6 Lapisan Guardrail (*Validation Layers*)

1. **Request Eligibility:** Menolak run yang berstatus `infeasible`, `unbounded`, `not solved`, `undefined`, atau `error` **sebelum** memanggil Gemini, serta menerapkan cooldown anti-duplikat (`DUPLICATE_REQUEST`).
2. **Payload Validation:** Memastikan seluruh bagian wajib tersedia (tanpa mengarang default), angka finite, jumlah bobot $= 1.0$, tidak ada `period_mismatch`, ukuran payload terkendali, dan alokasi konsisten dengan daftar rute.
3. **Schema Validation:** Parsing wajib ke struktur Pydantic `AIAnalysisOutput` (0–5 item per bagian, panjang teks dibatasi, setiap insight/tradeoff/recommendation wajib punya minimal 1 evidence key).
4. **Evidence Validation:** Seluruh insight, tradeoff, dan rekomendasi wajib mencantumkan bukti yang terdaftar dalam `evidence_catalog`.
5. **Numeric Consistency:** Memastikan setiap angka yang disebut AI dalam teks (format Indonesia `1.200,5` maupun Inggris `1,200.5` serta persentase) dapat dipetakan ke angka payload backend. Angka turunan/selisih yang dihitung sendiri oleh AI ditolak.
6. **Policy Validation & Mandatory Limitations:**
   - `solver_status` pada output wajib sama persis dengan status solver backend.
   - Menolak klaim reduksi sampah skala kota tanpa evaluasi eksternal.
   - Menolak klaim "pasti turun/meningkat" atau "dijamin" tanpa pembanding yang valid.
   - Menolak penyebutan hasil "optimal" bila status solver bukan `optimal` (mis. `feasible`).
   - Menolak rekomendasi penambahan kapasitas tanpa bukti utilisasi tinggi ($\ge 85\%$) dan pertimbangan biaya.
   - Menolak perlakuan residu proses sebagai material yang belum dialokasikan.
   - Menolak perbandingan baseline saat `baseline_unavailable`.
   - Menambahkan kalimat keterbatasan wajib secara deterministik bila flag `synthetic_data`, `yield_assumption`, `missing_route_profile`, atau `baseline_unavailable` aktif.

---

## 🚀 Cara Menjalankan

### 1. Atur `GEMINI_API_KEY` di file `.env`
Salin `backend/.env.example` menjadi `backend/.env` dan isi API key Anda:
```env
GEMINI_API_KEY=AIzaSy...
GEMINI_MODEL=gemini-3.8-flash
AI_ALLOW_MOCK=false
```
> Untuk pengembangan/pengujian lokal **tanpa** kuota Gemini, kosongkan `GEMINI_API_KEY` dan set `AI_ALLOW_MOCK=true`. Jika keduanya tidak aktif, endpoint mengembalikan HTTP `503 AI_NOT_CONFIGURED` (tidak pernah diam-diam memalsukan output Gemini).

### 2. Jalankan server FastAPI
```powershell
cd backend
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```
Buka dokumentasi Swagger UI di: `http://localhost:8000/docs`

---

## 🧪 Menjalankan Pengujian & Evaluasi

```powershell
cd backend
# 1. Jalankan 51 unit & integration tests
.venv\Scripts\python -m pytest tests -v

# 2. Jalankan 15 skenario evaluasi (pipeline check dengan mock provider)
.venv\Scripts\python -m tests.run_evaluation

# 3. Jalankan evaluasi live ke Gemini (memakai kuota API)
.venv\Scripts\python -m tests.run_evaluation --live --delay 5
```

---

## 🔗 Integrasi ke Sistem Utama WasteFlow

Lihat panduan langkah demi langkah (adapter PuLP $\rightarrow$ snapshot, registrasi router FastAPI, migrasi Alembic `ai_analyses`, serta contoh komponen Next.js) di [`docs/INTEGRATION.md`](docs/INTEGRATION.md).
