export const ASSISTED_DICTATION_SILENCE_MS = 3000;

export function appendDictationText(base: string, transcript: string): string {
  const addition = transcript.trim();
  if (!addition) return base;
  const prefix = base.trim();
  return `${prefix}${prefix ? ' ' : ''}${addition}`.slice(0, 1000).trimEnd();
}

export function shouldRestartDictation(now: number, lastResultAt: number, stopped: boolean): boolean {
  return !stopped && now - lastResultAt < ASSISTED_DICTATION_SILENCE_MS;
}
