// The coordinate transform — the crux that validates the upstream bbox/flip work.
//
// Our rects are PDF-NATIVE (bottom-left origin, y-up) in PDF points. PDF.js's
// viewport maps native -> screen (top-left, y-down), absorbing the y-flip, the
// render scale, and any page rotation. We convert BOTH corners and normalise
// with min/max, because after the y-flip the "bottom" corner becomes the larger
// screen-y — you cannot assume (x0,y0) is the visual top-left.
//
// devicePixelRatio note: callers render the canvas backing store at scale*dpr
// for crispness, but pass the *scale-only* viewport here. Overlay boxes are then
// in the same CSS px as the canvas's CSS size, so highlights line up regardless
// of dpr. Keep dpr OUT of this function.

import type { PageViewport } from './pdfjs';

export interface OverlayBox {
  left: number;
  top: number;
  width: number;
  height: number;
}

/** One PDF-native rect -> an absolutely-positioned overlay box (CSS px),
 *  relative to a page wrapper sized at viewport.width x viewport.height. */
export function nativeRectToOverlay(
  rect: [number, number, number, number],
  viewport: PageViewport,
): OverlayBox {
  const [x0, y0, x1, y1] = rect;
  const [ax, ay] = viewport.convertToViewportPoint(x0, y0);
  const [bx, by] = viewport.convertToViewportPoint(x1, y1);
  return {
    left: Math.min(ax, bx),
    top: Math.min(ay, by),
    width: Math.abs(bx - ax),
    height: Math.abs(by - ay),
  };
}

/** Is a point (CSS px, relative to the page wrapper) inside an overlay box? */
export function pointInBox(px: number, py: number, box: OverlayBox): boolean {
  return px >= box.left && px <= box.left + box.width && py >= box.top && py <= box.top + box.height;
}
