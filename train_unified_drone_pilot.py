from ultralytics import YOLO


if __name__ == "__main__":

    # Resume from the 1-epoch pilot checkpoint
    model = YOLO(
        r"D:\mp-1\runs\detect\unified_drone_pilot\weights\last.pt"
    )

    model.train(
        data=r"D:\mp-1\unified_drone_dataset\unified_drone.yaml",

        # Training configuration
        imgsz=1280,
        batch=1,
        epochs=20,
        workers=2,

        # Optimizer
        optimizer="AdamW",
        lr0=0.0005,

        # GPU
        device=0,
        amp=True,

        # Checkpointing
        save=True,
        save_period=1,

        # Dataset
        cache=False,

        # Augmentation
        degrees=0.0,
        translate=0.1,
        scale=0.5,
        fliplr=0.5,
        mosaic=1.0,

        # Output
        project=r"D:\mp-1\runs\detect",
        name="unified_drone_20ep",

        # Generate training plots
        plots=True,

        # Reproducibility
        seed=42,
    )