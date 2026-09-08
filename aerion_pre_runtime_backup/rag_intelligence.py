from typing import Dict, Any, List

from intelligence_engine import analyze_scene
from protocols import get_protocol
from report_generator import generate_report


# ============================================================
# RAG INTELLIGENCE
# ============================================================

def generate_grounded_intelligence(
    detections: List[Dict[str, Any]],
    mode: str = "disaster"
) -> Dict[str, Any]:

    """
    Convert raw detections into prioritized,
    protocol-grounded intelligence.

    Pipeline:
        Raw Detection
            ↓
        Intelligence Engine
            ↓
        Protocol Retrieval
            ↓
        Mistral Incident Report
    """

    # --------------------------------------------------------
    # STEP 1: Intelligence Engine
    # --------------------------------------------------------

    intelligence = analyze_scene(
        detections=detections,
        mode=mode
    )

    # --------------------------------------------------------
    # STEP 2: Retrieve protocol + generate AI report
    # --------------------------------------------------------

    for item in intelligence["detections"]:

        object_class = item["object_class"]

        # Retrieve standard protocol
        protocol = get_protocol(
            mode,
            object_class
        )

        item["protocol"] = protocol

        # ----------------------------------------------------
        # Prepare detection for Mistral
        # ----------------------------------------------------

        report_detection = {
            "mode": mode,
            "object_class": object_class,
            "confidence": item["confidence"],
            "priority_score": item["priority_score"],
            "priority_bucket": item["priority"],
            "location": item.get(
                "location",
                "unspecified"
            ),
            "change_detected": item.get(
                "change_detected",
                "unknown"
            )
        }

        # ----------------------------------------------------
        # Generate grounded Mistral report
        # ----------------------------------------------------

        try:

            item["ai_report"] = generate_report(
                report_detection
            )

        except Exception as e:

            # Do not allow LLM failure to break
            # the Intelligence Engine.

            item["ai_report"] = (
                "AI report unavailable. "
                "Refer to the detected evidence, "
                "priority score, and standard protocol."
            )

            item["ai_report_error"] = str(e)

    # --------------------------------------------------------
    # STEP 3: Build operator summary
    # --------------------------------------------------------

    summary = intelligence["summary"]

    if summary["critical"] > 0:

        overall_status = "CRITICAL"

    elif summary["high"] > 0:

        overall_status = "HIGH PRIORITY"

    elif summary["medium"] > 0:

        overall_status = "MEDIUM PRIORITY"

    else:

        overall_status = "LOW PRIORITY"

    intelligence["overall_status"] = overall_status

    return intelligence


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    test_detections = [

        {
            "class": "building_damage",
            "confidence": 0.85,
            "background_ssim": 0.4210,
            "local_ssim": 0.2705
        },

        {
            "class": "person",
            "confidence": 0.91,
            "background_ssim": 0.4210,
            "local_ssim": 0.3800
        }

    ]

    result = generate_grounded_intelligence(
        detections=test_detections,
        mode="disaster"
    )

    print("\n==========================================")
    print("GEOSHIELD AI — FULL RAG INTELLIGENCE")
    print("==========================================")

    print(
        f"Mode: {result['mode']}"
    )

    print(
        f"Overall Status: "
        f"{result['overall_status']}"
    )

    print(
        f"Total Detections: "
        f"{result['total_detections']}"
    )

    print("\nPriority Summary:")
    print(result["summary"])

    print("\nDetection Intelligence:")

    for i, item in enumerate(
        result["detections"],
        start=1
    ):

        print(f"\n--- Detection {i} ---")

        print(
            f"Class: "
            f"{item['object_class']}"
        )

        print(
            f"Confidence: "
            f"{item['confidence']}"
        )

        print(
            f"Priority Score: "
            f"{item['priority_score']}"
        )

        print(
            f"Priority: "
            f"{item['priority']}"
        )

        print(
            f"Protocol: "
            f"{item['protocol']}"
        )

        print("\nAI Report:")

        print(
            item["ai_report"]
        )