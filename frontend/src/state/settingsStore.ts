import { create } from 'zustand';
import { DEFAULT_DANGER_THRESHOLD } from '@/core/utils/riskLevel';
import { loadJson, saveJson, STORAGE_KEYS } from '@/data/services/storage';

export type ThemeMode = 'system' | 'light' | 'dark';

interface PersistedSettings {
  themeMode: ThemeMode;
  largeText: boolean;
  dangerThreshold: number; // 0.70 ~ 0.85 (전면 경고 트리거)
}

interface SettingsState extends PersistedSettings {
  hydrated: boolean;
  hydrate: () => Promise<void>;
  setThemeMode: (m: ThemeMode) => void;
  setLargeText: (v: boolean) => void;
  setDangerThreshold: (v: number) => void;
}

const DEFAULTS: PersistedSettings = {
  themeMode: 'system',
  largeText: false,
  dangerThreshold: DEFAULT_DANGER_THRESHOLD,
};

function persist(s: SettingsState) {
  const data: PersistedSettings = {
    themeMode: s.themeMode,
    largeText: s.largeText,
    dangerThreshold: s.dangerThreshold,
  };
  void saveJson(STORAGE_KEYS.settings, data);
}

export const useSettingsStore = create<SettingsState>((set, get) => ({
  ...DEFAULTS,
  hydrated: false,
  hydrate: async () => {
    const saved = await loadJson<PersistedSettings>(STORAGE_KEYS.settings);
    set({ ...DEFAULTS, ...(saved ?? {}), hydrated: true });
  },
  setThemeMode: (themeMode) => {
    set({ themeMode });
    persist(get());
  },
  setLargeText: (largeText) => {
    set({ largeText });
    persist(get());
  },
  setDangerThreshold: (dangerThreshold) => {
    set({ dangerThreshold });
    persist(get());
  },
}));
