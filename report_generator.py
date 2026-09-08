import os
import requests
from dotenv import load_dotenv
from protocols import get_protocol

load_dotenv()

MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
MISTRAL_URL = "https://api.mistral.ai/v1/chat/completions"


def generate_report(detection):
    if not MISTRAL_API_KEY:
        raise RuntimeError("MISTRAL_API_KEY environment variable is not set.")

    protocol = get_protocol(
        detection["mode"],
        detection["object_class"]
    )

    prompt = f"""
You are generating a short incident report for a
{detection['mode']} monitoring system operator.

Detection details:
- Object class: {detection['object_class']}
- Confidence: {detection['confidence']:.2f}
- Priority score: {detection['priority_score']:.3f}
- Priority level: {detection['priority_bucket']}
- Location: {detection.get('location', 'unspecified')}
- Change signal detected: {detection.get('change_detected', 'unknown')}

Relevant standard protocol:
{protocol}

Write a concise, plain-language incident report in 5-6 sentences.

The report must:
1. State what was detected.
2. Explain why it matters based on the priority level.
3. Reference the standard protocol.
4. Avoid inventing facts, locations, causes, casualties, or actions.
5. Clearly distinguish detected evidence from recommended action.
6. Do not interpret an SSIM drop as structural instability, severity,
   casualties, or physical risk unless that information is explicitly provided.
7. Do not use words such as "significant", "severe", "unstable",
   "dangerous", or "risk" unless supported by the supplied data.
8. Use normal spaces between all words and punctuation.
9. Do not call a detection an "anomaly" unless the input explicitly says
   that an anomaly was detected.
10. Do not infer damage extent, physical impact, threat level, or danger
    unless explicitly provided.
11. Use the exact object class provided by the detection data.
12. Treat the protocol as a recommendation, not as evidence that the
    recommended condition has already been confirmed.
13. Do not describe what a priority level "indicates" beyond stating the
    assigned priority level. Do not infer urgency, danger, concern, or risk
    from the priority level.

14. If information is unavailable or marked as "unspecified" or "unknown",
    do not discuss its absence unless it materially affects the report.
"""

    response = requests.post(
        MISTRAL_URL,
        headers={
            "Authorization": f"Bearer {MISTRAL_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "open-mistral-nemo",
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0.2
        },
        timeout=60
    )

    if response.status_code != 200:
        print("Mistral API Error")
        print("Status:", response.status_code)
        print("Response:", response.text)
        print("Rate Limit Remaining:", response.headers.get("X-RateLimit-Remaining"))
        response.raise_for_status()

    

    data = response.json()

    return data["choices"][0]["message"]["content"]


if __name__ == "__main__":

    test_detection = {
        "mode": "disaster",
        "object_class": "building_damage",
        "confidence": 0.85,
        "priority_score": 0.604,
        "priority_bucket": "High",
        "location": "Guatemala volcano tile 00000003",
        "change_detected": "SSIM local drop of 0.36 relative to surrounding terrain"
    }

    report = generate_report(test_detection)

    print("\n==========================================")
    print("GEOSHIELD AI — MISTRAL INCIDENT REPORT")
    print("==========================================\n")
    print(report)











