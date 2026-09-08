from ultralytics import YOLO

if __name__ == "__main__":
    model = YOLO(r"D:\mp-1\runs\obb\train-6\weights\best.pt")

    results = model(
        r"C:\Users\avira\yolo_project\datasets\DOTAv1.5-split\images\val\P0004__1024__0___440.jpg",
        conf=0.4
    )
    results[0].show()