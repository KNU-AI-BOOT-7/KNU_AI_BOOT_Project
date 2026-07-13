import Constants, { ExecutionEnvironment } from 'expo-constants';
import { USE_MOCK_STT } from '@/core/config/env';
import type { Scenario } from '@/data/mock/mockScenarios';
import { MockSttService, type RecognizedTurn, type SttService } from './sttMock';

export type { RecognizedTurn, SttService } from './sttMock';

/**
 * 온디바이스 실시간 STT (네이티브).
 * - dev/preview build: expo-speech-recognition(폰 내장) 실제 인식
 * - Expo Go: 네이티브 모듈 없음 → 자동 목 폴백
 * - 웹: sttService.web.ts 가 대신 사용됨(목)
 */
export const isExpoGo = Constants.executionEnvironment === ExecutionEnvironment.StoreClient;

class RealSttService implements SttService {
  private turnCb: ((t: RecognizedTurn) => void) | null = null;
  private endCb: (() => void) | null = null;
  private errCb: ((m: string) => void) | null = null;
  private subs: { remove: () => void }[] = [];
  private stopped = false;
  private startedAt = 0;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private SR: any = null;

  onTurn(cb: (t: RecognizedTurn) => void) {
    this.turnCb = cb;
  }
  onEnd(cb: () => void) {
    this.endCb = cb;
  }
  onError(cb: (m: string) => void) {
    this.errCb = cb;
  }

  async start() {
    this.stopped = false;
    this.startedAt = Date.now();
    try {
      // 네이티브 모듈은 dev build에만 존재 → 동적 require
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      this.SR = require('expo-speech-recognition');
    } catch {
      this.errCb?.('음성 인식 모듈을 불러올 수 없습니다. (dev build 필요)');
      return;
    }
    const mod = this.SR.ExpoSpeechRecognitionModule;
    try {
      const perm = await mod.requestPermissionsAsync();
      if (!perm.granted) {
        this.errCb?.('마이크·음성 인식 권한이 필요합니다.');
        return;
      }
    } catch {
      /* 권한 API 없으면 무시 */
    }

    this.subs.push(
      this.SR.addSpeechRecognitionListener('result', (e: { isFinal?: boolean; results?: { transcript?: string }[] }) => {
        const text = e.results?.[0]?.transcript?.trim();
        if (e.isFinal && text) {
          this.turnCb?.({
            role: 'speaker_a',
            content: text,
            isMine: false,
            atSec: Math.round((Date.now() - this.startedAt) / 1000),
          });
        }
      }),
    );
    this.subs.push(
      this.SR.addSpeechRecognitionListener('error', (e: { error?: string; message?: string }) => {
        if (e.error !== 'no-speech') this.errCb?.(e.message || e.error || '음성 인식 오류');
      }),
    );
    this.subs.push(
      this.SR.addSpeechRecognitionListener('end', () => {
        if (!this.stopped) {
          try {
            this.beginListening(mod);
          } catch {
            /* ignore */
          }
        }
      }),
    );
    this.beginListening(mod);
  }

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  private beginListening(mod: any) {
    mod.start({ lang: 'ko-KR', interimResults: true, continuous: true, requiresOnDeviceRecognition: false });
  }

  stop() {
    this.stopped = true;
    try {
      this.SR?.ExpoSpeechRecognitionModule?.stop();
    } catch {
      /* ignore */
    }
    this.subs.forEach((s) => {
      try {
        s.remove();
      } catch {
        /* ignore */
      }
    });
    this.subs = [];
  }
}

export function createSttService(scenario: Scenario, speed = 1): SttService {
  if (USE_MOCK_STT || isExpoGo) return new MockSttService(scenario, speed);
  return new RealSttService();
}
