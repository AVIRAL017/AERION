from ultralytics import YOLO
if __name__ == "__main__":
    model = YOLO(r"D:\mp-1\runs\obb\train-6\weights\best.pt")
    model.train(
        data="DOTAv1.5_split.yaml",
        epochs=30,
        imgsz=640,
        batch=5,
        patience=10,
        save_period=5
)