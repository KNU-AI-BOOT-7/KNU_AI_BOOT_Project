import { create } from 'zustand';
import type { TranscriptTurn } from '@/data/models/types';
import { loadJson, saveJson, STORAGE_KEYS } from '@/data/services/storage';

/**
 * 통화별 전사(대화 전문) 로컬 저장소.
 *
 * 백엔드 히스토리 상세(GET /calls/{id})는 위험도·근거만 주고 발화(전사)는 반환하지 않는다
 * (messages 조회 API 부재). 그래서 실시간 분석 중 받은 전사를 통화 종료 시 logId별로
 * 로컬(AsyncStorage)에 저장해 결과 화면에서 다시 볼 수 있게 한다.
 * 추후 백엔드에 발화 조회 엔드포인트가 생기면 이 로컬 저장은 폴백으로 남긴다.
 */
interface TranscriptState {
  byLog: Record<number, TranscriptTurn[]>;
  hydrated: boolean;
  hydrate: () => Promise<void>;
  save: (logId: number, turns: TranscriptTurn[]) => void;
}

export const useTranscriptStore = create<TranscriptState>((set, get) => ({
  byLog: {},
  hydrated: false,
  hydrate: async () => {
    if (get().hydrated) return;
    const saved = await loadJson<Record<number, TranscriptTurn[]>>(STORAGE_KEYS.transcripts);
    // 이미 메모리에 저장된 항목(이번 세션에서 방금 저장한 것)이 디스크보다 우선.
    set({ byLog: { ...(saved ?? {}), ...get().byLog }, hydrated: true });
  },
  save: (logId, turns) => {
    if (!logId || turns.length === 0) return;
    const byLog = { ...get().byLog, [logId]: turns };
    set({ byLog });
    void saveJson(STORAGE_KEYS.transcripts, byLog);
  },
}));
