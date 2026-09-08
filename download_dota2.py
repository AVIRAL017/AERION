from ultralytics import YOLO

if __name__ == "__main__":
    model = YOLO("yolov8n-obb.pt")
    try:
        model.train(data="DOTAv1.5.yaml", epochs=1, imgsz=640,batch=8)
    except Exception as e:
        print(f"Expected — dataset not split yet: {e}")