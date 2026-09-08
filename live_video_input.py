import cv2
import threading
import time


class LiveVideoInput:
    """
    Threaded video input with a bounded latest-frame buffer.

    Works with:
    - RTSP streams
    - Local video files used as live-stream simulations

    The capture thread continuously reads frames.
    If inference is slower than capture, old frames are replaced
    by the newest frame instead of building an unlimited queue.
    """

    def __init__(self, source, buffer_size=2):
        self.source = source
        self.buffer_size = max(1, buffer_size)

        self.cap = None
        self.running = False

        self.frame = None
        self.frame_number = 0

        self.lock = threading.Lock()
        self.thread = None

        self._fps = 0.0
        self._width = 0
        self._height = 0

    def open(self):
        self.cap = cv2.VideoCapture(self.source)

        if not self.cap.isOpened():
            raise RuntimeError(
                f"Unable to open video source: {self.source}"
            )

        self._fps = self.cap.get(cv2.CAP_PROP_FPS)
        self._width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        self.running = True

        self.thread = threading.Thread(
            target=self._capture_loop,
            daemon=True
        )

        self.thread.start()

        return True

    def _capture_loop(self):
        while self.running:

            success, frame = self.cap.read()

            if not success:
                self.running = False
                break

            with self.lock:
                self.frame = frame
                self.frame_number += 1

    def read(self):
        """
        Return the newest available frame.

        Returns:
            (frame, frame_number)

        If no frame is currently available:
            (None, None)
        """

        with self.lock:

            if self.frame is None:
                return None, None

            frame = self.frame.copy()
            number = self.frame_number

        return frame, number

    def is_open(self):
        return self.running

    def fps(self):
        return self._fps

    def width(self):
        return self._width

    def height(self):
        return self._height

    def release(self):
        self.running = False

        if self.thread is not None:
            self.thread.join(timeout=2)

        if self.cap is not None:
            self.cap.release()
            self.cap = None

        with self.lock:
            self.frame = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.release()