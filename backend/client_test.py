import asyncio
import json
import time
from typing import List, Tuple

import cv2
import websockets


def _draw_landmarks(
    frame: "cv2.Mat",
    keypoints: List[List[int]],
    topology: List[List[int]],
) -> None:
    """Draw keypoints and lines on a frame."""

    for x, y in keypoints:
        cv2.circle(frame, (int(x), int(y)), 5, (0, 255, 0), -1)

    for start, end in topology:
        if start < len(keypoints) and end < len(keypoints):
            p1 = tuple(map(int, keypoints[start]))
            p2 = tuple(map(int, keypoints[end]))
            cv2.line(frame, p1, p2, (0, 255, 0), 2)


async def send_video(uri: str) -> None:
    async with websockets.connect(uri) as websocket:
        # Start a dedicated thread for OpenCV windows to avoid Qt threading
        # errors when ``cv2.imshow`` is called from an asyncio coroutine.
        cv2.startWindowThread()
        cap = cv2.VideoCapture(0)
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                success, buffer = cv2.imencode(".jpg", frame)
                if not success:
                    continue

                send_time = time.time()
                await websocket.send(buffer.tobytes())

                response = await websocket.recv()
                delay_ms = int((time.time() - send_time) * 1000)
                data = json.loads(response)

                keypoints = data.get("keypoints", [])
                topology = data.get("topology", [])

                if keypoints:
                    _draw_landmarks(frame, keypoints, topology)

                cv2.putText(
                    frame,
                    f"{delay_ms} ms",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (0, 255, 0),
                    2,
                )

                cv2.imshow("Client Frame", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
        finally:
            cap.release()
            cv2.destroyAllWindows()


if __name__ == "__main__":
    asyncio.run(send_video("ws://localhost:5000/ws"))

