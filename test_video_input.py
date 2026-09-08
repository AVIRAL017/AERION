from video_input import VideoInput


VIDEO_PATH = (
    r"D:\mp-1\border_test_videos"
    r"\border_test_urban.mp4.mp4"
)


def main():

    video = VideoInput(VIDEO_PATH)

    video.open()

    print("=" * 60)
    print("VIDEO INPUT TEST")
    print("=" * 60)

    print("Source:", VIDEO_PATH)
    print("Width:", video.width())
    print("Height:", video.height())
    print("FPS:", video.fps())

    frame_count = 0

    while True:

        frame = video.read()

        if frame is None:
            break

        frame_count += 1

        if frame_count % 100 == 0:
            print(
                f"Frames read: {frame_count}"
            )

    video.release()

    print("=" * 60)
    print(
        "Total frames:",
        frame_count
    )
    print("VIDEO INPUT TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()