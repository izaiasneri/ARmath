import sys

import cv2


def stream(camera_index, backend):
    capture = cv2.VideoCapture(camera_index, backend)
    try:
        if not capture.isOpened():
            return 1
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 800)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 600)
        output = sys.stdout.buffer
        while True:
            success, frame = capture.read()
            if not success:
                return 1
            encoded, jpeg = cv2.imencode(".jpg", frame)
            if encoded:
                output.write(jpeg.nbytes.to_bytes(4, "big"))
                output.write(jpeg.tobytes())
                output.flush()
    finally:
        capture.release()


if __name__ == "__main__":
    sys.exit(stream(int(sys.argv[1]), int(sys.argv[2])))
