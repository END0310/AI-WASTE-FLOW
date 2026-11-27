"""
Test dataset representing 12 diverse operational conditions for WasteFlow AI Evaluation
as specified in WasteFlow AI Intelligence Specification v1.0 Section 9.2.
"""

from typing import List, Dict, Any

EVALUATION_CASES: List[Dict[str, Any]] = [
    {
        "id": "case_01_normal_balanced",
        "name": "Normal Balanced Operation",
        "expected_eligibility": True,
        "payload": {
            "facility": {"facility_id": "fac-01", "facility_name": "TPS3R Sukamaju"},
            "period": {"start": "2026-11-01", "end": "2026-11-07", "capacity_period": "day"},
            "solver": {"status": "optimal", "name": "PuLP", "version": "2.8"},
            "weights": {"cost": 0.333, "recovery": 0.333, "residual": 0.334},
            "data_source": "field",
            "metrics": {
                "total_input_kg": 1200.0,
                "total_cost_rp": 850000.0,
                "recovered_kg": 720.0,
                "recovery_rate": 0.60,
                "residual_kg": 180.0,
                "residual_rate": 0.15
            },
            "routes": [
                {"route_id": "route-sorting", "route_name": "Sorting Line", "allocated_kg": 500.0, "capacity_kg": 700.0, "utilization_rate": 0.714},
                {"route_id": "route-compost", "route_name": "Composting Bed", "allocated_kg": 450.0, "capacity_kg": 600.0, "utilization_rate": 0.75}
            ],
            "allocations": [
                {"material_id": "mat-plastic", "material_name": "Plastic", "route_id": "route-sorting", "allocated_kg": 300.0},
                {"material_id": "mat-organic", "material_name": "Organic", "route_id": "route-compost", "allocated_kg": 450.0}
            ],
            "baseline_metrics": {
                "status": "feasible",
                "total_cost_rp": 920000.0,
                "recovered_kg": 680.0,
                "residual_kg": 210.0
            }
        }
    },
    {
        "id": "case_02_high_utilization_bottleneck",
        "name": "High Utilization / Bottleneck in Sorting",
        "expected_eligibility": True,
        "payload": {
            "facility": {"facility_id": "fac-01", "facility_name": "TPS3R Sukamaju"},
            "period": {"start": "2026-11-01", "end": "2026-11-07", "capacity_period": "day"},
            "solver": {"status": "optimal", "name": "PuLP", "version": "2.8"},
            "weights": {"cost": 0.2, "recovery": 0.6, "residual": 0.2},
            "data_source": "field",
            "metrics": {
                "total_input_kg": 1500.0,
                "total_cost_rp": 980000.0,
                "recovered_kg": 1050.0,
                "recovery_rate": 0.70,
                "residual_kg": 200.0,
                "residual_rate": 0.133
            },
            "routes": [
                {"route_id": "route-sorting", "route_name": "Sorting Line", "allocated_kg": 665.0, "capacity_kg": 700.0, "utilization_rate": 0.95},
                {"route_id": "route-compost", "route_name": "Composting Bed", "allocated_kg": 400.0, "capacity_kg": 600.0, "utilization_rate": 0.667}
            ],
            "allocations": [
                {"material_id": "mat-plastic", "material_name": "Plastic", "route_id": "route-sorting", "allocated_kg": 665.0}
            ]
        }
    },
    {
        "id": "case_03_slack_capacity",
        "name": "Slack Capacity (Low Utilization)",
        "expected_eligibility": True,
        "payload": {
            "facility": {"facility_id": "fac-02", "facility_name": "TPS3R Mandiri"},
            "period": {"start": "2026-11-01", "end": "2026-11-07", "capacity_period": "day"},
            "solver": {"status": "optimal", "name": "PuLP", "version": "2.8"},
            "weights": {"cost": 0.333, "recovery": 0.333, "residual": 0.334},
            "data_source": "field",
            "metrics": {
                "total_input_kg": 400.0,
                "total_cost_rp": 320000.0,
                "recovered_kg": 240.0,
                "recovery_rate": 0.60,
                "residual_kg": 60.0,
                "residual_rate": 0.15
            },
            "routes": [
                {"route_id": "route-sorting", "route_name": "Sorting Line", "allocated_kg": 200.0, "capacity_kg": 700.0, "utilization_rate": 0.286},
                {"route_id": "route-compost", "route_name": "Composting Bed", "allocated_kg": 150.0, "capacity_kg": 600.0, "utilization_rate": 0.25}
            ],
            "allocations": [
                {"material_id": "mat-plastic", "material_name": "Plastic", "route_id": "route-sorting", "allocated_kg": 200.0}
            ]
        }
    },
    {
        "id": "case_04_synthetic_data",
        "name": "Synthetic Data Run (Requires Simulation Caveat)",
        "expected_eligibility": True,
        "payload": {
            "facility": {"facility_id": "fac-demo", "facility_name": "TPS3R Virtual Demo"},
            "period": {"start": "2026-11-01", "end": "2026-11-07", "capacity_period": "day"},
            "solver": {"status": "optimal", "name": "PuLP", "version": "2.8"},
            "weights": {"cost": 0.333, "recovery": 0.333, "residual": 0.334},
            "data_source": "synthetic",
            "metrics": {
                "total_input_kg": 1000.0,
                "total_cost_rp": 700000.0,
                "recovered_kg": 600.0,
                "recovery_rate": 0.60,
                "residual_kg": 150.0,
                "residual_rate": 0.15
            },
            "routes": [
                {"route_id": "route-sorting", "route_name": "Sorting Line", "allocated_kg": 400.0, "capacity_kg": 600.0, "utilization_rate": 0.667}
            ],
            "allocations": [
                {"material_id": "mat-paper", "material_name": "Paper", "route_id": "route-sorting", "allocated_kg": 400.0}
            ]
        }
    },
    {
        "id": "case_05_baseline_unavailable",
        "name": "Baseline Unavailable Run",
        "expected_eligibility": True,
        "payload": {
            "facility": {"facility_id": "fac-01", "facility_name": "TPS3R Sukamaju"},
            "period": {"start": "2026-11-01", "end": "2026-11-07", "capacity_period": "day"},
            "solver": {"status": "optimal", "name": "PuLP", "version": "2.8"},
            "weights": {"cost": 0.333, "recovery": 0.333, "residual": 0.334},
            "data_source": "field",
            "baseline_metrics": None,
            "metrics": {
                "total_input_kg": 1100.0,
                "total_cost_rp": 790000.0,
                "recovered_kg": 660.0,
                "recovery_rate": 0.60,
                "residual_kg": 165.0,
                "residual_rate": 0.15
            },
            "routes": [
                {"route_id": "route-sorting", "route_name": "Sorting Line", "allocated_kg": 450.0, "capacity_kg": 600.0, "utilization_rate": 0.75}
            ],
            "allocations": [
                {"material_id": "mat-glass", "material_name": "Glass", "route_id": "route-sorting", "allocated_kg": 450.0}
            ]
        }
    },
    {
        "id": "case_06_yield_assumption",
        "name": "Yield Assumption Flagged",
        "expected_eligibility": True,
        "payload": {
            "facility": {"facility_id": "fac-01", "facility_name": "TPS3R Sukamaju"},
            "period": {"start": "2026-11-01", "end": "2026-11-07", "capacity_period": "day"},
            "solver": {"status": "optimal", "name": "PuLP", "version": "2.8"},
            "weights": {"cost": 0.333, "recovery": 0.333, "residual": 0.334},
            "data_source": "field",
            "is_yield_assumed": True,
            "metrics": {
                "total_input_kg": 1200.0,
                "total_cost_rp": 850000.0,
                "recovered_kg": 720.0,
                "recovery_rate": 0.60,
                "residual_kg": 180.0,
                "residual_rate": 0.15
            },
            "routes": [
                {"route_id": "route-compost", "route_name": "Composting Bed", "allocated_kg": 500.0, "capacity_kg": 600.0, "utilization_rate": 0.833}
            ],
            "allocations": [
                {"material_id": "mat-organic", "material_name": "Organic", "route_id": "route-compost", "allocated_kg": 500.0}
            ]
        }
    },
    {
        "id": "case_07_recovery_priority",
        "name": "Recovery Priority Weighting",
        "expected_eligibility": True,
        "payload": {
            "facility": {"facility_id": "fac-01", "facility_name": "TPS3R Sukamaju"},
            "period": {"start": "2026-11-01", "end": "2026-11-07", "capacity_period": "day"},
            "solver": {"status": "optimal", "name": "PuLP", "version": "2.8"},
            "weights": {"cost": 0.1, "recovery": 0.8, "residual": 0.1},
            "data_source": "field",
            "metrics": {
                "total_input_kg": 1300.0,
                "total_cost_rp": 1100000.0,
                "recovered_kg": 1040.0,
                "recovery_rate": 0.80,
                "residual_kg": 130.0,
                "residual_rate": 0.10
            },
            "routes": [
                {"route_id": "route-sorting", "route_name": "Sorting Line", "allocated_kg": 550.0, "capacity_kg": 700.0, "utilization_rate": 0.785}
            ],
            "allocations": [
                {"material_id": "mat-plastic", "material_name": "Plastic", "route_id": "route-sorting", "allocated_kg": 550.0}
            ]
        }
    },
    {
        "id": "case_08_cost_priority",
        "name": "Cost Priority Weighting",
        "expected_eligibility": True,
        "payload": {
            "facility": {"facility_id": "fac-01", "facility_name": "TPS3R Sukamaju"},
            "period": {"start": "2026-11-01", "end": "2026-11-07", "capacity_period": "day"},
            "solver": {"status": "optimal", "name": "PuLP", "version": "2.8"},
            "weights": {"cost": 0.8, "recovery": 0.1, "residual": 0.1},
            "data_source": "field",
            "metrics": {
                "total_input_kg": 1200.0,
                "total_cost_rp": 450000.0,
                "recovered_kg": 480.0,
                "recovery_rate": 0.40,
                "residual_kg": 420.0,
                "residual_rate": 0.35
            },
            "routes": [
                {"route_id": "route-sorting", "route_name": "Sorting Line", "allocated_kg": 350.0, "capacity_kg": 700.0, "utilization_rate": 0.50}
            ],
            "allocations": [
                {"material_id": "mat-plastic", "material_name": "Plastic", "route_id": "route-sorting", "allocated_kg": 350.0}
            ]
        }
    },
    {
        "id": "case_09_residual_priority",
        "name": "Residual Minimization Priority",
        "expected_eligibility": True,
        "payload": {
            "facility": {"facility_id": "fac-01", "facility_name": "TPS3R Sukamaju"},
            "period": {"start": "2026-11-01", "end": "2026-11-07", "capacity_period": "day"},
            "solver": {"status": "optimal", "name": "PuLP", "version": "2.8"},
            "weights": {"cost": 0.15, "recovery": 0.15, "residual": 0.70},
            "data_source": "field",
            "metrics": {
                "total_input_kg": 1200.0,
                "total_cost_rp": 920000.0,
                "recovered_kg": 850.0,
                "recovery_rate": 0.708,
                "residual_kg": 90.0,
                "residual_rate": 0.075
            },
            "routes": [
                {"route_id": "route-sorting", "route_name": "Sorting Line", "allocated_kg": 500.0, "capacity_kg": 700.0, "utilization_rate": 0.714}
            ],
            "allocations": [
                {"material_id": "mat-plastic", "material_name": "Plastic", "route_id": "route-sorting", "allocated_kg": 500.0}
            ]
        }
    },
    {
        "id": "case_10_missing_route_profile",
        "name": "Missing Route Profile Parameter",
        "expected_eligibility": True,
        "payload": {
            "facility": {"facility_id": "fac-01", "facility_name": "TPS3R Sukamaju"},
            "period": {"start": "2026-11-01", "end": "2026-11-07", "capacity_period": "day"},
            "solver": {"status": "optimal", "name": "PuLP", "version": "2.8"},
            "weights": {"cost": 0.333, "recovery": 0.333, "residual": 0.334},
            "data_source": "field",
            "has_missing_routes": True,
            "metrics": {
                "total_input_kg": 1000.0,
                "total_cost_rp": 700000.0,
                "recovered_kg": 600.0,
                "recovery_rate": 0.60,
                "residual_kg": 150.0,
                "residual_rate": 0.15
            },
            "routes": [
                {"route_id": "route-sorting", "route_name": "Sorting Line", "allocated_kg": 400.0, "capacity_kg": 600.0, "utilization_rate": 0.667}
            ],
            "allocations": [
                {"material_id": "mat-glass", "material_name": "Glass", "route_id": "route-sorting", "allocated_kg": 400.0}
            ]
        }
    },
    {
        "id": "case_11_solver_feasible_non_optimal",
        "name": "Solver Feasible (Non-Optimal)",
        "expected_eligibility": True,
        "payload": {
            "facility": {"facility_id": "fac-01", "facility_name": "TPS3R Sukamaju"},
            "period": {"start": "2026-11-01", "end": "2026-11-07", "capacity_period": "day"},
            "solver": {"status": "feasible", "name": "PuLP", "version": "2.8"},
            "weights": {"cost": 0.333, "recovery": 0.333, "residual": 0.334},
            "data_source": "field",
            "metrics": {
                "total_input_kg": 1000.0,
                "total_cost_rp": 750000.0,
                "recovered_kg": 550.0,
                "recovery_rate": 0.55,
                "residual_kg": 250.0,
                "residual_rate": 0.25
            },
            "routes": [
                {"route_id": "route-sorting", "route_name": "Sorting Line", "allocated_kg": 400.0, "capacity_kg": 600.0, "utilization_rate": 0.667}
            ],
            "allocations": [
                {"material_id": "mat-plastic", "material_name": "Plastic", "route_id": "route-sorting", "allocated_kg": 400.0}
            ]
        }
    },
    {
        "id": "case_12_solver_infeasible",
        "name": "Solver Infeasible (Must be Blocked)",
        "expected_eligibility": False,
        "payload": {
            "facility": {"facility_id": "fac-01", "facility_name": "TPS3R Sukamaju"},
            "period": {"start": "2026-11-01", "end": "2026-11-07", "capacity_period": "day"},
            "solver": {"status": "infeasible", "name": "PuLP", "version": "2.8"},
            "weights": {"cost": 0.333, "recovery": 0.333, "residual": 0.334},
            "data_source": "field",
            "metrics": {
                "total_input_kg": 0.0,
                "total_cost_rp": 0.0,
                "recovered_kg": 0.0,
                "recovery_rate": 0.0,
                "residual_kg": 0.0,
                "residual_rate": 0.0
            },
            "routes": [],
            "allocations": []
        }
    },
    {
        "id": "case_13_period_mismatch",
        "name": "Period Mismatch (Must be Blocked before Gemini)",
        "expected_eligibility": False,
        "payload": {
            "facility": {"facility_id": "fac-01", "facility_name": "TPS3R Sukamaju"},
            "period": {"start": "2026-11-01", "end": "2026-11-07", "capacity_period": "day"},
            "solver": {"status": "optimal", "name": "PuLP", "version": "2.8"},
            "weights": {"cost": 0.333, "recovery": 0.333, "residual": 0.334},
            "data_source": "field",
            "is_period_mismatched": True,
            "metrics": {"total_input_kg": 1000.0, "total_cost_rp": 700000.0, "recovered_kg": 600.0,
                        "recovery_rate": 0.60, "residual_kg": 150.0, "residual_rate": 0.15},
            "routes": [{"route_id": "route-sorting", "route_name": "Sorting Line", "allocated_kg": 400.0,
                        "capacity_kg": 600.0, "utilization_rate": 0.667}],
            "allocations": [{"material_id": "mat-plastic", "material_name": "Plastic",
                             "route_id": "route-sorting", "allocated_kg": 400.0}]
        }
    },
    {
        "id": "case_14_solver_unbounded",
        "name": "Solver Unbounded (Must be Blocked)",
        "expected_eligibility": False,
        "payload": {
            "facility": {"facility_id": "fac-01", "facility_name": "TPS3R Sukamaju"},
            "period": {"start": "2026-11-01", "end": "2026-11-07", "capacity_period": "day"},
            "solver": {"status": "Unbounded", "name": "PuLP", "version": "2.8"},
            "weights": {"cost": 0.333, "recovery": 0.333, "residual": 0.334},
            "data_source": "field",
            "metrics": {"total_input_kg": 1000.0, "total_cost_rp": 0.0, "recovered_kg": 0.0,
                        "recovery_rate": 0.0, "residual_kg": 0.0, "residual_rate": 0.0}
        }
    },
    {
        "id": "case_15_synthetic_bottleneck_yield",
        "name": "Synthetic + Bottleneck + Yield Assumption",
        "expected_eligibility": True,
        "payload": {
            "facility": {"facility_id": "fac-demo", "facility_name": "TPS3R Virtual Demo"},
            "period": {"start": "2026-11-01", "end": "2026-11-07", "capacity_period": "day"},
            "solver": {"status": "optimal", "name": "PuLP", "version": "2.8"},
            "weights": {"cost": 0.2, "recovery": 0.6, "residual": 0.2},
            "data_source": "synthetic",
            "is_yield_assumed": True,
            "metrics": {"total_input_kg": 1400.0, "total_cost_rp": 990000.0, "recovered_kg": 910.0,
                        "recovery_rate": 0.65, "residual_kg": 210.0, "residual_rate": 0.15},
            "routes": [
                {"route_id": "route-sorting", "route_name": "Sorting Line", "allocated_kg": 680.0,
                 "capacity_kg": 700.0, "utilization_rate": 0.971},
                {"route_id": "route-compost", "route_name": "Composting Bed", "allocated_kg": 420.0,
                 "capacity_kg": 600.0, "utilization_rate": 0.7}
            ],
            "allocations": [
                {"material_id": "mat-plastic", "material_name": "Plastic", "route_id": "route-sorting", "allocated_kg": 680.0},
                {"material_id": "mat-organic", "material_name": "Organic", "route_id": "route-compost", "allocated_kg": 420.0}
            ]
        }
    }
]
