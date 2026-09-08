# from ultralytics import YOLO

# model = YOLO(r"D:\mp-1\runs\detect\visdrone_6class\weights\best.pt")

# results = model(r"C:\Users\avira\yolo_project\datasets\VisDrone\images\val\0000001_05249_d_0000009.jpg", conf=0.5, iou=0.4)
# im = results[0].plot(labels=False, line_width=1)
# import cv2
# cv2.imshow("result", im)
# cv2.waitKey(0)

# from ultralytics import YOLO

# model = YOLO(r"D:\mp-1\runs\detect\visdrone_6class\weights\best.pt")

# results = model.track(
#     source=r"D:\mp-1\220487_medium.mp4",
#     save=True,
#     conf=0.25,
#     iou=0.6,
#     imgsz=1280,
#     agnostic_nms=True,
#     augment=True   # test-time augmentation — slower, but can catch more small objects
# )
# from ultralytics import YOLO

# if __name__ == "__main__":
#     model = YOLO(r"D:\mp-1\runs\obb\train-12\weights\best.pt")
#     metrics = model.val(data="DOTAv1.5_split.yaml")


# from ultralytics import YOLO

# if __name__ == "__main__":
#     model = YOLO(r"D:\mp-1\runs\obb\train-6\weights\best.pt")
#     metrics_640 = model.val(data="DOTAv1.5_split.yaml", imgsz=640)
#     metrics_1280 = model.val(data="DOTAv1.5_split.yaml", imgsz=1280)


# from ultralytics import YOLO

# if __name__ == "__main__":
#     model = YOLO(r"D:\mp-1\runs\obb\train-6\weights\best.pt")
#     model.train(
#         data="DOTAv1.5_split.yaml",
#         epochs=1,
#         imgsz=1280,
#         batch=2,
#         patience=10,
#         workers=1      # reduced from default 8
#     )



# from ultralytics import YOLO

# if __name__ == "__main__":
#     model = YOLO(r"D:\mp-1\runs\obb\train-6\weights\best.pt")

#     model.train(
#         data=r"DOTAv1.5_split.yaml",
#         epochs=15,
#         imgsz=1280,
#         batch=1,
#         patience=15,
#         project=r"D:\mp-1\runs\obb",
#         name="dota_1280_finetune"
#     )



# from ultralytics import YOLO


# if __name__ == "__main__":

#     model = YOLO(
#         r"D:\mp-1\runs\obb\dota_1280_finetune\weights\last.pt"
#     )

#     model.train(
#         resume=True,
#         workers=2
#     )



from ultralytics import YOLO

if __name__ == "__main__":

    # ============================================================
    # 1. LOAD YOLOv8 SMALL PRETRAINED MODEL
    # ============================================================
    model = YOLO("yolov8s.pt")

    # ============================================================
    # 2. TRAIN ON CUSTOM 6-CLASS VISDRONE DATASET
    # ============================================================
    model.train(
        # Dataset
        data=r"D:\mp-1\VisDrone_Custom.yaml",

        # Higher resolution helps with small drone objects
        imgsz=1280,

        # RTX 3050 6GB
        # Start conservatively to avoid CUDA OOM
        batch=1,

        # Training duration
        epochs=30,

        # Allow the full 30 epochs
        patience=30,

        # Windows multiprocessing stability
        workers=2,

        # Optimizer
        optimizer="AdamW",
        lr0=0.0005,

        # GPU
        device=0,

        # Mixed precision
        amp=True,

        # Save checkpoints
        save=True,
        save_period=5,

        # Output directory
        project=r"D:\mp-1\runs\detect",
        name="visdrone_8s_1280_30ep",

        # Don't load entire dataset into RAM
        cache=False
    )