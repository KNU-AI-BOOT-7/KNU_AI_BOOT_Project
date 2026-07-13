/**
 * "실시간 청취 분석" 화면 전용 프리미티브.
 * 디자인(VoiceGuard 청취분석.dc.html)의 인라인 SVG/CSS 애니메이션을
 * react-native-svg + react-native-reanimated로 최대한 동일하게 재현한다.
 * (RN이라 앱/웹 공통으로 동작)
 */
import { useEffect } from 'react';
import { View } from 'react-native';
import Svg, { Circle, Path, Rect } from 'react-native-svg';
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withDelay,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';
import { AppText } from './AppText';

/** #rrggbb + alpha → rgba() 문자열 */
export function rgba(hex: string, a: number): string {
  const h = hex.replace('#', '');
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${a})`;
}

// ───────────────────────── 애니메이션 아톰 ─────────────────────────

/** vgPulse: 링이 커지며 흐려짐(맥동). 마이크 오브 주변 링. */
function PulseRing({ size, color, delay = 0 }: { size: number; color: string; delay?: number }) {
  const p = useSharedValue(0);
  useEffect(() => {
    p.value = withDelay(delay, withRepeat(withTiming(1, { duration: 1300, easing: Easing.inOut(Easing.ease) }), -1, true));
  }, [p, delay]);
  const style = useAnimatedStyle(() => ({
    transform: [{ scale: 1 + 0.12 * p.value }],
    opacity: 0.55 - 0.4 * p.value,
  }));
  return (
    <Animated.View
      pointerEvents="none"
      style={[
        {
          position: 'absolute',
          width: size,
          height: size,
          borderRadius: size / 2,
          borderWidth: 1.5,
          borderColor: rgba(color, 0.4),
        },
        style,
      ]}
    />
  );
}

/** vgBlink: 깜빡임(1↔0.25). LIVE 점/상태 점. */
export function BlinkDot({ size, color, period = 1600 }: { size: number; color: string; period?: number }) {
  const o = useSharedValue(1);
  useEffect(() => {
    o.value = withRepeat(withTiming(0.25, { duration: period / 2, easing: Easing.inOut(Easing.ease) }), -1, true);
  }, [o, period]);
  const style = useAnimatedStyle(() => ({ opacity: o.value }));
  return (
    <Animated.View
      style={[
        { width: size, height: size, borderRadius: size / 2, backgroundColor: color, shadowColor: color, shadowOpacity: 0.9, shadowRadius: 6 },
        style,
      ]}
    />
  );
}

/** vgSpin: 회전(AI 노드 궤도). */
function SpinRing({
  inset,
  color,
  duration,
  dashed = false,
  reverse = false,
}: {
  inset: number;
  color: string;
  duration: number;
  dashed?: boolean;
  reverse?: boolean;
}) {
  const r = useSharedValue(0);
  useEffect(() => {
    r.value = withRepeat(withTiming(reverse ? -360 : 360, { duration, easing: Easing.linear }), -1, false);
  }, [r, duration, reverse]);
  const style = useAnimatedStyle(() => ({ transform: [{ rotate: `${r.value}deg` }] }));
  return (
    <Animated.View
      pointerEvents="none"
      style={[
        {
          position: 'absolute',
          top: inset,
          left: inset,
          right: inset,
          bottom: inset,
          borderRadius: 999,
          borderWidth: 1,
          borderStyle: dashed ? 'dashed' : 'solid',
          borderColor: color,
        },
        style,
      ]}
    />
  );
}

/** vgFloat: 위아래 부유. AI 코어. */
function FloatDot({ color }: { color: string }) {
  const y = useSharedValue(0);
  useEffect(() => {
    y.value = withRepeat(withTiming(-3, { duration: 1700, easing: Easing.inOut(Easing.ease) }), -1, true);
  }, [y]);
  const style = useAnimatedStyle(() => ({ transform: [{ translateY: y.value }] }));
  return (
    <Animated.View
      pointerEvents="none"
      style={[
        {
          position: 'absolute',
          top: 46,
          left: 46,
          right: 46,
          bottom: 46,
          borderRadius: 999,
          backgroundColor: color,
          shadowColor: color,
          shadowOpacity: 0.7,
          shadowRadius: 12,
        },
        style,
      ]}
    />
  );
}

// ───────────────────────── SVG 글리프 (디자인 그대로) ─────────────────────────

export function MicGlyph({ size = 34, color }: { size?: number; color: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Rect x="8.5" y="2" width="7" height="12" rx="3.5" fill={color} />
      <Path d="M5 11a7 7 0 0 0 14 0" stroke={color} strokeWidth={2} strokeLinecap="round" />
      <Path d="M12 18v3.5M8.5 21.5h7" stroke={color} strokeWidth={2} strokeLinecap="round" />
    </Svg>
  );
}

export function ShieldGlyph({ size = 24 }: { size?: number }) {
  return (
    <Svg width={size} height={(size * 26) / 24} viewBox="0 0 24 26" fill="none">
      <Path d="M12 1 22 4.6v8.2c0 6.6-4.3 10-10 12.2C6 22.8 2 19.4 2 12.8V4.6L12 1Z" fill="#12233f" stroke="#3f7ad6" strokeWidth={1.4} />
      <Path d="M7.6 13.2l2.7 2.9 6.1-6.6" stroke="#5b9bff" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

export function ChatGlyph({ size = 18, color = '#8b93a1' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M4 5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v8A2.5 2.5 0 0 1 17.5 16H9l-4 4v-4H6.5A2.5 2.5 0 0 1 4 13.5v-8Z"
        stroke={color}
        strokeWidth={1.6}
        strokeLinejoin="round"
      />
    </Svg>
  );
}

export function SparkleGlyph({ size = 18, color = '#8ab4ff' }: { size?: number; color?: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M12 2l1.9 5.6L19.5 9l-4.4 3.4L16.6 18 12 14.7 7.4 18l1.5-5.6L4.5 9l5.6-1.4L12 2Z" fill={color} />
    </Svg>
  );
}

export function PauseGlyph({ size = 18, color }: { size?: number; color: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Rect x="6" y="5" width="4" height="14" rx="1.4" fill={color} />
      <Rect x="14" y="5" width="4" height="14" rx="1.4" fill={color} />
    </Svg>
  );
}

export function PlayGlyph({ size = 18, color }: { size?: number; color: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M7 5.5v13a1 1 0 0 0 1.5.87l11-6.5a1 1 0 0 0 0-1.74l-11-6.5A1 1 0 0 0 7 5.5Z" fill={color} />
    </Svg>
  );
}

export function StopGlyph({ size = 18, color }: { size?: number; color: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Rect x="6" y="6" width="12" height="12" rx="3" fill={color} />
    </Svg>
  );
}

export function FileGlyph({ size = 18, color }: { size?: number; color: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path d="M7 3h7l4 4v14a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z" stroke={color} strokeWidth={1.6} />
      <Path d="M13 3v5h5M9 13h6M9 16.5h6" stroke={color} strokeWidth={1.6} strokeLinecap="round" />
    </Svg>
  );
}

export function GuideGlyph({ size = 18, color }: { size?: number; color: string }) {
  return (
    <Svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <Path
        d="M4 5.5A1.5 1.5 0 0 1 5.5 4H11v16H5.5A1.5 1.5 0 0 1 4 18.5v-13ZM20 5.5A1.5 1.5 0 0 0 18.5 4H13v16h5.5A1.5 1.5 0 0 0 20 18.5v-13Z"
        stroke={color}
        strokeWidth={1.6}
        strokeLinejoin="round"
      />
    </Svg>
  );
}

// ───────────────────────── 합성 컴포넌트 ─────────────────────────

/** 맥동 링 2개 + 중앙 마이크 오브. */
export function MicOrb({ color, label }: { color: string; label: string }) {
  return (
    <View style={{ position: 'relative', height: 190, alignItems: 'center', justifyContent: 'center', marginBottom: 6 }}>
      <PulseRing size={180} color={color} delay={0} />
      <PulseRing size={150} color={color} delay={600} />
      <View
        style={{
          width: 130,
          height: 130,
          borderRadius: 65,
          backgroundColor: '#120d05',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 7,
          borderWidth: 2,
          borderColor: rgba(color, 0.9),
          shadowColor: color,
          shadowOpacity: 0.45,
          shadowRadius: 22,
          shadowOffset: { width: 0, height: 0 },
          elevation: 14,
        }}
      >
        <MicGlyph size={34} color={color} />
        <AppText weight="700" style={{ fontSize: 15, color }}>
          {label}
        </AppText>
      </View>
    </View>
  );
}

/** AI 분석 카드 우측 장식 노드(궤도 회전 + 부유 코어). */
export function AiNode() {
  return (
    <View pointerEvents="none" style={{ position: 'absolute', right: -6, top: 44, width: 118, height: 118 }}>
      <View style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, borderRadius: 59, backgroundColor: rgba('#5b9bff', 0.12) }} />
      <SpinRing inset={22} color={rgba('#78aaff', 0.35)} duration={14000} />
      <SpinRing inset={34} color={rgba('#78aaff', 0.5)} duration={9000} dashed reverse />
      <FloatDot color="#5b83d0" />
    </View>
  );
}

/** 점수 원형 게이지(디자인: r=40, stroke=8, 중앙에 점수 + 소제목). */
export function ScoreGauge({ score, color, sub }: { score: number; color: string; sub: string }) {
  const size = 96;
  const stroke = 8;
  const r = 40;
  const cx = 48;
  const C = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, score));
  const off = C * (1 - clamped / 100);
  return (
    <View style={{ width: size, height: size }}>
      {/* -90° 회전으로 게이지 시작점을 12시 방향으로. (G origin 대신 Svg style 회전 → web DOM 경고 회피) */}
      <Svg width={size} height={size} style={{ transform: [{ rotate: '-90deg' }] }}>
        <Circle cx={cx} cy={cx} r={r} stroke="rgba(255,255,255,0.09)" strokeWidth={stroke} fill="none" />
        <Circle
          cx={cx}
          cy={cx}
          r={r}
          stroke={color}
          strokeWidth={stroke}
          strokeLinecap="round"
          fill="none"
          strokeDasharray={C}
          strokeDashoffset={off}
        />
      </Svg>
      <View style={{ position: 'absolute', left: 0, right: 0, top: 0, bottom: 0, alignItems: 'center', justifyContent: 'center' }}>
        <AppText weight="800" style={{ fontSize: 30, color: '#f6f8fc', lineHeight: 32 }}>
          {clamped}
        </AppText>
        <AppText weight="600" style={{ fontSize: 11, color, marginTop: 3 }}>
          {sub}
        </AppText>
      </View>
    </View>
  );
}
