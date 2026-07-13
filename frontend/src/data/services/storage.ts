import AsyncStorage from '@react-native-async-storage/async-storage';

/** 로컬 영구 저장 (설정/온보딩 플래그/로컬 통화 상세) */
export const STORAGE_KEYS = {
  onboarded: 'vg.onboarded',
  settings: 'vg.settings',
  results: 'vg.results', // 세션 중 누적한 CallResult 목록(과거 상세 API 부재 우회)
  transcripts: 'vg.transcripts', // 통화별 전사(대화 전문) 로컬 저장 (messages 조회 API 부재 우회)
} as const;

export async function loadJson<T>(key: string): Promise<T | null> {
  try {
    const raw = await AsyncStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

export async function saveJson(key: string, value: unknown): Promise<void> {
  try {
    await AsyncStorage.setItem(key, JSON.stringify(value));
  } catch {
    // 저장 실패는 조용히 무시(데모)
  }
}

export async function removeKey(key: string): Promise<void> {
  try {
    await AsyncStorage.removeItem(key);
  } catch {
    // ignore
  }
}
