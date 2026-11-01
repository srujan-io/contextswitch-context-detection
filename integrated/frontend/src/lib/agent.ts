import type { ModalityId, ModalityState } from "@/types/contextSwitch";

export const RELIABILITY_THRESHOLD = 0.6;
/** Preferred modality wins if within this margin of the best candidate. */
export const PREFERENCE_MARGIN = 0.05;

/**
 * Pure selection rule used by the demo simulation (the real agent runs on the backend).
 * Picks the most reliable available modality at/above threshold; ties go to the preferred one.
 */
export function pickModality(
  modalities: ModalityState[],
  preferred: ModalityId,
  threshold = RELIABILITY_THRESHOLD,
): ModalityId | null {
  const candidates = modalities.filter(
    (m) => m.available && m.confidence !== null && m.confidence >= threshold,
  );
  if (candidates.length === 0) return null;
  const best = candidates.reduce((a, b) => ((b.confidence ?? 0) > (a.confidence ?? 0) ? b : a));
  const pref = candidates.find((m) => m.id === preferred);
  if (pref && (best.confidence ?? 0) - (pref.confidence ?? 0) <= PREFERENCE_MARGIN) return pref.id;
  return best.id;
}

/** Manual selection is only allowed for available modalities. */
export function canSelectManually(modalities: ModalityState[], id: ModalityId): boolean {
  return modalities.some((m) => m.id === id && m.available);
}
