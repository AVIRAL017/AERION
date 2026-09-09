import hashlib
from pathlib import Path

models = {
    'Drone': ('runs/detect/visdrone_8s_1280_30ep/weights/best.pt', '343215ac779c1683eef66801b9d0fbf315361074ea71be4356bcb2a40d7a8a2f'),
    'Satellite': ('runs/obb/train-6/weights/best.pt', 'd96c42323b83826db9781981ef34c4c8673ddee9cf84ea0117e473ab040560dd'),
    'Damage': ('change_detection_runs_v2/best_model.pth', '0dc2d422693030f5e2446b54e58bda896bc3ecfc05a250e8df78bf2648d61f6b'),
    'Unified Drone': ('runs/detect/unified_drone_20ep/weights/best.pt', '05281a43dc81ab015491fa1a7c821bdd9b9f13b1d78d80b2a0d549cf30a0a630')
}

all_match = True
for name, (path, expected) in models.items():
    p = Path(path)
    if not p.exists():
        print(f'{name}: MISSING ({path})')
        all_match = False
        continue
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    match = (h == expected)
    if not match:
        all_match = False
    status = "MATCH" if match else "MISMATCH"
    print(f'{name}: {status} ({h})')

if not all_match:
    exit(1)
print('ALL FROZEN HASHES VERIFIED')
