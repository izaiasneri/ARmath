import os
import sys

import cv2


def camera_output():
    if sys.stdout is not None:
        return os.fdopen(os.dup(sys.stdout.fileno()), "wb")

    # The Windows GUI executable has no Python stdout, but QProcess passes a pipe handle.
    from ctypes import WinDLL, WinError, wintypes
    import msvcrt

    get_std_handle = WinDLL("kernel32", use_last_error=True).GetStdHandle
    get_std_handle.argtypes = (wintypes.DWORD,)
    get_std_handle.restype = wintypes.HANDLE
    handle = get_std_handle(-11)  # STD_OUTPUT_HANDLE
    if handle in (None, wintypes.HANDLE(-1).value):
        raise WinError()
    return os.fdopen(msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY), "wb")


def stream(camera_index, backend):
    capture = cv2.VideoCapture(camera_index, backend)
    try:
        if not capture.isOpened():
            return 1
        capture.set(cv2.CAP_PROP_FRAME_WIDTH, 800)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 600)
        with camera_output() as output:
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
