import time

from live_video_input import LiveVideoInput


VIDEO_PATH = r"D:\mp-1\border_test_videos\border_test_urban.mp4.mp4"


def main():

    print("=" * 60)
    print("LIVE VIDEO INPUT TEST")
    print("=" * 60)

    video = LiveVideoInput(
        VIDEO_PATH,
        buffer_size=2
    )

    video.open()

    print(f"Source: {VIDEO_PATH}")
    print(f"Width: {video.width()}")
    print(f"Height: {video.height()}")
    print(f"FPS: {video.fps()}")
    print()

    frames_received = 0
    last_frame_number = None

    start_time = time.perf_counter()

    while video.is_open():

        frame, frame_number = video.read()

        if frame is None:
            time.sleep(0.001)
            continue

        # Count only newly received frames
        if frame_number != last_frame_number:

            frames_received += 1
            last_frame_number = frame_number

            if frames_received % 100 == 0:
                print(
                    f"New frames received: {frames_received} "
                    f"| Source frame: {frame_number}"
                )

        time.sleep(0.01)

    elapsed = time.perf_counter() - start_time

    video.release()

    print("=" * 60)
    print("LIVE VIDEO INPUT TEST COMPLETE")
    print("=" * 60)

    print(f"New frames received: {frames_received}")
    print(f"Elapsed time: {elapsed:.2f} seconds")
    print("=" * 60)


if __name__ == "__main__":
    main()