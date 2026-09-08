# from ultralytics import YOLO

# model = YOLO("yolov8n.pt")  # nano model, auto-downloads first run
# results = model("https://ultralytics.com/images/bus.jpg")
# results[0].show()


# from ultralytics.utils.downloads import download
# from pathlib import Path

# # This uses ultralytics' built-in VisDrone config, which handles download + conversion
# from ultralytics.cfg import get_cfg

# from ultralytics import YOLO

# if __name__ == "__main__":
#     model = YOLO("yolov8n.pt")
#     model.train(
#         data="VisDrone_custom.yaml",
#         epochs=100,
#         imgsz=640,
#         batch=8,
#         patience=20,
#         save_period=10,
#         name="visdrone_6class"
#     )


from ultralytics import YOLO

if __name__ == "__main__":
    model = YOLO(r"D:\mp-1\runs\detect\visdrone_6class\weights\best.pt")
    model.train(
        data="VisDrone_custom.yaml",   # must specify explicitly this time
        epochs=50,
        imgsz=640,
        batch=8,
        patience=20,
        name="visdrone_6class_extended"
    )
    