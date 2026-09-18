import { useEffect, useRef, useCallback } from 'react'

const WS_PATH = '/ws/approach'
const FRAME_INTERVAL_MS = 500   // 0.5초에 1프레임 (2fps)
const JPEG_QUALITY = 0.6        // 감지용이므로 화질보다 속도 우선
const CAM_W = 320               // 낮은 해상도로 전송 크기 절감
const CAM_H = 240

/**
 * 흰 지팡이 / 휠체어 접근 감지 훅.
 *
 * 카메라 프레임을 0.5초마다 서버로 전송하고, 흰 지팡이나 휠체어가 감지되면
 * TTS 오디오를 재생하고 콜백을 호출한다. 감지 대상에 따라 프론트가 켜야 할
 * 입력 모드가 다르다 (docs/AI 질의.md 설계: 흰 지팡이 → 음성, 휠체어 → 제스처).
 *
 * @param {object} options
 * @param {boolean} options.enabled          - 감지 활성화 여부
 * @param {function} options.onModeAction    - 새 감지로 모드 활성화 시 호출 ('voice' | 'gesture')
 * @param {function} options.onModeEnd       - 3회 안내 완료 또는 사용자 입력 후 호출
 * @param {function} options.onStateChange   - 매 프레임 결과 수신 시 호출 ({ mode_on, active_trigger, announcement_count, ... })
 */
export function useApproachDetector({
  enabled = true,
  onModeAction,
  onModeEnd,
  onStateChange,
} = {}) {
  const wsRef        = useRef(null)
  const videoRef     = useRef(null)
  const canvasRef    = useRef(null)
  const timerRef     = useRef(null)
  const audioRef     = useRef(null)
  const prevModeRef  = useRef(false)

  const getWsUrl = useCallback(() => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const host  = window.location.host
    return `${proto}://${host}${WS_PATH}`
  }, [])

  const stopCamera = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    if (videoRef.current?.srcObject) {
      videoRef.current.srcObject.getTracks().forEach(t => t.stop())
      videoRef.current.srcObject = null
    }
  }, [])

  const sendFrame = useCallback(() => {
    const ws     = wsRef.current
    const video  = videoRef.current
    const canvas = canvasRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    if (!video || video.readyState < 2) return

    canvas.width  = CAM_W
    canvas.height = CAM_H
    const ctx = canvas.getContext('2d')
    ctx.drawImage(video, 0, 0, CAM_W, CAM_H)

    canvas.toBlob(blob => {
      if (!blob) return
      blob.arrayBuffer().then(buf => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          wsRef.current.send(buf)
        }
      })
    }, 'image/jpeg', JPEG_QUALITY)
  }, [])

  const playAudio = useCallback((bytes) => {
    const blob = new Blob([bytes], { type: 'audio/mpeg' })
    const url  = URL.createObjectURL(blob)
    if (audioRef.current) {
      audioRef.current.pause()
      URL.revokeObjectURL(audioRef.current.src)
    }
    const audio = new Audio(url)
    audioRef.current = audio
    audio.play().catch(() => {})
    audio.onended = () => URL.revokeObjectURL(url)
  }, [])

  // 사용자 입력(터치/클릭) 시 음성 안내 모드 종료 신호 전송
  const notifyUserInput = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'user_input' }))
    }
  }, [])

  useEffect(() => {
    if (!enabled) {
      stopCamera()
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      return
    }

    // 카메라 초기화
    videoRef.current  = document.createElement('video')
    canvasRef.current = document.createElement('canvas')
    videoRef.current.playsInline = true
    videoRef.current.muted = true

    navigator.mediaDevices
      .getUserMedia({ video: { width: CAM_W, height: CAM_H, facingMode: 'user' } })
      .then(stream => {
        videoRef.current.srcObject = stream
        return videoRef.current.play()
      })
      .catch(err => console.warn('[ApproachDetector] 카메라 접근 실패:', err))

    // WebSocket 연결
    const ws = new WebSocket(getWsUrl())
    ws.binaryType = 'arraybuffer'
    wsRef.current = ws

    ws.onopen = () => {
      timerRef.current = setInterval(sendFrame, FRAME_INTERVAL_MS)
    }

    ws.onmessage = (e) => {
      // binary: TTS 오디오
      if (e.data instanceof ArrayBuffer) {
        playAudio(e.data)
        return
      }

      let data
      try { data = JSON.parse(e.data) } catch { return }

      if (data.error) {
        console.warn('[ApproachDetector] 서버 오류:', data.error)
        return
      }

      // 새 감지로 모드 활성화 알림 — mode_action('voice'|'gesture')과 함께 전달
      if (data.mode_on && !prevModeRef.current) {
        onModeAction?.(data.mode_action)
      }

      // 모드 종료 알림
      if (data.mode_ended) {
        onModeEnd?.()
      }

      prevModeRef.current = data.mode_on
      onStateChange?.({
        mode_on:              data.mode_on,
        active_trigger:       data.active_trigger,
        mode_action:          data.mode_action,
        announcement_count:   data.announcement_count,
        white_cane_detected:  data.white_cane_detected,
        wheelchair_detected:  data.wheelchair_detected,
      })
    }

    ws.onclose = () => {
      clearInterval(timerRef.current)
      timerRef.current = null
    }

    return () => {
      stopCamera()
      ws.close()
      wsRef.current = null
    }
  }, [enabled, getWsUrl, sendFrame, playAudio, onModeAction, onModeEnd, onStateChange, stopCamera])

  return { notifyUserInput }
}
