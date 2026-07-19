import type { AnalyzeMode, ShapeType, Verdict } from './types';

export const KO_VERDICT: Record<Verdict, string> = {
  POSSIBLE: '제작 가능',
  IMPOSSIBLE: '제작 불가능',
  UNKNOWN: '판정 미완료',
};

export const KO_SHAPE_TYPE: Record<ShapeType, string> = {
  EMPTY: '빈 도형',
  BASIC: '기본 제작형',
  HALF: '하프',
  SWAPPABLE: '스왑 가능형',
  STACKABLE: '쌓기형',
  CLAW: '클로',
  CLAW_HYBRID: '클로 하이브리드',
  PIN_PUSH: '핀 밀기형',
  IMPOSSIBLE: '불가능',
  UNKNOWN: '미분류',
};

export const KO_MODE: Record<AnalyzeMode, string> = {
  fast: '빠른 판정',
  type: '유형 분석',
  proof: '제작 과정',
};

export const KO_OPERATION: Record<string, string> = {
  RAW_INPUT: '기본 입력',
  ROTATE: '회전',
  CUT: '자르기',
  SWAP: '스왑',
  STACK: '쌓기',
  GENERATE: '결정 생성',
  PIN_PUSH: '핀 밀기',
  CERTIFIED_MACRO: '인증된 묶음 과정',
};

export const KO_ROUTE: Record<string, string> = {
  empty: '빈 도형',
  unstable: '물리 불안정',
  basic: '기본 제작형',
  half: '전층 하프',
  swap: '스왑 조립',
  stack: '쌓기 조립',
  'claw-table': '인증 클로',
  'claw-target-index': '인증 클로 빠른 인덱스',
  'claw-hybrid-table': '인증 클로 하이브리드',
  'hybrid-target-index': '인증 클로 하이브리드 빠른 인덱스',
  'cap2-exhaustive-pinpush': '2층 이하 전수 핀 밀기',
  'pp-receipt-chain': 'PP receipt chain',
  'rank0-pinpush-frontier': 'Rank0 핀 밀기 frontier',
  'pp-closure-exhausted': 'PP closure 소진',
  'known-negative-certificate': '인증 음성 증명',
  'fast-corner-reject': '전층 코너 규칙 위반',
  'corner-necessary-condition': '전층 코너 필요조건 위반',
};

export function koRoute(route: string): string {
  return KO_ROUTE[route] ?? route;
}

export function koOperation(operation?: string): string {
  if (!operation) return '';
  return KO_OPERATION[operation] ?? operation;
}
