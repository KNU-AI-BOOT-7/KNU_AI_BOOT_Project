import type { Scenario } from '@/data/mock/mockScenarios';

/** STT 공통 타입 + 목 구현 (네이티브/웹 양쪽에서 재사용) */
export interface RecognizedTurn {
  role: string;
  content: string;
  isMine: boolean;
  atSec: number;
}

export interface SttService {
  start(): void;
  stop(): void;
  onTurn(cb: (t: RecognizedTurn) => void): void;
  onEnd(cb: () => void): void;
  onError(cb: (msg: string) => void): void;
}

/** 스크립트 시나리오 재생(목) */
export class MockSttService implements SttService {
  private timers: ReturnType<typeof setTimeout>[] = [];
  private turnCb: ((t: RecognizedTurn) => void) | null = null;
  private endCb: (() => void) | null = null;
  private stopped = false;

  constructor(
    private scenario: Scenario,
    private speed = 1,
  ) {}

  onTurn(cb: (t: RecognizedTurn) => void) {
    this.turnCb = cb;
  }
  onEnd(cb: () => void) {
    this.endCb = cb;
  }
  onError() {}

  start() {
    this.stopped = false;
    for (const turn of this.scenario.turns) {
      const t = setTimeout(() => {
        if (this.stopped) return;
        this.turnCb?.({ role: turn.role, content: turn.content, isMine: turn.isMine, atSec: turn.atSec });
      }, (turn.atSec * 1000) / this.speed);
      this.timers.push(t);
    }
    const last = this.scenario.turns[this.scenario.turns.length - 1];
    const endT = setTimeout(
      () => {
        if (!this.stopped) this.endCb?.();
      },
      ((last ? last.atSec + 4 : 4) * 1000) / this.speed,
    );
    this.timers.push(endT);
  }

  stop() {
    this.stopped = true;
    this.timers.forEach(clearTimeout);
    this.timers = [];
  }
}
