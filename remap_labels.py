from pathlib import Path

# old_id -> new_id, based on verified VisDrone.yaml order
CLASS_MAP = {
    0: 0,  # pedestrian -> person
    1: 0,  # people -> person
    2: 5,  # bicycle -> other_transport
    3: 1,  # car -> light_vehicle
    4: 1,  # van -> light_vehicle
    5: 3,  # truck -> truck
    6: 5,  # tricycle -> other_transport
    7: 5,  # awning-tricycle -> other_transport
    8: 2,  # bus -> bus
    9: 4,  # motor -> motorbike
}

NEW_NAMES = ["person", "light_vehicle", "bus", "truck", "motorbike", "other_transport"]

def remap_split(labels_dir):
    labels_dir = Path(labels_dir)
    txt_files = list(labels_dir.glob("*.txt"))
    print(f"Remapping {len(txt_files)} label files in {labels_dir}...")

    for txt_file in txt_files:
        lines = txt_file.read_text().strip().splitlines()
        new_lines = []
        for line in lines:
            parts = line.split()
            old_id = int(parts[0])
            new_id = CLASS_MAP[old_id]
            parts[0] = str(new_id)
            new_lines.append(" ".join(parts))
        txt_file.write_text("\n".join(new_lines) + "\n")

    print(f"Done: {labels_dir}")

if __name__ == "__main__":
    base = Path(r"C:\Users\avira\yolo_project\datasets\VisDrone\labels")
    remap_split(base / "train")
    remap_split(base / "val")