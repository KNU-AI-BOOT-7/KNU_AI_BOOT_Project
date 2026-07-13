import { create } from 'zustand';
import { fetchCalls as apiFetchCalls, type CallListItem } from '@/data/services/callsApi';

/**
 * 통화 히스토리 저장소 (백엔드 조회 기반).
 *
 * 결과는 분석 시점에 백엔드가 저장하므로, 앱은 GET /calls로 목록을 받아온다.
 * (로컬 저장 없음 — 백엔드가 단일 진실 소스)
 * 위험/주의/정상 카운트는 설정 임계값에 따라 화면에서 risk_score로 계산한다.
 */
interface CallState {
  calls: CallListItem[];
  loaded: boolean; // 최초 로드 완료 여부
  loading: boolean;
  error: string | null;
  fetchCalls: () => Promise<void>;
}

export const useCallStore = create<CallState>((set) => ({
  calls: [],
  loaded: false,
  loading: false,
  error: null,
  fetchCalls: async () => {
    set({ loading: true, error: null });
    try {
      const { calls } = await apiFetchCalls(100);
      const sorted = [...calls].sort(
        (a, b) => new Date(b.called_at).getTime() - new Date(a.called_at).getTime(),
      );
      set({ calls: sorted, loaded: true, loading: false });
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e), loading: false, loaded: true });
    }
  },
}));
