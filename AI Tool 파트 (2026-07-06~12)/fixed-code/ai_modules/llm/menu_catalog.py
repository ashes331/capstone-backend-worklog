"""
메뉴 카탈로그 — ⚠️ 역할 축소됨

- LLM Tool의 모든 메뉴 조회 및 조작은 이제 DB API(api_client.py)를 통해 수행됩니다.
- MENU_CATALOG, get_menu() 등은 레거시이므로 action_tools.py에서 더 이상 import하지 마십시오.
- 단, 아래의 render_vocab_for_stt() 함수는 Whisper STT의 고유 오디오 어휘 힌트(Prompt)용으로 사용되므로 보존합니다.
"""
from __future__ import annotations

# Whisper STT 힌트 제공을 위한 임시 목록 (지우지 마세요)
_VOCAB_ITEMS = [
    "F버거", "불고기버거", "더블불고기버거", "새우버거", "치즈버거", 
    "치킨다릿살버거", "치킨가슴살버거", "데리버거", "게살버거", "비건버거", 
    "모짜렐라버거", "그릴드비프버거", "감자튀김", "치즈스틱", "치킨너겟", 
    "양념감자튀김", "코카콜라", "코카콜라제로", "사이다", "사이다제로", 
    "생수", "오렌지주스", "뽀로로음료수", "콜라", "제로콜라", "제로사이다", "뽀로로음료"
]

def render_vocab_for_stt() -> str:
    """
    Whisper `prompt`로 전달할 메뉴 어휘 힌트 문자열.
    고유 메뉴명과 세트 옵션명을 Whisper에 미리 흘려서 "F버거"를 "에프버거" 등으로 잘못 인식하는 것을 방지합니다.
    """
    menu_str = ", ".join(_VOCAB_ITEMS)
    return f"햄버거 키오스크 주문. 세트, 단품, 결제. 메뉴: {menu_str}."

# 백엔드 모듈(stt_service.py 등)과의 하위 호환성을 유지하기 위한 레거시 스텁 변수
MENU_CATALOG: list = []
SET_DRINKS: list = []
SET_SIDES: list = []

def render_catalog_for_prompt() -> str:
    """agent.py 등 레거시 프롬프트 템플릿 포맷팅 대응을 위한 스텁 함수"""
    return ""