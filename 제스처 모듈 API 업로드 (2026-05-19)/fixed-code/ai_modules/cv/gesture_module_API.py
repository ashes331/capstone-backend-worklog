import cv2
import mediapipe as mp
from collections import deque

# MediaPipe Hands 초기화 (손 인식 모듈)
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(static_image_mode=False, max_num_hands=1)

# 스와이프 감지를 위한 손목 위치 기록 버퍼 (최근 15프레임)
wrist_buffer = deque(maxlen=15)


def detect_gesture(frame):
    """
    카메라 프레임을 받아 제스처와 검지 끝 좌표를 반환
    """
    try:
        # BGR → RGB 변환 (MediaPipe는 RGB만 처리)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = hands.process(rgb)

        if not result.multi_hand_landmarks:
            wrist_buffer.clear()  # 손이 없으면 버퍼 초기화
            return {"gesture": None, "index_position": None}

        landmarks = result.multi_hand_landmarks[0].landmark
        h, w, _ = frame.shape  # 프레임 실제 픽셀 크기

        # 손목(0번) 좌표를 픽셀로 변환해서 버퍼에 저장
        wrist_x = int(landmarks[0].x * w)
        wrist_y = int(landmarks[0].y * h)
        wrist_buffer.append((wrist_x, wrist_y))

        # 검지 끝(8번) 좌표를 항상 픽셀로 변환 (제스처와 무관하게 항상 추적)
        index_x = int(landmarks[8].x * w)
        index_y = int(landmarks[8].y * h)
        index_position = (index_x, index_y)

        # 제스처 우선순위대로 감지
        swipe = _detect_swipe()
        if swipe:
            return {"gesture": swipe, "index_position": index_position}

        if _is_ok(landmarks):
            return {"gesture": "ok", "index_position": index_position}

        # 손가락 개수 감지 (1~5)
        finger_count = _count_fingers(landmarks)
        if finger_count > 0:
            return {"gesture": f"finger_{finger_count}", "count": finger_count, "index_position": index_position}

        return {"gesture": None, "index_position": index_position}

    except Exception as e:
        return {"gesture": None, "index_position": None, "error": str(e)}


def _detect_swipe():
    """손목 이동 궤적으로 스와이프 방향 감지"""
    if len(wrist_buffer) < 10:  # 데이터가 충분하지 않으면 감지 안 함
        return None

    # 버퍼의 처음과 끝 위치 차이로 이동 방향 계산
    dx = wrist_buffer[-1][0] - wrist_buffer[0][0]  # 좌우 이동량
    dy = wrist_buffer[-1][1] - wrist_buffer[0][1]  # 상하 이동량
    dist = (dx**2 + dy**2) ** 0.5  # 총 이동 거리

    if dist < 80:  # 80픽셀 미만이면 스와이프로 인정 안 함
        return None

    # 이동량이 더 큰 축을 기준으로 방향 결정
    if abs(dx) > abs(dy):
        return "swipe_right" if dx > 0 else "swipe_left"
    else:
        return "swipe_down" if dy > 0 else "swipe_up"


def _is_ok(landmarks):
    """엄지(4번)와 검지(8번) 끝이 가깝고 나머지 손가락이 펴져 있으면 OK"""
    thumb = landmarks[4]
    index = landmarks[8]
    dist = ((thumb.x - index.x) ** 2 + (thumb.y - index.y) ** 2) ** 0.5

    middle_open = landmarks[12].y < landmarks[10].y
    ring_open   = landmarks[16].y < landmarks[14].y
    pinky_open  = landmarks[20].y < landmarks[18].y

    return dist < 0.05 and middle_open and ring_open and pinky_open


def _count_fingers(landmarks):
    """펴진 손가락 개수 반환 (1~5)"""
    count = 0

    # 엄지는 x축으로 판단 (좌우 방향이라 y축 기준 불가)
    if landmarks[4].x < landmarks[3].x:
        count += 1

    # 나머지 4손가락은 y축으로 판단 (tip이 pip보다 위에 있으면 펴진 것)
    finger_tips = [8, 12, 16, 20]   # 검지, 중지, 약지, 소지 끝
    finger_pips = [6, 10, 14, 18]   # 검지, 중지, 약지, 소지 중간 관절

    for tip, pip in zip(finger_tips, finger_pips):
        if landmarks[tip].y < landmarks[pip].y:
            count += 1

    return count