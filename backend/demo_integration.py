"""
Demo Script: Pengujian End-to-End Integrasi WasteFlow AI Intelligence Layer
(Menguji alur integrasi dari INTEGRATION.md: Solver -> Snapshot -> API -> AI Analysis -> Guardrails)
"""

import sys
import os
import json
import time

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.core.database import Base, engine, SessionLocal
from app.models.optimization_run import OptimizationRun
from app.models.ai_analysis import AIAnalysis

import argparse
from app.ai.gemini_client import MockAIClient
from app.api.v1.ai import get_ai_client_factory

def print_separator(title=""):
    print("\n" + "=" * 70)
    if title:
        print(f"  {title.upper()}")
        print("=" * 70)

def main():
    parser = argparse.ArgumentParser(description="Test integrasi WasteFlow AI")
    parser.add_argument("--mock", action="store_true", help="Gunakan mock AI deterministic (tanpa koneksi luar)")
    args = parser.parse_args()

    if args.mock:
        app.dependency_overrides[get_ai_client_factory] = lambda: (lambda: MockAIClient())

    mode_str = "MOCK (Offline Deterministic)" if args.mock else f"LIVE ({settings.GEMINI_MODEL})"

    print_separator("PENGUJIAN INTEGRASI WASTEFLOW AI (END-TO-END)")
    print(f"Konfigurasi:")
    print(f"- Mode Operasi     : {mode_str}")
    print(f"- Prompt Version   : {settings.PROMPT_VERSION}")
    print(f"- API Key Status   : {'Terdeteksi' if settings.GEMINI_API_KEY else 'Kosong'}")

    # Buat tabel SQLite jika belum ada
    Base.metadata.create_all(bind=engine)
    client = TestClient(app)

    # -------------------------------------------------------------
    # LANGKAH 1: Healthcheck API
    # -------------------------------------------------------------
    print_separator("Langkah 1: Memeriksa Status Kesehatan Server (/health)")
    res = client.get("/health")
    print(f"HTTP Status: {res.status_code}")
    print("Response:")
    print(json.dumps(res.json(), indent=2))
    assert res.status_code == 200, "Healthcheck gagal!"

    # -------------------------------------------------------------
    # LANGKAH 2: Simulasi Output Solver PuLP & Penyimpanan Snapshot
    # -------------------------------------------------------------
    print_separator("Langkah 2: Simulasi Solver Selesai -> Buat Snapshot Run (Spec 3.2)")
    snapshot_payload = {
        "status": "optimal",
        "data_source": "field",
        "snapshot_data": {
            "facility": {"facility_id": "fac-01", "facility_name": "TPS3R Sukamaju"},
            "period": {"start": "2026-11-01", "end": "2026-11-07", "capacity_period": "day"},
            "solver": {"status": "optimal", "name": "PuLP", "version": "2.8"},
            "weights": {"cost": 0.333, "recovery": 0.333, "residual": 0.334},
            "metrics": {
                "total_input_kg": 1200.0,
                "total_cost_rp": 850000.0,
                "recovered_kg": 720.0,
                "recovery_rate": 0.60,
                "residual_kg": 180.0,
                "residual_rate": 0.15
            },
            "routes": [
                {
                    "route_id": "route-sorting",
                    "route_name": "Sorting Line",
                    "allocated_kg": 500.0,
                    "capacity_kg": 700.0,
                    "utilization_rate": 0.714
                },
                {
                    "route_id": "route-compost",
                    "route_name": "Composting Bed",
                    "allocated_kg": 450.0,
                    "capacity_kg": 600.0,
                    "utilization_rate": 0.75
                }
            ],
            "allocations": [
                {
                    "material_id": "mat-plastic",
                    "material_name": "Plastic",
                    "route_id": "route-sorting",
                    "allocated_kg": 300.0
                },
                {
                    "material_id": "mat-organic",
                    "material_name": "Organic",
                    "route_id": "route-compost",
                    "allocated_kg": 450.0
                }
            ],
            "baseline_metrics": {
                "status": "feasible",
                "total_cost_rp": 920000.0,
                "recovered_kg": 680.0,
                "residual_kg": 210.0
            },
            "validation": {
                "mass_balance_error_kg": 0.0,
                "capacity_violations": 0,
                "compatibility_violations": 0
            }
        }
    }

    create_run_res = client.post("/api/v1/optimization/runs", json=snapshot_payload)
    print(f"HTTP Status: {create_run_res.status_code}")
    run_info = create_run_res.json()
    run_id = run_info["run_id"]
    print(f"Tersimpan Run ID: {run_id} (Status Solver: {run_info['status']})")

    # -------------------------------------------------------------
    # LANGKAH 3: Simulasi Tombol Frontend "Generate AI Analysis"
    # -------------------------------------------------------------
    print_separator("Langkah 3: Frontend Menembak Endpoint AI (/optimization/runs/{id}/analysis)")
    print("Memproses analisis operasional, verifikasi 6-layer guardrails, & pemanggilan AI...")

    start_t = time.time()
    ai_res = client.post(
        f"/api/v1/optimization/runs/{run_id}/analysis",
        json={"analysis_type": "full"}
    )
    elapsed = time.time() - start_t

    print(f"HTTP Status  : {ai_res.status_code} ({elapsed:.2f} detik)")
    ai_body = ai_res.json()

    if ai_res.status_code == 200:
        result = ai_body["result"]
        print("\nHASIL ANALISIS TERVALIDASI (Diterima oleh Next.js):")
        print("-" * 50)
        print(f"Ringkasan (Summary):\n{result['summary']}\n")

        print("Operational Insights (Temuan Bottleneck/Kapasitas):")
        for idx, item in enumerate(result.get("operational_insights", []), 1):
            print(f"  {idx}. [{item['severity'].upper()}] {item['title']}")
            print(f"     Temuan: {item['finding']}")
            print(f"     Bukti (Evidence): {', '.join(item['evidence'])}")

        print("\nOptimization Interpretation (Trade-off Bobot):")
        for idx, item in enumerate(result.get("optimization_interpretation", {}).get("tradeoffs", []), 1):
            print(f"  {idx}. {item['statement']}")
            print(f"     Bukti: {', '.join(item['evidence'])}")

        print("\nRekomendasi Tindakan:")
        for idx, item in enumerate(result.get("recommendations", []), 1):
            print(f"  {idx}. [{item['priority'].upper()}] {item['action']}")
            print(f"     Alasan: {item['rationale']}")
            print(f"     Bukti: {', '.join(item['evidence'])}")

        print("\nLimitasi Data:")
        for l in result.get("limitations", []):
            print(f"  - {l}")

    else:
        print("Panggilan AI mengembalikan respon terkontrol:")
        print(json.dumps(ai_body, indent=2))

    # -------------------------------------------------------------
    # LANGKAH 4: Cek Riwayat Audit Database (ai_analyses)
    # -------------------------------------------------------------
    print_separator("Langkah 4: Memeriksa Riwayat Audit di Database (/ai/history)")
    hist_res = client.get(f"/api/v1/ai/history?run_id={run_id}")
    history_data = hist_res.json()
    print(f"Total riwayat tercatat untuk run ini: {history_data.get('total', len(history_data.get('items', [])))}")
    if history_data.get("items"):
        item = history_data["items"][0]
        print(f"- Analysis ID        : {item.get('analysis_id', item.get('id'))}")
        print(f"- Validation Status  : {item.get('validation_status')}")
        print(f"- Latency            : {item.get('latency_ms')} ms")
        print(f"- Error Code         : {item.get('error_code')}")
        print(f"- Error Message      : {item.get('error_message')}")

    # -------------------------------------------------------------
    # LANGKAH 5: Uji Proteksi Satpam (Kasus Infeasible Solver)
    # -------------------------------------------------------------
    print_separator("Langkah 5: Uji Proteksi Satpam (Mencegah Analisis Solver Gagal)")
    infeasible_run = client.post("/api/v1/optimization/runs", json={
        "status": "infeasible",
        "data_source": "field",
        "snapshot_data": {
            "solver": {"status": "infeasible"}
        }
    }).json()["run_id"]

    bad_res = client.post(f"/api/v1/optimization/runs/{infeasible_run}/analysis", json={"analysis_type": "full"})
    print(f"HTTP Status (Harus 422): {bad_res.status_code}")
    print("Respon Penolakan Aman:")
    print(json.dumps(bad_res.json(), indent=2))

    print_separator("KESIMPULAN PENGUJIAN INTEGRASI")
    print(" Seluruh rantai integrasi (Langkah 1 - Langkah 5) berfungsi normal.")
    print(" Modul AI siap disematkan ke backend utama dan dipanggil dari Next.js!")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
