import { useState, useCallback, useRef, useEffect, useMemo } from 'react'
import { useGesture } from './hooks/useGesture'
import { LocaleProvider, useLocale } from './i18n/LocaleContext'
import * as cartService from './services/cartService'
import CollectTool from './tools/CollectTool'
import StartScreen from './screens/StartScreen'
import OrderTypeScreen from './screens/OrderTypeScreen'
import MenuScreen from './screens/MenuScreen'
import CartScreen from './screens/CartScreen'
import PaymentScreen from './screens/PaymentScreen'
import CompletionScreen from './screens/CompletionScreen'
import CardPaymentScreen from './screens/CardPaymentScreen'
import PayPaymentScreen from './screens/PayPaymentScreen'
import CashPaymentScreen from './screens/CashPaymentScreen'
import ChatPanel from './components/ChatPanel'
import { useMenuData } from './hooks/useMenuData'
import { useApproachDetector } from './hooks/useApproachDetector'

// 제스처 키 → 표시 문자열 (컴포넌트 외부 상수)
const GESTURE_LABELS = {
  swipe_right: '→ 다음',
  swipe_left:  '← 이전',
  swipe_up:    '↑ 위로',
  swipe_down:  '↓ 아래로',
  ok:          '✓ 확인',
  finger_1:    '☝ 1',
  finger_2:    '✌ 2',
  finger_3:    '3',
  finger_4:    '4',
  finger_5:    '✋ 5',
}

const _isCollect = new URLSearchParams(window.location.search).has('collect')

// orderType 화면 진입 직후, 직전 화면의 OK 핀치 해제 과도기 동작을 매장/포장 선택으로
// 오인식하지 않도록 무시하는 유예 구간(ms)
const ORDER_TYPE_GESTURE_GRACE_MS = 900

// 접근성 컨트롤 바(음성인식/제스처/카메라) 고정 높이
const CONTROL_BAR_HEIGHT = 58

// 메뉴 원본(options 포함)에서 특정 그룹의 옵션을 이름으로 찾는다.
// name이 없으면(SET_UPGRADE처럼 단일 옵션인 경우) 그룹만으로 찾는다.
function findOption(menu, group, name) {
  return menu?.options?.find(o => o.option_group === group && (name == null || o.name_ko === name))
}

// 백엔드 CartItemOut → 화면(CartItem 등)이 기대하는 로컬 카트 항목 형태로 역매핑.
function adaptCartItem(ci, menuById) {
  const menu = menuById[ci.menu_item_id]
  const opts = ci.selected_options || []
  const matchGroup = (group) => {
    for (const sel of opts) {
      const opt = menu?.options?.find(o => o.id === sel.option_id)
      if (opt && opt.option_group === group) return opt
    }
    return null
  }
  const isSet    = !!matchGroup('SET_UPGRADE')
  const exclOpt  = matchGroup('EXCLUDE')
  const sideOpt  = matchGroup('SET_SIDE')
  const drinkOpt = matchGroup('SET_DRINK')
  return {
    cartId: ci.cart_item_id,
    id: ci.menu_item_id,
    categoryId: menu?.categoryId ?? null,
    name: menu?.name ?? ci.name_ko,
    image: isSet ? (menu?.setImage ?? menu?.image) : menu?.image,
    type: isSet ? 'set' : 'single',
    qty: ci.quantity,
    unitPrice: Number(ci.original_price ?? ci.unit_price),
    originalPrice: Number(ci.original_price ?? ci.unit_price),
    finalPrice: Number(ci.final_price ?? ci.unit_price),
    discountAmount: Number(ci.discount_amount ?? 0),
    appliedDiscounts: ci.applied_discounts ?? [],
    exclusion: exclOpt?.name_ko ?? '없음',
    side: sideOpt?.name_ko ?? null,
    sideExtra: Number(sideOpt?.additional_price ?? 0),
    drink: drinkOpt?.name_ko ?? null,
    drinkExtra: Number(drinkOpt?.additional_price ?? 0),
    special_note: ci.special_note,
    key: ci.cart_item_id,
  }
}

// LocaleProvider 바깥에서는 useLocale() 호출 불가 → AppContent로 분리
function AppContent() {
  const { setLocale } = useLocale()
  // UI에서 쓰는 메뉴 데이터와 동일한 소스 — API 연동 시에도 자동 반영
  const { menuData, isLoading: isMenuLoading, error: menuError, retry: retryMenu } = useMenuData()
  const activeDiscounts = menuData?.activeDiscounts ?? []
  const [screen,    setScreen]    = useState('start')
  const [cart,      setCart]      = useState([])
  const [orderType, setOrderType] = useState(null)
  const [orderNum,  setOrderNum]  = useState(null)
  const [chatOpen,  setChatOpen]  = useState(false)
  const [voiceToast, setVoiceToast] = useState(null)   // AI 동작 알림
  const voiceToastTimer = useRef(null)

  // 손동작 인식 On/Off & PiP 표시 (localStorage 영구 저장)
  const [gestureEnabled, setGestureEnabled] = useState(() => {
    const v = localStorage.getItem('gestureEnabled')
    return v === null ? true : v === 'true'
  })
  const [pipEnabled, setPipEnabled] = useState(() => {
    return localStorage.getItem('pipEnabled') === 'true'
  })
  useEffect(() => { localStorage.setItem('gestureEnabled', String(gestureEnabled)) }, [gestureEnabled])
  useEffect(() => { localStorage.setItem('pipEnabled',     String(pipEnabled))     }, [pipEnabled])

  // 취약계층 자동 감지 (Issue #66): 카메라로 휠체어 감지 시 제스처 인식 모드 자동 ON.
  // 흰 지팡이 감지(mode_action==='voice')는 별도 이슈(#49) 범위라 여기서는 처리하지 않음
  // — 서버는 안내 음성만 재생하고 프론트 모드 전환은 아직 없음.
  // 콜백은 반드시 안정적인 참조여야 함 — 훅의 useEffect 의존성이라, 매 렌더 새 함수를 넘기면
  // (App은 제스처 HUD로 자주 리렌더) 카메라/WebSocket이 계속 끊겼다 재연결됨.
  const handleApproachModeAction = useCallback((action) => {
    if (action === 'gesture') setGestureEnabled(true)
  }, [])
  const { notifyUserInput } = useApproachDetector({
    enabled: true,
    onModeAction: handleApproachModeAction,
  })
  // 화면을 만지거나 제스처 OK로 클릭하면 진행 중인 안내를 끝낸다 (서버는 안내 중일 때만 반응)
  useEffect(() => {
    window.addEventListener('pointerdown', notifyUserInput, true)
    window.addEventListener('click', notifyUserInput, true)
    return () => {
      window.removeEventListener('pointerdown', notifyUserInput, true)
      window.removeEventListener('click', notifyUserInput, true)
    }
  }, [notifyUserInput])

  // PiP 캔버스 — useGesture가 매 프레임 카메라 영상 + 관절을 직접 그림
  const pipCanvasRef = useRef(null)

  // 포인터 — DOM 직접 조작으로 React 리렌더 없이 30fps 업데이트
  const pointerRef    = useRef(null)   // 최신 위치 { x, y }
  const pointerDivRef = useRef(null)   // 커서 DOM 노드

  // OK 로딩 링 — DOM 직접 조작
  const okRingRef = useRef(null)
  const okRafRef  = useRef(null)

  // 엣지 존 — DOM 직접 조작
  const EDGE_MARGIN    = 0.10   // 화면 크기의 10%
  const EDGE_MAX_SPEED = 500    // px/s (최대 강도일 때)
  const edgeTopRef    = useRef(null)
  const edgeBottomRef = useRef(null)
  const edgeLeftRef   = useRef(null)
  const edgeRightRef  = useRef(null)
  const edgeStateRef  = useRef({ left: 0, right: 0, top: 0, bottom: 0 })
  const edgeRafRef    = useRef(null)
  const edgeLastTRef  = useRef(null)

  // MenuScreen 스와이프 / 모달 imperative 핸들러
  const menuSwipeRef = useRef(null)
  const menuModalRef = useRef(null)

  // 음성 화면 제어: 현재 화면이 등록하는 액션 핸들러 + 대기 액션 큐
  const screenVoiceRef    = useRef(null)
  const pendingActionsRef = useRef([])
  const awaitingScreenRef = useRef(false)   // navigate 후 새 화면 마운트 대기 중 여부
  const drainTimerRef     = useRef(null)     // 화면 마운트 지연 시 재드레인 폴백 타이머
  // 현재 열린 메뉴 팝업 상태 — LLM이 선택 내용을 읽고 수정하는 데 사용
  const modalStateRef     = useRef(null)

  // 음성 액션 핸들러가 항상 최신 데이터를 읽도록 ref로 유지
  // (speechEndHandlerRef의 stale closure를 우회하는 유일한 안전한 방법)
  const appCartRef    = useRef(cart)
  const menuDataRef   = useRef(menuData)
  const menuByIdRef   = useRef({})
  appCartRef.current  = cart
  menuDataRef.current = menuData

  // 현재 화면을 ref로 유지 — handleGesture 콜백 재생성 없이 참조
  const screenRef = useRef(screen)
  // 화면 진입 시각 — 전환 직후 잔여 손동작(직전 화면의 OK 핀치를 풀며 손을 펴는 과도기 동작)이
  // finger_1/finger_2로 오인식되어 매장/포장이 자동 선택되는 것을 막기 위한 유예 구간 기준점
  const screenEnteredAtRef = useRef(performance.now())
  useEffect(() => {
    screenRef.current = screen
    screenEnteredAtRef.current = performance.now()
  }, [screen])

  // 화면별 제스처 액션 — 렌더마다 최신 클로저를 갱신
  const gestureActionsRef = useRef({})
  gestureActionsRef.current = {
    orderType: {
      dineIn:  () => { setOrderType('dine-in'); setScreen('menu') },
      takeout: () => { setOrderType('takeout');  setScreen('menu') },
    },
  }

  // 감지된 제스처 표시용 (일시적 알림)
  const [gestureLabel, setGestureLabel] = useState(null)
  const labelTimerRef = useRef(null)

  const showLabel = useCallback((text) => {
    setGestureLabel(text)
    clearTimeout(labelTimerRef.current)
    labelTimerRef.current = setTimeout(() => setGestureLabel(null), 1200)
  }, [])

  // ── 포인터 민감도 ────────────────────────────────────────────────────────
  // 앵커 기반 매핑을 useGesture 에서 처리하므로 1.0 고정.
  // 이동 범위는 useGesture.js 의 ANCHOR_WINDOW_HALF 로 조절.
  const POINTER_SENS_X = 1.0
  const POINTER_SENS_Y = 1.0

  // 정규화 좌표(MediaPipe 0~1, 좌우 반전 전) → 화면 픽셀로 변환
  const normToScreen = useCallback(({ x, y }) => {
    const nx = (1 - x) - 0.5   // 좌우 반전 후 중심 기준
    const ny = y - 0.5
    return {
      x: (0.5 + nx * POINTER_SENS_X) * window.innerWidth,
      y: (0.5 + ny * POINTER_SENS_Y) * window.innerHeight,
    }
  }, [])

  // 제스처 활동 → idle 타이머 리셋용 커스텀 이벤트 (2초 스로틀)
  const lastActivityRef = useRef(0)
  const dispatchActivity = useCallback(() => {
    const now = Date.now()
    if (now - lastActivityRef.current > 2000) {
      lastActivityRef.current = now
      window.dispatchEvent(new Event('gesture-activity'))
    }
  }, [])

  // 엣지 인디케이터 opacity 초기화
  const clearEdge = useCallback(() => {
    edgeStateRef.current = { left: 0, right: 0, top: 0, bottom: 0 }
    if (edgeTopRef.current)    edgeTopRef.current.style.opacity    = 0
    if (edgeBottomRef.current) edgeBottomRef.current.style.opacity = 0
    if (edgeLeftRef.current)   edgeLeftRef.current.style.opacity   = 0
    if (edgeRightRef.current)  edgeRightRef.current.style.opacity  = 0
  }, [])

  // 포인터: useGesture 의 onPointer 콜백 — React state 없이 DOM 직접 업데이트
  const handlePointer = useCallback((norm) => {
    if (!norm) {
      pointerRef.current = null
      // opacity 만 끄기 — DOM은 유지해서 재등장 시 위치가 부드럽게 트랜지션됨
      if (pointerDivRef.current) pointerDivRef.current.style.opacity = '0'
      clearEdge()
      return
    }
    const p = normToScreen(norm)
    pointerRef.current = p
    const d = pointerDivRef.current
    if (d) {
      d.style.left    = `${p.x - 14}px`
      d.style.top     = `${p.y - 14}px`
      d.style.opacity = '1'
    }

    // ── 엣지 존 감지 ──────────────────────────────────────────────────────
    const nx = p.x / window.innerWidth
    const ny = p.y / window.innerHeight
    // 강도: 존 경계에서 0, 화면 끝에서 1
    const eL = Math.max(0, (EDGE_MARGIN - nx)       / EDGE_MARGIN)
    const eR = Math.max(0, (EDGE_MARGIN - (1 - nx)) / EDGE_MARGIN)
    const eT = Math.max(0, (EDGE_MARGIN - ny)       / EDGE_MARGIN)
    const eB = Math.max(0, (EDGE_MARGIN - (1 - ny)) / EDGE_MARGIN)

    if (edgeTopRef.current)    edgeTopRef.current.style.opacity    = eT
    if (edgeBottomRef.current) edgeBottomRef.current.style.opacity = eB
    if (edgeLeftRef.current)   edgeLeftRef.current.style.opacity   = eL
    if (edgeRightRef.current)  edgeRightRef.current.style.opacity  = eR

    edgeStateRef.current = { left: eL, right: eR, top: eT, bottom: eB }

    // 엣지 자동 스크롤 루프 — 이미 실행 중이면 재시작 안 함
    if ((eL + eR + eT + eB) > 0 && !edgeRafRef.current) {
      edgeLastTRef.current = null
      const tick = (t) => {
        const cur = pointerRef.current
        if (!cur) { edgeRafRef.current = null; return }
        const e = edgeStateRef.current
        if (e.left + e.right + e.top + e.bottom === 0) { edgeRafRef.current = null; return }

        const dt = edgeLastTRef.current !== null ? (t - edgeLastTRef.current) / 1000 : 0
        edgeLastTRef.current = t

        if (dt > 0) {
          const dx = (e.right - e.left) * EDGE_MAX_SPEED * dt
          const dy = (e.bottom - e.top) * EDGE_MAX_SPEED * dt
          // 커서 위치 아래의 스크롤 가능한 요소 탐색
          let el = document.elementFromPoint(cur.x, cur.y)
          let scrolled = false
          while (el && el !== document.documentElement) {
            const cs   = window.getComputedStyle(el)
            const canY = (cs.overflowY === 'auto' || cs.overflowY === 'scroll') && el.scrollHeight > el.clientHeight
            const canX = (cs.overflowX === 'auto' || cs.overflowX === 'scroll') && el.scrollWidth  > el.clientWidth
            if (canY || canX) {
              if (canY) el.scrollTop  += dy
              if (canX) el.scrollLeft += dx
              scrolled = true
              break
            }
            el = el.parentElement
          }
          if (!scrolled) window.scrollBy(0, dy)
        }

        edgeRafRef.current = requestAnimationFrame(tick)
      }
      edgeRafRef.current = requestAnimationFrame(tick)
    }

    dispatchActivity()
  }, [normToScreen, dispatchActivity, clearEdge])

  // OK 이동 취소 임계값 (screen px) — 이 이상 움직이면 링 취소
  const OK_MOVE_THRESHOLD = 80

  // OK: 손을 충분히 안 움직이면 0.5초 후 클릭 — DOM 직접 조작으로 rAF 리렌더 없음
  const fireOk = useCallback(() => {
    if (okRafRef.current !== null) return

    const p = pointerRef.current
    if (!p) return

    const startX   = p.x
    const startY   = p.y
    const start    = performance.now()
    const DURATION = 500
    const ring     = okRingRef.current

    if (ring) {
      ring.style.display    = 'block'
      ring.style.left       = `${startX - 28}px`
      ring.style.top        = `${startY - 28}px`
      ring.style.background = `conic-gradient(rgba(80,210,255,0.95) 0deg, rgba(255,255,255,0.18) 0deg)`
    }

    const tick = (now) => {
      const cur = pointerRef.current
      if (!cur || Math.hypot(cur.x - startX, cur.y - startY) > OK_MOVE_THRESHOLD) {
        okRafRef.current = null
        if (ring) ring.style.display = 'none'
        return
      }

      const progress = Math.min((now - start) / DURATION, 1)
      if (ring) ring.style.background =
        `conic-gradient(rgba(80,210,255,0.95) ${progress * 360}deg, rgba(255,255,255,0.18) 0deg)`

      if (progress < 1) {
        okRafRef.current = requestAnimationFrame(tick)
      } else {
        okRafRef.current = null
        if (ring) ring.style.display = 'none'
        const el = document.elementFromPoint(startX, startY)
        if (el) el.click()
      }
    }
    okRafRef.current = requestAnimationFrame(tick)
  }, [])

  // 포인터 위치의 가장 가까운 스크롤 가능 요소를 스크롤
  const scrollAtPointer = useCallback((dy) => {
    const p = pointerRef.current
    let el = p ? document.elementFromPoint(p.x, p.y) : null
    while (el && el !== document.documentElement) {
      const { overflowY } = window.getComputedStyle(el)
      if ((overflowY === 'auto' || overflowY === 'scroll') && el.scrollHeight > el.clientHeight) {
        el.scrollBy({ top: dy, behavior: 'smooth' })
        return
      }
      el = el.parentElement
    }
    window.scrollBy({ top: dy, behavior: 'smooth' })
  }, [])

  // 테스트용 HUD 상태
  const [gestureHud, setGestureHud] = useState(null)

  const handleGesture = useCallback(({ gesture, hands, total_fingers }) => {
    // HUD 업데이트 (포인터는 onPointer 가 처리, 제스처는 showLabel 이 갱신)
    setGestureHud({
      left:  hands?.left  ? `${hands.left.finger_count}개`  : '-',
      right: hands?.right ? `${hands.right.finger_count}개` : '-',
      total: total_fingers ?? 0,
    })

    if (!gesture) return

    const currentScreen = screenRef.current

    // ── 랜딩 페이지: 커서 + OK만 ─────────────────────
    if (currentScreen === 'start') {
      if (gesture === 'ok') { fireOk(); showLabel(GESTURE_LABELS.ok) }
      return
    }

    // ── 식사 장소 선택: OK(포인터 클릭) + 1(매장) + 2(포장) ──
    if (currentScreen === 'orderType') {
      const { dineIn, takeout } = gestureActionsRef.current.orderType
      const activeHand  = hands?.right || hands?.left
      const fingerCount = activeHand?.finger_count ?? -1
      // 화면 진입 직후 짧은 유예 구간 — 직전 화면(start)의 OK 핀치를 풀며 손을 펴는 동작이
      // finger_1/finger_2로 오인식되어 매장/포장이 사용자 의도 없이 자동 선택되는 것을 방지
      const settled = performance.now() - screenEnteredAtRef.current >= ORDER_TYPE_GESTURE_GRACE_MS
      if      (gesture === 'ok')                                        { fireOk(); showLabel(GESTURE_LABELS.ok) }
      else if (settled && gesture === 'finger_1' && fingerCount <= 1)  { dineIn();  showLabel('☝ 매장') }
      else if (settled && gesture === 'finger_2' && fingerCount >= 2)  { takeout(); showLabel('✌ 포장') }
      return
    }

    // ── 나머지 모든 페이지 ────────────────────────────
    if (gesture === 'ok') {
      fireOk()
      showLabel(GESTURE_LABELS.ok)
      return
    }

    if (gesture === 'swipe_up') {
      scrollAtPointer(-260)
      showLabel(GESTURE_LABELS.swipe_up)
      return
    }

    if (gesture === 'swipe_down') {
      scrollAtPointer(260)
      showLabel(GESTURE_LABELS.swipe_down)
      return
    }

    // 메뉴 화면 모달 제스처 (단품/세트 선택) — 스와이프/스크롤보다 먼저 처리
    if (currentScreen === 'menu' && menuModalRef.current) {
      if (gesture === 'finger_1') { menuModalRef.current('single'); showLabel('☝ 단품'); return }
      if (gesture === 'finger_2') { menuModalRef.current('set');    showLabel('✌ 세트');  return }
    }

    // 메뉴 화면 좌우 스와이프 → 페이지/탭 전환
    if (currentScreen === 'menu' && (gesture === 'swipe_left' || gesture === 'swipe_right')) {
      menuSwipeRef.current?.(gesture === 'swipe_right' ? 'left' : 'right')
      showLabel(GESTURE_LABELS[gesture])
      return
    }

    if (gesture.startsWith('swipe_')) showLabel(GESTURE_LABELS[gesture])
  }, [showLabel, fireOk, scrollAtPointer])

  useGesture({
    onPointer:    handlePointer,
    onGesture:    handleGesture,
    enabled:      gestureEnabled,
    pipCanvasRef: gestureEnabled && pipEnabled ? pipCanvasRef : null,
  })

  // 손동작 OFF: 잔여 포인터/OK 링 UI 즉시 숨김
  useEffect(() => {
    if (gestureEnabled) return
    pointerRef.current = null
    if (pointerDivRef.current) pointerDivRef.current.style.opacity = '0'
    if (okRingRef.current)     okRingRef.current.style.display     = 'none'
    if (okRafRef.current) { cancelAnimationFrame(okRafRef.current); okRafRef.current = null }
    if (edgeRafRef.current) { cancelAnimationFrame(edgeRafRef.current); edgeRafRef.current = null }
    edgeStateRef.current = { left: 0, right: 0, top: 0, bottom: 0 }
  }, [gestureEnabled])


  const nav = (s) => {
    if (s === 'start') {
      // 새 손님 시작 — 채팅 닫기, 언어·세션 초기화
      setChatOpen(false)
      setLocale('ko')
      sessionStorage.removeItem('kiosk_detected_lang')
      // 세션 ID 재발급은 ChatPanel의 kiosk-session-reset 핸들러(newSessionId())가 전담
      // (카트 API도 동일 session.js를 통해 이 새 세션을 바라보게 됨 — 경쟁 상태 방지)
      window.dispatchEvent(new CustomEvent('kiosk-session-reset'))
    }
    setScreen(s)
  }

  // 백엔드 카트(session_id 기준)가 단일 소스 — 서버에서 다시 받아와 로컬 state에 반영한다.
  const refreshCart = useCallback(async () => {
    try {
      const data = await cartService.fetchCart()
      setCart(data.items.map(ci => adaptCartItem(ci, menuByIdRef.current)))
    } catch (e) {
      console.error('[cart] refresh 실패:', e)
      showVoiceToast('오류: 장바구니를 불러오지 못했습니다')
    }
  }, [])  // eslint-disable-line react-hooks/exhaustive-deps

  // draft: ItemDetailModal 이 onAdd 로 넘기는 형태 { id, type, qty, exclusion, side, drink, special_note? }
  const addToCart = async (draft) => {
    const menu = menuByIdRef.current[draft.id]
    if (!menu) { console.warn('[cart] 알 수 없는 메뉴:', draft.id); return }

    const selected_options = []
    if (draft.type === 'set') {
      const su = findOption(menu, 'SET_UPGRADE')
      if (su) selected_options.push({ option_id: su.id, name: su.name_ko })
      if (draft.side)  { const s = findOption(menu, 'SET_SIDE',  draft.side);  if (s) selected_options.push({ option_id: s.id, name: s.name_ko }) }
      if (draft.drink) { const d = findOption(menu, 'SET_DRINK', draft.drink); if (d) selected_options.push({ option_id: d.id, name: d.name_ko }) }
    }
    if (draft.exclusion && draft.exclusion !== '없음') {
      const ex = findOption(menu, 'EXCLUDE', draft.exclusion)
      if (ex) selected_options.push({ option_id: ex.id, name: ex.name_ko })
    }

    try {
      await cartService.addCartItem({
        menu_item_id: draft.id,
        quantity: draft.qty ?? 1,
        selected_options,
        special_note: draft.special_note ?? null,
      })
      await refreshCart()
    } catch (e) {
      console.error('[cart] 담기 실패:', e)
      showVoiceToast(`오류: ${e.message || '장바구니 담기에 실패했습니다'}`)
    }
  }

  // 낙관적 업데이트(즉각 반응) 후 서버에 반영, 실패하면 refreshCart로 서버 진실을 되돌림
  const updateQty = async (cartId, qty) => {
    setCart(prev => qty <= 0 ? prev.filter(c => c.cartId !== cartId)
                              : prev.map(c => c.cartId === cartId ? { ...c, qty } : c))
    try {
      if (qty <= 0) await cartService.removeCartItem(cartId)
      else          await cartService.updateCartItem(cartId, { quantity: qty })
    } catch (e) {
      console.error('[cart] 수량 변경 실패:', e)
      showVoiceToast(`오류: ${e.message || '수량 변경에 실패했습니다'}`)
      await refreshCart()
    }
  }

  const clearCart = async () => {
    setCart([])
    try {
      await cartService.clearCartApi()
    } catch (e) {
      console.error('[cart] 초기화 실패:', e)
    }
  }

  // ── 음성 주문: LLM 친화 장바구니 변환 ────────────────────────────────────
  const cartForLLM = useMemo(() =>
    cart.map(c => ({
      cart_id:   c.cartId,
      menu_id:   c.id,
      name:      c.name,
      item_type: c.type,
      quantity:  c.qty,
      unit_price: c.unitPrice,
      exclusion: c.exclusion,
      side:      c.side,
      drink:     c.drink,
    }))
  , [cart])

  // UI와 동일한 menuData 소스로 id → item 맵 구성
  const _menuById = useMemo(() => {
    if (!menuData?.menuItems) return {}
    const map = {}
    Object.values(menuData.menuItems).forEach(list => list.forEach(m => { map[m.id] = m }))
    return map
  }, [menuData])
  menuByIdRef.current = _menuById   // 항상 최신 맵을 ref에 반영

  // 메뉴 데이터가 준비되면(옵션 조회를 위해 필요) 서버 카트를 1회 복원한다.
  // — 새로고침/재방문 시에도 기존에 담아둔(또는 음성으로 담긴) 항목이 그대로 보이게 함.
  const cartRestoredRef = useRef(false)
  useEffect(() => {
    if (menuData && !cartRestoredRef.current) {
      cartRestoredRef.current = true
      refreshCart()
    }
  }, [menuData, refreshCart])

  // App 레벨에서 처리 가능한 액션 실행.
  // 반환: 'nav'(화면 전환 발생) | 'handled'(처리됨) | 'no'(App 레벨 아님 → 화면 브릿지로)
  function execAppAction(a) {
    switch (a.type) {
      case 'add_item': {
        // 백엔드 카트는 LLM 툴 실행 시점에 이미 반영을 끝냈다 — 로컬에서 재구성하지 않고
        // 메뉴 화면이 마운트되어 있으면 시각적 확인(모달 워크스루)만 띄운 뒤 refreshCart로 동기화.
        screenVoiceRef.current?.({...a, type: 'add_item'})
        refreshCart()
        return 'handled'
      }
      case 'update_qty':
        // 현재 어떤 LLM 툴도 이 액션 타입을 발생시키지 않음(터치 전용 함수) — 안전하게 무시
        return 'handled'
      case 'remove_item':
      case 'update_item':
      case 'clear_cart':
        // 백엔드가 이미 반영을 끝냈으므로 최신 카트만 다시 받아온다
        refreshCart()
        return 'handled'
      case 'navigate':
        nav(a.screen)
        return 'nav'
      case 'checkout':
        nav('cart')
        return 'nav'
      case 'order_type':
        setOrderType(a.value === 'takeout' ? 'takeout' : 'dine-in')
        nav('menu')
        return 'nav'
      case 'set_language':
        if (a.value) setLocale(a.value)
        return 'handled'
      case 'set_gesture':
        setGestureEnabled(a.value === 'on')
        return 'handled'
      case 'set_camera':
        setPipEnabled(a.value === 'on')
        return 'handled'
      default:
        return 'no'   // 화면 종속 액션
    }
  }

  // 큐 드레인: App 레벨 → 화면 브릿지 순으로 처리.
  // 화면 전환(navigate) 직후 새 화면이 마운트되기 전 도착한 종속 액션은 버리지 않고
  // 큐에 유지했다가 마운트 후(또는 폴백 타이머) 재드레인한다.
  function drainVoiceActions() {
    const q = pendingActionsRef.current
    while (q.length) {
      const a = q[0]
      const res = execAppAction(a)
      if (res === 'nav') {
        q.shift()
        awaitingScreenRef.current = true   // 새 화면 마운트 대기 시작
        break
      }
      if (res === 'handled') { q.shift(); continue }
      // 화면 종속 액션 → 현재 화면 브릿지에 위임
      // screenVoiceRef.current가 null이면 화면이 아직 핸들러 등록 전 — 재시도
      if (!screenVoiceRef.current) {
        scheduleDrainRetry()
        break
      }
      const handled = screenVoiceRef.current(a)
      if (handled) { q.shift(); continue }
      // 처리 못 함: 화면 전환 대기 중이면 보존하고 잠시 후 재시도
      if (awaitingScreenRef.current) {
        scheduleDrainRetry()
        break
      }
      // 전환 대기도 아닌데 처리 불가 → 현재 화면과 무관한 액션, 무시
      console.warn('[voice] 현재 화면에서 처리할 수 없는 액션, 무시:', a)
      q.shift()
    }
  }

  // 화면 마운트가 늦어질 때 큐를 재드레인하는 폴백 (최대 ~1초)
  function scheduleDrainRetry(attempt = 0) {
    if (drainTimerRef.current) clearTimeout(drainTimerRef.current)
    if (attempt > 20) {   // 약 1초 후에도 처리 못 하면 포기(무한 보류 방지)
      awaitingScreenRef.current = false
      if (pendingActionsRef.current.length) {
        console.warn('[voice] 대기 액션 처리 실패, 폐기:', pendingActionsRef.current.splice(0))
      }
      return
    }
    drainTimerRef.current = setTimeout(() => {
      const before = pendingActionsRef.current.length
      drainVoiceActions()
      // 여전히 남아있고 아직 대기 중이면 다음 시도 예약
      if (pendingActionsRef.current.length && pendingActionsRef.current.length === before
          && awaitingScreenRef.current) {
        scheduleDrainRetry(attempt + 1)
      }
    }, 50)
  }

  // AI 액션 → 한국어 알림 메시지
  function actionToMsg(a) {
    const menuName = a.name || (appCartRef.current.find(c => c.id === a.menu_id)?.name) || `메뉴#${a.menu_id}`
    const catLabel = { recommended: '추천메뉴', burger: '버거', side: '사이드', drink: '음료수' }
    const screenLabel = { start: '시작', orderType: '주문유형', menu: '메뉴', cart: '장바구니', complete: '완료' }
    switch (a.type) {
      case 'add_item':        return `장바구니 추가: ${menuName} ${a.quantity || 1}개`
      case 'update_qty':      return `수량 변경: ${a.quantity}개`
      case 'remove_item':     return `삭제: ${menuName}`
      case 'update_item':     return `옵션 변경: ${menuName}`
      case 'clear_cart':      return '장바구니 전체 삭제'
      case 'navigate':        return `화면 이동: ${screenLabel[a.screen] || a.screen}`
      case 'checkout':        return '장바구니로 이동'
      case 'order_type':      return a.value === 'dine-in' ? '매장 식사 선택' : '포장 선택'
      case 'select_category': return `카테고리: ${catLabel[a.value] || a.value}`
      case 'menu_page':       return a.value === 'next' ? '다음 페이지' : '이전 페이지'
      case 'open_item':       return `메뉴 상세 열기`
      case 'update_modal':    return `팝업 수정: ${a.field} → ${a.value}`
      case 'start_checkout':  return '결제 시작'
      case 'points':          return a.value === 'yes' ? '포인트 적립' : '포인트 미적립'
      case 'points_phone':    return `전화번호: ${a.phone || ''}`
      case 'payment_method':  return `결제 수단: ${{ card:'카드', cash:'현금', pay:'간편결제' }[a.value] || a.value}`
      case 'set_language':    return `언어 변경: ${a.value}`
      case 'set_gesture':     return `손동작 ${a.value === 'on' ? 'ON' : 'OFF'}`
      case 'set_camera':      return `카메라 ${a.value === 'on' ? 'ON' : 'OFF'}`
      default:                return null
    }
  }

  function showVoiceToast(msg) {
    if (!msg) return
    clearTimeout(voiceToastTimer.current)
    setVoiceToast({ msg, key: Date.now() })
    voiceToastTimer.current = setTimeout(() => setVoiceToast(null), 2500)
  }

  // 음성 액션 디스패처 — 큐에 넣고 즉시 드레인 시도
  function handleVoiceAction(a) {
    showVoiceToast(actionToMsg(a))
    pendingActionsRef.current.push(a)
    drainVoiceActions()
  }

  // 화면 전환 후(자식 화면 브릿지 등록 effect가 먼저 실행됨) 남은 액션 이어서 처리
  useEffect(() => {
    awaitingScreenRef.current = false   // 새 화면 마운트 완료 → 대기 해제
    if (pendingActionsRef.current.length) drainVoiceActions()
  }, [screen])  // eslint-disable-line react-hooks/exhaustive-deps

  const total = cart.reduce((sum, c) => sum + (c.finalPrice ?? c.unitPrice) * c.qty, 0)
  const props = { cart, total, addToCart, updateQty, clearCart, nav, setOrderNum, orderType, setOrderType, chatOpen, menuData, activeDiscounts, isLoading: isMenuLoading, error: menuError, retry: retryMenu }

  const screens = {
    start:       <StartScreen {...props} />,
    orderType:   <OrderTypeScreen nav={nav} setOrderType={setOrderType} />,
    menu:        <MenuScreen {...props} swipeRef={menuSwipeRef} modalRef={menuModalRef} voiceRef={screenVoiceRef} modalStateRef={modalStateRef} />,
    cart:        <CartScreen {...props} voiceRef={screenVoiceRef} />,
    payment:     <PaymentScreen {...props} />,
    complete:    <CompletionScreen orderNum={orderNum} nav={nav} />,
    cardPayment: <CardPaymentScreen {...props} />,
    payPayment:  <PayPaymentScreen {...props} />,
    cashPayment: <CashPaymentScreen {...props} />,
  }

  return (
    <>
        {/* ── AI 동작 토스트 알림 ── */}
        {voiceToast && (
          <div key={voiceToast.key} style={{
            position: 'fixed',
            bottom: chatOpen ? 'calc(33vh + 72px)' : 80,
            left: '50%',
            transform: 'translateX(-50%)',
            background: 'rgba(116,64,50,0.92)',
            color: '#fff',
            padding: '10px 22px',
            borderRadius: 24,
            fontSize: 15,
            fontWeight: 600,
            pointerEvents: 'none',
            zIndex: 9050,
            whiteSpace: 'nowrap',
            boxShadow: '0 4px 16px rgba(0,0,0,0.3)',
          }}>
            AI: {voiceToast.msg}
          </div>
        )}

        {/* ── 테스트 HUD (좌측 하단) ── */}
        {gestureHud && (
          <div style={{
            position: 'fixed', bottom: 16, left: 16,
            background: 'rgba(0,0,0,0.75)', color: '#fff',
            padding: '10px 16px', borderRadius: 10,
            fontSize: 13, lineHeight: 1.8,
            fontFamily: 'monospace', pointerEvents: 'none', zIndex: 9002,
          }}>
            <div>왼손 &nbsp;: {gestureHud.left}</div>
            <div>오른손: {gestureHud.right}</div>
            <div>합계 &nbsp;: {gestureHud.total}개</div>
            <div style={{ color: gestureLabel ? '#7fff7f' : '#888' }}>
              제스처: {gestureLabel ?? '-'}
            </div>
          </div>
        )}

        {/* ── 제스처 포인터 — DOM 직접 조작, React 리렌더 없음 ── */}
        <div ref={pointerDivRef} style={{
          position: 'fixed',
          left: -100, top: -100,
          width: 28, height: 28,
          borderRadius: '50%',
          background: 'rgba(255, 80, 80, 0.55)',
          border: '2.5px solid rgba(255,255,255,0.85)',
          pointerEvents: 'none',
          zIndex: 9000,
          opacity: 0,
          // 등장/사라짐만 트랜지션 (위치는 이미 OneEuro로 스무딩됨)
          transition: 'opacity 0.18s ease-out',
          willChange: 'left, top, opacity',
        }} />

        {/* ── 카메라 PiP — 우측 상단 반투명 미리보기 (실제 인식 영역 + 관절) ── */}
        {gestureEnabled && pipEnabled && (
          <div style={{
            position: 'fixed',
            top: 16, right: 16,
            width: 200,
            borderRadius: 10,
            overflow: 'hidden',
            border: '1.5px solid rgba(255,255,255,0.45)',
            boxShadow: '0 4px 18px rgba(0,0,0,0.45)',
            opacity: 0.82,
            background: '#000',
            pointerEvents: 'none',
            zIndex: 9003,
          }}>
            {/* canvas 비율은 카메라 해상도에 따라 자동 — width:100% + height:auto 로 왜곡 없이 */}
            <canvas
              ref={pipCanvasRef}
              style={{ display: 'block', width: '100%', height: 'auto' }}
            />
          </div>
        )}

        {/* ── OK 로딩 링 — DOM 직접 조작 ── */}
        <div ref={okRingRef} style={{
          display: 'none',
          position: 'fixed',
          width: 56, height: 56,
          borderRadius: '50%',
          pointerEvents: 'none',
          zIndex: 9004,
        }}>
          <div style={{
            position: 'absolute', inset: 7,
            borderRadius: '50%',
            background: 'rgba(0,0,0,0.55)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'rgba(255,255,255,0.9)',
            fontSize: 14, fontWeight: 700,
          }}>✓</div>
        </div>

        {/* ── 제스처 라벨 알림 ── */}
        {gestureLabel && (
          <div style={{
            position: 'fixed',
            top: 24, left: '50%',
            transform: 'translateX(-50%)',
            background: 'rgba(0,0,0,0.72)',
            color: '#fff',
            padding: '8px 22px',
            borderRadius: 24,
            fontSize: 18,
            fontWeight: 600,
            pointerEvents: 'none',
            zIndex: 9001,
          }}>
            {gestureLabel}
          </div>
        )}

        {/* ── 메인 레이아웃 ── */}
        <div style={{
          display: 'flex', flexDirection: 'column',
          height: '100dvh', minHeight: '100vh',
          overflow: 'hidden',
          paddingBottom: CONTROL_BAR_HEIGHT,
        }}>
          {/* 화면 영역 — 채팅창이 열리면 자동으로 줄어듦 */}
          <div style={{ flex: 1, minHeight: 0, position: 'relative', overflow: 'hidden' }}>
            {screens[screen] ?? screens.start}
          </div>

          {/* 채팅 패널 — 항상 마운트(백그라운드 모델 프리로드), CSS로 열고 닫음 */}
          <div style={{
            flexShrink: 0,
            height: chatOpen ? '33vh' : 0,
            overflow: 'hidden',
            transition: 'height 0.35s ease',
            background: '#e0e0e0',
            borderTop: chatOpen ? '1.5px solid #bbb' : 'none',
          }}>
            <ChatPanel
              onClose={() => setChatOpen(false)}
              isOpen={chatOpen}
              cart={cartForLLM}
              screen={screen}
              orderType={orderType}
              modalStateRef={modalStateRef}
              onAction={handleVoiceAction}
            />
          </div>
        </div>

        {/* ── 접근성 컨트롤 바 — 음성인식/제스처/카메라 On-Off, 항상 화면 맨 아래 고정
             (음성인식 UI가 열려도 그 아래에 그대로 고정 — 위로 밀려 올라가지 않음) ── */}
        <div
          style={{
            position: 'fixed',
            bottom: 0,
            left: 0, right: 0,
            zIndex: 500,
            height: CONTROL_BAR_HEIGHT,
            boxSizing: 'border-box',
            background: '#000',
            color: '#fff',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 40,
            fontSize: 14,
          }}
        >
          <ControlText
            onClick={() => setChatOpen(o => !o)}
            ko={`음성인식 ${chatOpen ? 'ON' : 'OFF'}`}
            en={`Voice ${chatOpen ? 'ON' : 'OFF'}`}
          />
          <ControlText
            onClick={() => setGestureEnabled(v => !v)}
            ko={`제스처 ${gestureEnabled ? 'ON' : 'OFF'}`}
            en={`Gesture ${gestureEnabled ? 'ON' : 'OFF'}`}
          />
          <ControlText
            disabled={!gestureEnabled}
            onClick={() => gestureEnabled && setPipEnabled(v => !v)}
            ko={`카메라 ${pipEnabled && gestureEnabled ? 'ON' : 'OFF'}`}
            en={`Camera ${pipEnabled && gestureEnabled ? 'ON' : 'OFF'}`}
          />
        </div>
      </>
  )
}

// 접근성 컨트롤 바의 텍스트 버튼 — 한국어(위, 크게) + 영어(아래, 작게) 동시 표기
function ControlText({ onClick, disabled = false, ko, en }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        background: 'none',
        border: 'none',
        color: disabled ? 'rgba(255,255,255,0.4)' : '#fff',
        cursor: disabled ? 'not-allowed' : 'pointer',
        padding: '4px 0',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 2,
        lineHeight: 1.3,
      }}
    >
      <span style={{ fontSize: 15, fontWeight: 700 }}>{ko}</span>
      <span style={{ fontSize: 11, fontWeight: 400, opacity: 0.75 }}>{en}</span>
    </button>
  )
}

export default _isCollect ? CollectTool : function App() {
  return (
    <LocaleProvider>
      <AppContent />
    </LocaleProvider>
  )
}
