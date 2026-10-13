// First-run guide: shown once automatically, skippable, and available again from the Guide button.

const KEY = 'pngsvg.tour.v1';

export const tour = $state({ open: false, step: 0 });

export function tourSeen(): boolean {
  try {
    return localStorage.getItem(KEY) === 'done';
  } catch {
    return true; // no storage (private mode): do not nag on every start
  }
}

export function startTour(): void {
  tour.step = 0;
  tour.open = true;
}

export function finishTour(): void {
  tour.open = false;
  try {
    localStorage.setItem(KEY, 'done');
  } catch {
    /* ignore */
  }
}
