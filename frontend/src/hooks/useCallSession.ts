import { useCallback, useEffect, useRef, useState } from 'react';
import { Platform } from 'react-native';
import { categorizeType, extractKeywords } from '@/core/utils/keywords';
import { riskLevelFromScore, type RiskLevel } from '@/core/utils/riskLevel';
import type { AnalysisEvent, CallResult, TranscriptTurn } from '@/data/models/types';
import type { Scenario } from '@/data/mock/mockScenarios';
import { createSttService, type SttService } from '@/data/services/sttService';
import { createAudioCapture, type AudioCaptureService } from '@/data/services/audioCapture';
import { createAnalyzeConnection, type AnalyzeConnection } from '@/data/services/wsService';
import { useSettingsStore } from '@/state/settingsStore';

export interface CallSessionState {
  logId: number; // 백엔드가 발급한 통화 로그 id (call_started) — 0이면 아직 없음
  turns: TranscriptTurn[];
  score: number; // 현재 누적 위험도
  level: RiskLevel;
  matchedPatterns: string[];
  coreEvidence: string;
  elapsedSec: number;
  running: boolean;
  paused: boolean; // 분석 일시정지 상태 (오디오 캡처만 멈추고 WS 세션은 유지)
  finished: boolean;
  error: string | null; // 백엔드 연결/분석 오류 (실사용 시 표시)
}

/**
 * STT(목/실제) → WS(목/실제) 오케스트레이션.
 * 발화 인식마다 WS로 전송하고, 응답으로 위험도/근거/자막을 갱신한다.
 * 강한 경고 임계값을 처음 넘으면 onDangerCross 콜백을 1회 호출한다.
 */
export function useCallSession(
  scenario: Scenario,
  opts: { speed?: number; onDangerCross?: (s: CallSessionState) => void } = {},
) {
  const dangerThreshold = useSettingsStore((s) => s.dangerThreshold);
  const [state, setState] = useState<CallSessionState>({
    logId: 0,
    turns: [],
    score: 0,
    level: 'safe',
    matchedPatterns: [],
    coreEvidence: '',
    elapsedSec: 0,
    running: false,
    paused: false,
    finished: false,
    error: null,
  });

  // 최신 state를 참조로 보관 — 종료 시 grace 대기 후 "그 시점의 최종" turns/logId/score를 읽기 위함.
  const latestRef = useRef(state);
  latestRef.current = state;

  // 세션은 start() 시점에 1회 생성(실제 WS 소켓이 렌더마다 새로 열리는 것 방지)
  const connRef = useRef<AnalyzeConnection | null>(null);
  const sttRef = useRef<SttService | null>(null);
  const captureRef = useRef<AudioCaptureService | null>(null);
  const speed = opts.speed ?? 1;

  // 웹 라이브(대본 없는 실시간) 세션은 오디오 스트리밍 경로를 사용한다.
  // (마이크 → 16kHz WAV 3초 청크 → 백엔드 Whisper 전사·채점)
  // 데모 시나리오(turns 존재)나 네이티브는 기존 STT(텍스트) 경로 유지.
  const audioMode = Platform.OS === 'web' && scenario.turns.length === 0;
  const turnCounter = useRef(0);
  const maxScore = useRef(0);
  const warned = useRef(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const startedAt = useRef<number>(0);
  // 보낸 오디오 청크 수 vs 응답 받은 청크 수 — 종료 시 "전부 전사될 때까지" 대기용.
  const sentChunks = useRef(0);
  const recvChunks = useRef(0);
  const pausedAccumMs = useRef(0); // 일시정지 누적 시간(경과초 보정용)
  const pausedAtMs = useRef(0);
  const onDanger = useRef(opts.onDangerCross);
  onDanger.current = opts.onDangerCross;

  const handleEvent = useCallback(
    (e: AnalysisEvent) => {
      // 오디오 청크 하나당 응답 하나(ack/detected/chunk_ack/error). chunk_index가 있으면 응답 1건으로 집계.
      if ('chunk_index' in e && (e as { chunk_index?: number }).chunk_index != null) {
        recvChunks.current += 1;
      }
      if (e.type === 'error' || e.type === 'audio_chunk_error') {
        setState((prev) => ({ ...prev, error: e.message }));
        return;
      }
      if (e.type === 'call_started') {
        // 백엔드가 통화 로그를 생성 → 종료 시 이 id로 상세를 조회한다.
        setState((prev) => ({ ...prev, logId: e.call.id }));
        return;
      }
      // 오디오 청크 응답: 백엔드가 3초 청크마다 "그 청크만" 독립 전사해 조각으로 내려준다.
      // 한 문장이 청크 경계에서 잘려 여러 조각으로 오므로, 같은 화자(role)의 연속 조각을
      // 하나의 말풍선으로 병합해 대화가 끊겨 보이는 문제를 해결한다. (화자가 바뀌면 새 말풍선)
      if (e.type === 'audio_analysis_ack' || e.type === 'audio_phishing_detected') {
        const score = e.risk_score;
        maxScore.current = Math.max(maxScore.current, score);
        const matched = e.type === 'audio_phishing_detected' ? e.matched_patterns : [];
        const evidence = e.type === 'audio_phishing_detected' ? e.core_evidence : '';
        const incoming = (e.transcripts ?? [])
          .map((tr) => ({
            role: (tr.role ?? 'unknown').trim() || 'unknown',
            content: (tr.content ?? '').trim(),
            atSec: Math.round(tr.start_time ?? 0),
          }))
          .filter((t) => t.content.length > 0);

        setState((prev) => {
          const level = riskLevelFromScore(score, dangerThreshold);
          const turns: TranscriptTurn[] = [...prev.turns];
          for (const inc of incoming) {
            const last = turns[turns.length - 1];
            if (last && last.role === inc.role) {
              // 같은 화자의 연속 발화 → 직전 말풍선에 이어붙인다.
              const merged = `${last.content} ${inc.content}`.replace(/\s+/g, ' ').trim();
              turns[turns.length - 1] = {
                ...last,
                content: merged,
                riskScore: score,
                keywords: extractKeywords(merged, 4),
              };
            } else {
              // 화자 전환(또는 첫 발화) → 새 말풍선.
              turnCounter.current += 1;
              turns.push({
                turnIndex: turnCounter.current,
                role: inc.role,
                isMine: false,
                content: inc.content,
                atSec: inc.atSec,
                riskScore: score,
                keywords: extractKeywords(inc.content, 4),
              });
            }
          }
          const next: CallSessionState = {
            ...prev,
            turns,
            score,
            level,
            matchedPatterns: matched.length ? matched : prev.matchedPatterns,
            coreEvidence: evidence || prev.coreEvidence,
          };
          if (!warned.current && level === 'danger') {
            warned.current = true;
            setTimeout(() => onDanger.current?.(next), 0);
          }
          return next;
        });
        return;
      }
      if (e.type === 'analysis_ack' || e.type === 'phishing_detected') {
        const score = e.risk_score;
        maxScore.current = Math.max(maxScore.current, score);
        const matched = e.type === 'phishing_detected' ? e.matched_patterns : [];
        const evidence = e.type === 'phishing_detected' ? e.core_evidence : '';
        const turnIdx = e.message?.turn_index;

        setState((prev) => {
          const level = riskLevelFromScore(score, dangerThreshold);
          const turns = turnIdx
            ? prev.turns.map((t) => (t.turnIndex === turnIdx ? { ...t, riskScore: score } : t))
            : prev.turns;
          const next: CallSessionState = {
            ...prev,
            turns,
            score,
            level,
            matchedPatterns: matched.length ? matched : prev.matchedPatterns,
            coreEvidence: evidence || prev.coreEvidence,
          };
          if (!warned.current && level === 'danger') {
            warned.current = true;
            setTimeout(() => onDanger.current?.(next), 0);
          }
          return next;
        });
      }
    },
    [dangerThreshold],
  );

  // 경과초 타이머(일시정지 누적 시간 pausedAccumMs를 빼서 정지 중엔 멈춘 것처럼 보이게 함)
  const startTimer = () => {
    if (timer.current) return;
    timer.current = setInterval(() => {
      setState((prev) => ({
        ...prev,
        elapsedSec: Math.floor((Date.now() - startedAt.current - pausedAccumMs.current) / 1000),
      }));
    }, 1000);
  };

  // 오디오 캡처 시작(마이크→3초 WAV 청크→WS). start()와 resume()에서 재사용.
  const beginAudioCapture = (conn: AnalyzeConnection) => {
    const capture = createAudioCapture();
    captureRef.current = capture;
    capture.onError((m) => setState((prev) => ({ ...prev, error: m })));
    capture.onChunk((c) => {
      sentChunks.current += 1;
      conn.sendAudioChunk(c.base64, c.chunkIndex);
    });
    void capture.start();
  };

  const start = useCallback(() => {
    const conn = createAnalyzeConnection();
    connRef.current = conn;
    conn.onEvent(handleEvent);
    startedAt.current = Date.now();
    pausedAccumMs.current = 0;
    sentChunks.current = 0;
    recvChunks.current = 0;

    // ── 웹 실시간: 오디오 스트리밍 경로 ──
    if (audioMode) {
      conn.start(scenario.phone, { audio: true });
      beginAudioCapture(conn);
      startTimer();
      setState((prev) => ({ ...prev, running: true }));
      return;
    }

    // ── 네이티브/데모: 텍스트 STT 경로 ──
    const stt = createSttService(scenario, speed);
    sttRef.current = stt;
    conn.start(scenario.phone);

    stt.onTurn((t) => {
      turnCounter.current += 1;
      const idx = turnCounter.current;
      const turn: TranscriptTurn = {
        turnIndex: idx,
        role: t.role,
        isMine: t.isMine,
        content: t.content,
        atSec: t.atSec,
        keywords: t.isMine ? [] : extractKeywords(t.content, 4),
      };
      setState((prev) => ({ ...prev, turns: [...prev.turns, turn] }));
      conn.sendMessage(t.role, t.content, idx);
    });
    stt.onEnd(() => {
      setState((prev) => ({ ...prev, finished: true }));
    });

    startTimer();
    stt.start();
    setState((prev) => ({ ...prev, running: true }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [handleEvent, scenario, speed, audioMode]);

  const stop = useCallback(() => {
    sttRef.current?.stop();
    captureRef.current?.stop();
    connRef.current?.close();
    if (timer.current) clearInterval(timer.current);
    timer.current = null;
    setState((prev) => ({ ...prev, running: false }));
  }, []);

  // 분석 일시정지: 오디오 캡처(또는 데모 STT)만 멈추고 WS 세션은 유지 → 같은 통화로 이어서 재개.
  const pause = useCallback(() => {
    if (!connRef.current) return;
    captureRef.current?.stop();
    captureRef.current = null;
    sttRef.current?.stop();
    if (timer.current) {
      clearInterval(timer.current);
      timer.current = null;
    }
    pausedAtMs.current = Date.now();
    setState((prev) => ({ ...prev, paused: true, running: false }));
  }, []);

  const resume = useCallback(() => {
    const conn = connRef.current;
    if (!conn) return;
    pausedAccumMs.current += Date.now() - pausedAtMs.current;
    if (audioMode) beginAudioCapture(conn);
    else sttRef.current?.start();
    startTimer();
    setState((prev) => ({ ...prev, paused: false, running: true }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [audioMode]);

  // 정상 종료: 아직 3초 못 채운 마지막 오디오를 마저 보내고, "보낸 청크 전부의 전사 응답이
  // 도착할 때까지" 기다린 뒤(최대 MAX_WAIT_MS) WS를 닫는다. 대기 후의 "최종" state를 반환한다.
  // → 종료 시점에 아직 전사 안 된 마지막 발화까지 대화 내역에 남는다. (지연은 감수)
  const MAX_WAIT_MS = 20000; // 백엔드가 멈춰도 무한 대기하지 않도록 안전 상한
  const finish = useCallback(async (): Promise<CallSessionState> => {
    captureRef.current?.flushFinal(); // 남은 partial 오디오를 마지막 청크로 전송(sentChunks 증가)
    captureRef.current?.stop();
    captureRef.current = null;
    sttRef.current?.stop();
    if (timer.current) {
      clearInterval(timer.current);
      timer.current = null;
    }
    setState((prev) => ({ ...prev, running: false }));
    // 보낸 청크 수만큼 응답(전사)이 다 올 때까지 대기. 상한 초과 시 중단.
    const deadline = Date.now() + MAX_WAIT_MS;
    while (recvChunks.current < sentChunks.current && Date.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 200));
    }
    // 마지막 응답의 setState가 latestRef에 반영될 시간을 조금 더 준다.
    await new Promise((resolve) => setTimeout(resolve, 400));
    connRef.current?.close();
    connRef.current = null;
    return latestRef.current;
  }, []);

  const buildResult = useCallback(
    (id: number): CallResult => {
      const fullText = state.turns.map((t) => `${t.role}: ${t.content}`).join('\n');
      return {
        id,
        name: scenario.phone,
        category: categorizeType(state.matchedPatterns, fullText),
        finalScore: maxScore.current,
        matchedPatterns: state.matchedPatterns,
        coreEvidence: state.coreEvidence || '분석된 위험 근거가 없습니다.',
        keywords: extractKeywords(fullText, 6),
        turns: state.turns,
        source: scenario.source,
        createdAt: new Date().toISOString(),
        durationSec: state.elapsedSec,
      };
    },
    [scenario.phone, scenario.source, state],
  );

  useEffect(() => {
    return () => {
      sttRef.current?.stop();
      captureRef.current?.stop();
      connRef.current?.close();
      if (timer.current) clearInterval(timer.current);
    };
  }, []);

  return { state, start, stop, pause, resume, finish, buildResult };
}
