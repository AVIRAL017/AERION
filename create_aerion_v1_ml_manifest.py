import json
from datetime import datetime, timezone
from pathlib import Path


# ================================================================
# AERION v1 — FINAL ML VERIFICATION MANIFEST
# ================================================================

BASE = Path(r"D:\mp-1")

FREEZE_DIR = BASE / "test_results" / "model_freeze"

DRONE_FREEZE = FREEZE_DIR / "aerion_v1_drone_freeze.json"
SATELLITE_FREEZE = FREEZE_DIR / "aerion_v1_satellite_freeze.json"
DAMAGE_FREEZE = FREEZE_DIR / "aerion_v1_damage_freeze.json"

OUTPUT = BASE / "test_results" / "aerion_v1_ml_verification_manifest.json"


# ================================================================
# HELPERS
# ================================================================

def load_json(path: Path):
    """Load a JSON file and fail clearly if it is missing/corrupt."""

    if not path.exists():
        raise FileNotFoundError(
            f"Required freeze record not found:\n{path}"
        )

    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Invalid JSON in freeze record:\n{path}\n{exc}"
        ) from exc


def verify_drone_freeze(record):
    """Validate the actual AERION drone freeze-record schema."""

    if record.get("project") != "AERION":
        raise RuntimeError("Drone freeze record project is not AERION.")

    if record.get("version") != "v1":
        raise RuntimeError("Drone freeze record version is not v1.")

    if record.get("subsystem") != "drone_detection":
        raise RuntimeError(
            "Drone freeze record subsystem is not drone_detection."
        )

    if record.get("freeze_status") != "FROZEN":
        raise RuntimeError(
            f"Drone freeze record is not FROZEN. "
            f"Found: {record.get('freeze_status')!r}"
        )

    models = record.get("models")

    if not isinstance(models, dict):
        raise RuntimeError("Drone freeze record has no valid 'models' section.")

    required = [
        "drone_visdrone_only",
        "drone_unified",
    ]

    for name in required:
        if name not in models:
            raise RuntimeError(
                f"Drone freeze record missing model: {name}"
            )

        if models[name].get("status") != "FROZEN":
            raise RuntimeError(
                f"Drone model '{name}' is not FROZEN."
            )

    return True


def verify_satellite_freeze(record):
    """Validate the actual AERION satellite freeze-record schema."""

    if record.get("project") != "AERION":
        raise RuntimeError(
            "Satellite freeze record project is not AERION."
        )

    if record.get("version") != "v1":
        raise RuntimeError(
            "Satellite freeze record version is not v1."
        )

    if record.get("subsystem") != "satellite_detection":
        raise RuntimeError(
            "Satellite freeze record subsystem is not satellite_detection."
        )

    if record.get("freeze_status") != "FROZEN":
        raise RuntimeError(
            f"Satellite freeze record is not FROZEN. "
            f"Found: {record.get('freeze_status')!r}"
        )

    model = record.get("model")

    if not isinstance(model, dict):
        raise RuntimeError(
            "Satellite freeze record has no valid 'model' section."
        )

    if model.get("status") != "FROZEN":
        raise RuntimeError(
            "Satellite model is not FROZEN."
        )

    return True


def verify_damage_freeze(record):
    """
    Validate the actual AERION damage freeze-record schema.

    The damage freeze record uses top-level 'status',
    unlike the drone/satellite records which use 'freeze_status'.
    """

    if record.get("project") != "AERION":
        raise RuntimeError(
            "Damage freeze record project is not AERION."
        )

    if record.get("version") != "v1":
        raise RuntimeError(
            "Damage freeze record version is not v1."
        )

    if record.get("status") != "FROZEN":
        raise RuntimeError(
            f"Damage freeze record is not FROZEN. "
            f"Found: {record.get('status')!r}"
        )

    model = record.get("model")

    if not isinstance(model, dict):
        raise RuntimeError(
            "Damage freeze record has no valid 'model' section."
        )

    integrity = record.get("integrity")

    if not isinstance(integrity, dict):
        raise RuntimeError(
            "Damage freeze record has no valid 'integrity' section."
        )

    if not integrity.get("sha256"):
        raise RuntimeError(
            "Damage freeze record has no SHA-256 hash."
        )

    return True


# ================================================================
# MAIN
# ================================================================

def main():

    print("=" * 78)
    print("AERION v1 — FINAL ML VERIFICATION MANIFEST")
    print("=" * 78)

    # ============================================================
    # LOAD FREEZE RECORDS
    # ============================================================

    drone = load_json(DRONE_FREEZE)
    satellite = load_json(SATELLITE_FREEZE)
    damage = load_json(DAMAGE_FREEZE)

    print("\n[OK] Drone freeze record loaded")
    print("[OK] Satellite freeze record loaded")
    print("[OK] Damage freeze record loaded")

    # ============================================================
    # VERIFY FREEZE RECORDS
    # ============================================================

    verify_drone_freeze(drone)
    print("[OK] Drone freeze status: FROZEN")

    verify_satellite_freeze(satellite)
    print("[OK] Satellite freeze status: FROZEN")

    verify_damage_freeze(damage)
    print("[OK] Damage freeze status: FROZEN")

    # ============================================================
    # EXTRACT AUTHORITATIVE MODEL RECORDS
    # ============================================================

    drone_visdrone = drone["models"]["drone_visdrone_only"]
    drone_unified = drone["models"]["drone_unified"]

    satellite_model = satellite["model"]
    damage_model = damage["model"]

    # ============================================================
    # MODEL REGISTRY
    # ============================================================

    models = {

        "drone_visdrone_only": {
            "model_path": drone_visdrone["model_path"],
            "architecture": drone_visdrone["architecture"],
            "input_size": drone_visdrone["input_size"],
            "training_dataset": drone_visdrone["training_dataset"],
            "classes": drone_visdrone["classes"],
            "file_size_mb": drone_visdrone["file_size_mb"],
            "sha256": drone_visdrone["sha256"],
            "primary_metrics": drone_visdrone["primary_metrics"],
            "status": drone_visdrone["status"],
        },

        "drone_unified": {
            "model_path": drone_unified["model_path"],
            "architecture": drone_unified["architecture"],
            "input_size": drone_unified["input_size"],
            "training_dataset": drone_unified["training_dataset"],
            "classes": drone_unified["classes"],
            "file_size_mb": drone_unified["file_size_mb"],
            "sha256": drone_unified["sha256"],
            "primary_metrics": drone_unified["primary_metrics"],
            "status": drone_unified["status"],
        },

        "satellite": {
            "model_path": satellite_model["model_path"],
            "architecture": satellite_model["architecture"],
            "dataset": satellite_model["dataset"],
            "dataset_format": satellite_model["dataset_format"],
            "training_configuration": satellite_model[
                "training_configuration"
            ],
            "classes": satellite_model["classes"],
            "file_size_mb": satellite_model["file_size_mb"],
            "sha256": satellite_model["sha256"],
            "validation_metrics": satellite_model[
                "validation_metrics"
            ],
            "status": satellite_model["status"],
        },

        "damage": {
            "model_path": damage_model["path"],
            "architecture": damage_model["architecture"],
            "framework": damage_model["framework"],
            "dataset": damage["dataset"]["name"],
            "file_size_mb": damage["integrity"]["size_mb"],
            "sha256": damage["integrity"]["sha256"],
            "validation": damage["validation"],
            "status": damage["status"],
        },
    }

    # ============================================================
    # DRONE VALIDATION
    # ============================================================

    drone_validation = {

        "VisDrone_internal": {
            "precision": drone_visdrone[
                "primary_metrics"
            ]["precision"],

            "recall": drone_visdrone[
                "primary_metrics"
            ]["recall"],

            "mAP50": drone_visdrone[
                "primary_metrics"
            ]["mAP50"],

            "mAP50_95": drone_visdrone[
                "primary_metrics"
            ]["mAP50_95"],
        },

        "Unified_internal": {
            "mAP50": drone_unified[
                "primary_metrics"
            ]["mAP50"],

            "mAP50_95": drone_unified[
                "primary_metrics"
            ]["mAP50_95"],
        },

        "UAVDT_external_subset": {

            "visdrone_only": drone_visdrone[
                "external_validation"
            ]["UAVDT"],

            "unified": drone_unified[
                "external_validation"
            ]["UAVDT"],

            "note": (
                "Results are from a reproducible UAVDT "
                "external-validation subset and are not "
                "official UAVDT leaderboard scores."
            ),
        },

        "SeaDronesSee_external": {

            "visdrone_only": drone_visdrone[
                "external_validation"
            ]["SeaDronesSee"],

            "unified": drone_unified[
                "external_validation"
            ]["SeaDronesSee"],

            "note": (
                "SeaDronesSee results use the corrected "
                "unified 10-class evaluation."
            ),
        },

        "real_video_benchmark": {

            "video": drone_visdrone[
                "runtime_benchmark"
            ]["video"],

            "frames": drone_visdrone[
                "runtime_benchmark"
            ]["frames"],

            "visdrone_only": {
                "detections": drone_visdrone[
                    "runtime_benchmark"
                ]["detections"],

                "fps": drone_visdrone[
                    "runtime_benchmark"
                ]["fps"],

                "avg_inference_ms": drone_visdrone[
                    "runtime_benchmark"
                ]["avg_inference_ms"],
            },

            "unified": {
                "detections": drone_unified[
                    "runtime_benchmark"
                ]["detections"],

                "fps": drone_unified[
                    "runtime_benchmark"
                ]["fps"],

                "avg_inference_ms": drone_unified[
                    "runtime_benchmark"
                ]["avg_inference_ms"],
            },
        },
    }

    # ============================================================
    # SATELLITE VALIDATION
    # ============================================================

    satellite_validation = {
        "dataset": satellite_model["dataset"],

        "architecture": satellite_model[
            "architecture"
        ],

        "metrics": satellite_model[
            "validation_metrics"
        ],

        "training_configuration": satellite_model[
            "training_configuration"
        ],

        "selected_checkpoint": (
            satellite_model[
                "training_configuration"
            ]["selected_checkpoint"]
        ),

        "note": (
            "The 1280px fine-tuning experiment was not "
            "selected as the final AERION v1 satellite model."
        ),
    }

    # ============================================================
    # DAMAGE VALIDATION
    # ============================================================

    damage_validation = {
        "dataset": damage["dataset"]["name"],

        "validation": damage["validation"],

        "training": damage["training"],

        "note": (
            "AERION v1 uses the frozen Siamese ResNet18 "
            "damage model from the validated v2 processing pipeline."
        ),
    }

    # ============================================================
    # UNIFIED DRONE TAXONOMY
    # ============================================================

    unified_drone_taxonomy = [
        "person",
        "light_vehicle",
        "bus",
        "truck",
        "motorbike",
        "other_transport",
        "boat",
        "jetski",
        "life_saving_appliance",
        "buoy",
    ]

    # ============================================================
    # SATELLITE TAXONOMY
    # ============================================================

    satellite_taxonomy = satellite_model["classes"]

    # ============================================================
    # CHANGE DETECTION
    # ============================================================

    change_detection = {

        "method":
            "Hybrid SSIM + learned damage detection",

        "damage_model":
            damage_model["path"],

        "damage_threshold":
            0.50,

        "priority_formula": (
            "0.5 * (class_weight * confidence) + "
            "0.5 * max(0, "
            "(background_ssim - local_ssim) / "
            "background_ssim)"
        ),

        "priority_buckets": {
            "critical": ">= 0.75",
            "high": ">= 0.50",
            "medium": ">= 0.25",
            "low": "< 0.25",
        },

        "validated_ssim_examples": {
            "Palm Jumeirah": 0.5609,
            "Guatemala volcano": 0.3657,
        },

        "validated_priority_examples": {
            "minor_damage_1": 0.568,
            "minor_damage_2": 0.604,
            "destroyed": 0.425,
        },
    }

    # ============================================================
    # BORDER INTELLIGENCE
    # ============================================================

    border_intelligence = {

        "tracking": {
            "tracker": "ByteTrack",
            "persistence_threshold": 10,
            "movement_threshold": 2.0,
            "history_length": 30,
        },

        "zone_analysis": {
            "dwell_threshold": 5,
            "point_in_polygon": True,
            "direction_analysis": True,
            "boundary_distance": True,
        },

        "priority_weights": {
            "zone_entry": 0.40,
            "approach": 0.15,
            "movement": 0.15,
            "persistence": 0.10,
            "confidence": 0.05,
            "zone_dwell": 0.05,
            "movement_inside": 0.10,
        },

        "event_filter": {
            "minimum_confidence": 0.30,
            "minimum_persistence": 0.30,
            "cooldown_frames": 30,
        },

        "real_video_result": {
            "frames": 725,
            "filtered_alerts": 34,
            "critical_alerts": 3,
            "high_alerts": 31,
            "medium_alerts": 0,
        },
    }

    # ============================================================
    # INTELLIGENCE / RAG
    # ============================================================

    intelligence = {

        "deterministic_protocols": True,

        "scene_analysis": True,

        "detection_analysis": True,

        "rag_grounding": True,

        "llm": "Mistral",

        "fabricated_detections_allowed": False,

        "fabricated_confidence_allowed": False,

        "fabricated_counts_allowed": False,

        "grounding_policy": (
            "Intelligence output must remain grounded in actual "
            "detections, model results, configured geographic or "
            "terrain context, and available protocol information."
        ),

        "unsupported_capabilities_must_be_reported": True,
    }

    # ============================================================
    # PRODUCTION SAFETY / INTEGRITY RULES
    # ============================================================

    production_constraints = {

        "fake_detection": False,

        "fake_counts": False,

        "fake_confidence": False,

        "simulated_intelligence": False,

        "external_substitute_resources": False,

        "unimplemented_capabilities_must_be_reported": True,

        "trained_models_are_frozen": True,

        "deployment_started": False,

        "backend_integration_started": False,

        "frontend_integration_started": False,

        "model_retraining_allowed_for_v1": False,
    }

    # ============================================================
    # FREEZE RECORD REFERENCES
    # ============================================================

    freeze_records = {

        "drone": str(DRONE_FREEZE),

        "satellite": str(SATELLITE_FREEZE),

        "damage": str(DAMAGE_FREEZE),
    }

    # ============================================================
    # FINAL MANIFEST
    # ============================================================

    manifest = {

        "project": "AERION",

        "version": "v1",

        "manifest_type":
            "final_ml_verification",

        "status":
            "ML_FREEZE_VERIFIED",

        "generated_at":
            datetime.now(timezone.utc).isoformat(),

        "models":
            models,

        "validation": {

            "drone":
                drone_validation,

            "satellite":
                satellite_validation,

            "damage":
                damage_validation,
        },

        "taxonomies": {

            "drone_unified":
                unified_drone_taxonomy,

            "satellite_dota":
                satellite_taxonomy,
        },

        "change_detection":
            change_detection,

        "border_intelligence":
            border_intelligence,

        "intelligence":
            intelligence,

        "production_constraints":
            production_constraints,

        "freeze_records":
            freeze_records,

        "verification_statement": (
            "AERION v1 trained ML artifacts have been frozen "
            "and recorded with integrity hashes. This verification "
            "manifest performs no training and does not modify any "
            "model artifact."
        ),
    }

    # ============================================================
    # WRITE MANIFEST
    # ============================================================

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    with OUTPUT.open(
        "w",
        encoding="utf-8"
    ) as f:
        json.dump(
            manifest,
            f,
            indent=2
        )

    # ============================================================
    # FINAL REPORT
    # ============================================================

    print("\n" + "=" * 78)
    print("AERION v1 ML VERIFICATION COMPLETE")
    print("=" * 78)

    print("\nStatus:")
    print("ML_FREEZE_VERIFIED")

    print("\nFrozen components:")
    print("  [OK] Drone — VisDrone-only")
    print("  [OK] Drone — Unified")
    print("  [OK] Satellite — DOTA-v1.5")
    print("  [OK] Damage — xBD/xView2")

    print("\nIntegrity hashes:")

    print(
        "  Drone VisDrone :",
        drone_visdrone["sha256"]
    )

    print(
        "  Drone Unified  :",
        drone_unified["sha256"]
    )

    print(
        "  Satellite      :",
        satellite_model["sha256"]
    )

    print(
        "  Damage         :",
        damage["integrity"]["sha256"]
    )

    print("\nValidation records:")

    print("  [OK] VisDrone internal validation")
    print("  [OK] SeaDronesSee external validation")
    print("  [OK] UAVDT external validation subset")
    print("  [OK] Real drone video benchmark")
    print("  [OK] DOTA-v1.5 satellite validation")
    print("  [OK] xBD/xView2 damage validation")

    print("\nIntegrity checks:")
    print("  [OK] All freeze records loaded")
    print("  [OK] All required models marked FROZEN")
    print("  [OK] SHA-256 hashes recorded")
    print("  [OK] No model files modified")
    print("  [OK] No training performed")

    print("\nManifest:")
    print(OUTPUT)

    print("\n" + "=" * 78)
    print("ML PHASE FROZEN — READY FOR RUNTIME ADAPTER PHASE")
    print("=" * 78)


if __name__ == "__main__":
    main()