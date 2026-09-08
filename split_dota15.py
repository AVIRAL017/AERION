from ultralytics.data.split_dota import split_trainval, split_test

# Split train and val sets, with labels
split_trainval(
    data_root=r"C:\Users\avira\yolo_project\datasets\DOTAv1.5",
    save_dir=r"C:\Users\avira\yolo_project\datasets\DOTAv1.5-split",
    rates=[1.0],   # single-scale, as we decided — keeps tile count manageable
    gap=200        # overlap between tiles, so objects at tile edges aren't cut off
)