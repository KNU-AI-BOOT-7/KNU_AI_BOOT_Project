import { create } from 'zustand';
import { loadJson, saveJson, STORAGE_KEYS } from '@/data/services/storage';

/** 온보딩 완료 여부 (최초 1회 노출) */
interface AppState {
  onboarded: boolean | null; // null = 아직 로드 전
  hydrate: () => Promise<void>;
  completeOnboarding: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  onboarded: null,
  hydrate: async () => {
    const v = await loadJson<boolean>(STORAGE_KEYS.onboarded);
    set({ onboarded: v === true });
  },
  completeOnboarding: () => {
    void saveJson(STORAGE_KEYS.onboarded, true);
    set({ onboarded: true });
  },
}));
