import cv2
from gesture_module_API import detect_gesture

cap = cv2.VideoCapture(0)
last_gesture = None      # 이전 제스처 저장용 (변경 시에만 출력하기 위해)
last_position = None     # 이전 검지 좌표 저장용 (움직임 감지용)
frame_count = 0          # 프레임 카운터 (출력 속도 조절용)
PRINT_INTERVAL = 10      # 몇 프레임마다 출력할지 (숫자 높일수록 느려짐)
MOVE_THRESHOLD = 10      # 몇 픽셀 이상 움직여야 좌표 출력할지

print("카메라 시작! 'q' 누르면 종료")

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame_count += 1
    result = detect_gesture(frame)
    current_gesture = result["gesture"]

    # PRINT_INTERVAL 프레임마다 한 번만 출력 (출력 속도 조절)
    if frame_count % PRINT_INTERVAL == 0:

        # 이전 제스처와 다를 때만 출력 (같은 제스처 반복 출력 방지)
        if current_gesture != last_gesture:
            if current_gesture:
                print("감지된 제스처:", current_gesture)

                # 손가락 개수일 때 숫자도 출력
                if "count" in result:
                    print("손가락 개수:", result["count"])

            last_gesture = current_gesture  # 현재 제스처를 이전으로 저장

        # 검지 좌표가 일정 픽셀 이상 움직였을 때만 출력
        if result["index_position"]:
            curr_pos = result["index_position"]

            if last_position is None:
                last_position = curr_pos
            else:
                dx = abs(curr_pos[0] - last_position[0])
                dy = abs(curr_pos[1] - last_position[1])

                # MOVE_THRESHOLD 픽셀 이상 움직였을 때만 출력
                if dx > MOVE_THRESHOLD or dy > MOVE_THRESHOLD:
                    print("검지 위치:", curr_pos)
                    last_position = curr_pos  # 현재 좌표를 이전으로 저장

    # 화면에 감지 결과 텍스트 표시
    gesture_text = current_gesture if current_gesture else "없음"
    cv2.putText(frame, f"Gesture: {gesture_text}",
                (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    cv2.imshow("Gesture Test", frame)

    # 'q' 키 누르면 종료
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()