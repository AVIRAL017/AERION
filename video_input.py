import cv2


class VideoInput:
    """
    Unified video input adapter.

    Supports:
    - Local video files: MP4, AVI, MKV, etc.
    - RTSP live streams

    Downstream ML code receives only OpenCV frames,
    so BorderPipeline does not need to know where
    the frames came from.
    """

    def __init__(self, source):
        self.source = source
        self.cap = None

    def open(self):
        self.cap = cv2.VideoCapture(self.source)

        if not self.cap.isOpened():
            raise RuntimeError(
                f"Unable to open video source: {self.source}"
            )

        return True

    def read(self):
        if self.cap is None:
            raise RuntimeError("VideoInput is not opened.")

        success, frame = self.cap.read()

        if not success:
            return None

        return frame

    def is_open(self):
        return self.cap is not None and self.cap.isOpened()

    def fps(self):
        if not self.is_open():
            return 0.0

        return self.cap.get(cv2.CAP_PROP_FPS)

    def width(self):
        if not self.is_open():
            return 0

        return int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))

    def height(self):
        if not self.is_open():
            return 0

        return int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def release(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()