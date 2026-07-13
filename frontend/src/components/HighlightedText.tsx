import { Text, type TextStyle } from 'react-native';
import { AppText } from './AppText';

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * 텍스트 안의 위험 키워드를 하이라이트.
 * (백엔드가 단어 위치를 주지 않아 앱 키워드 사전으로 근사 — 05 항목 4)
 */
export function HighlightedText({
  text,
  keywords,
  baseColor,
  highlightColor,
  highlightBg,
  style,
  weightHighlight = '700',
}: {
  text: string;
  keywords: string[];
  baseColor: string;
  highlightColor: string;
  highlightBg?: string;
  style?: TextStyle;
  weightHighlight?: '600' | '700';
}) {
  const valid = keywords.filter((k) => k && k.length > 0).sort((a, b) => b.length - a.length);
  if (valid.length === 0) {
    return (
      <AppText color={baseColor} style={style}>
        {text}
      </AppText>
    );
  }

  const re = new RegExp(`(${valid.map(escapeRegex).join('|')})`, 'g');
  const parts = text.split(re);

  return (
    <AppText color={baseColor} style={style}>
      {parts.map((part, i) => {
        const isHit = valid.some((k) => k === part);
        if (!isHit) return part;
        return (
          <Text
            key={i}
            style={{
              color: highlightColor,
              backgroundColor: highlightBg,
              fontWeight: weightHighlight,
            }}
          >
            {part}
          </Text>
        );
      })}
    </AppText>
  );
}
