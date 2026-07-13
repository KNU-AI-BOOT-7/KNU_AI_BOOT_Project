import { View } from 'react-native';
import Svg, { Circle, G } from 'react-native-svg';
import { AppText } from './AppText';
import { toPercent } from '@/core/utils/riskLevel';

/** 원형 위험도 게이지 */
export function RiskGauge({
  score,
  size = 120,
  color,
  trackColor = 'rgba(255,255,255,0.14)',
  textColor,
  showPercentSign = false,
  bgColor = 'transparent',
}: {
  score: number;
  size?: number;
  color: string;
  trackColor?: string;
  textColor?: string;
  showPercentSign?: boolean;
  bgColor?: string;
}) {
  const stroke = Math.max(4, size * 0.1);
  const r = (size - stroke) / 2;
  const cx = size / 2;
  const circumference = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, score));
  const dashOffset = circumference * (1 - pct);

  return (
    <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
      <Svg width={size} height={size}>
        <G rotation={-90} origin={`${cx}, ${cx}`}>
          <Circle cx={cx} cy={cx} r={r} stroke={trackColor} strokeWidth={stroke} fill={bgColor} />
          <Circle
            cx={cx}
            cy={cx}
            r={r}
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            fill="transparent"
          />
        </G>
      </Svg>
      <View style={{ position: 'absolute', alignItems: 'center' }}>
        <AppText
          weight="800"
          style={{ fontSize: size * 0.3, color: textColor ?? color, lineHeight: size * 0.34 }}
        >
          {toPercent(score)}
          {showPercentSign ? '%' : ''}
        </AppText>
      </View>
    </View>
  );
}
