// Bake the reader's annotations into a downloadable PDF.
//
//   • highlight / underline → drawn into the page content (always visible,
//     including printouts), using the stored PDF-native rects directly — they're
//     already in PDF user space (bottom-left origin, y-up), the same coordinate
//     system pdf-lib draws in, so no transform is needed.
//   • note → a REAL PDF Text annotation (the clickable sticky-note object), with
//     the user's comment as its Contents. Shows/expands in any PDF viewer that
//     supports annotations (Acrobat, Preview, Chrome/Edge); a bare viewer or a
//     printout shows just the icon. This is option "C".

import { BlendMode, PDFArray, PDFDocument, PDFHexString, PDFName, type PDFPage, rgb } from 'pdf-lib';
import type { Annotation } from '@/lib/groups/types';

const DEFAULT_COLOR = '#FFD54A'; // matches AnnotationLayer's default
const HIGHLIGHT_OPACITY = 0.4;
const UNDERLINE_THICKNESS = 1.5;
const NOTE_ICON_SIZE = 18;

/** '#RRGGBB' → [r,g,b] in 0..1; falls back to the default highlight colour. */
function hexToRgb(hex: string): [number, number, number] {
  const m = /^#?([0-9a-fA-F]{6})$/.exec(hex);
  if (!m) return [1, 0.835, 0.29];
  const n = parseInt(m[1], 16);
  return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

/** Add a clickable PDF Text (sticky-note) annotation to a page's /Annots. */
function addNoteAnnotation(
  pdfDoc: PDFDocument,
  page: PDFPage,
  x: number,
  y: number,
  comment: string,
  color: [number, number, number],
) {
  const ref = pdfDoc.context.register(
    pdfDoc.context.obj({
      Type: 'Annot',
      Subtype: 'Text',
      Rect: [x, y - NOTE_ICON_SIZE, x + NOTE_ICON_SIZE, y],
      Contents: PDFHexString.fromText(comment),
      T: PDFHexString.fromText('Note'),
      Name: 'Comment', // standard note icon
      Open: false,
      C: color,
    }),
  );
  // Reuse the page's existing /Annots array if present (e.g. real PDF links),
  // otherwise create one — never clobber annotations already in the document.
  const existing = page.node.lookup(PDFName.of('Annots'));
  let annots: PDFArray;
  if (existing instanceof PDFArray) {
    annots = existing;
  } else {
    annots = pdfDoc.context.obj([]) as PDFArray;
    page.node.set(PDFName.of('Annots'), annots);
  }
  annots.push(ref);
}

/** Original PDF bytes + the active group's annotations → an annotated PDF. */
export async function buildAnnotatedPdf(
  pdfBytes: ArrayBuffer,
  annotations: Annotation[],
): Promise<Uint8Array> {
  const pdfDoc = await PDFDocument.load(pdfBytes);
  const pages = pdfDoc.getPages();

  for (const a of annotations) {
    const [r, g, b] = hexToRgb(a.color || DEFAULT_COLOR);

    if (a.type === 'note') {
      const first = a.rects[0];
      const page = first && pages[first.page - 1];
      if (!page) continue;
      const [x0, , , y1] = first.rect; // anchor the icon at the selection's top-left
      addNoteAnnotation(pdfDoc, page, x0, y1, a.comment ?? '', [r, g, b]);
      continue;
    }

    const color = rgb(r, g, b);
    for (const { page: pageNum, rect } of a.rects) {
      const page = pages[pageNum - 1];
      if (!page) continue;
      const [x0, y0, x1, y1] = rect;
      const width = Math.max(0, x1 - x0);
      if (a.type === 'underline') {
        page.drawRectangle({ x: x0, y: y0, width, height: UNDERLINE_THICKNESS, color });
      } else {
        // highlight — Multiply keeps the underlying text crisp (real-highlighter look)
        const height = Math.max(0, y1 - y0);
        page.drawRectangle({ x: x0, y: y0, width, height, color, opacity: HIGHLIGHT_OPACITY, blendMode: BlendMode.Multiply });
      }
    }
  }

  return pdfDoc.save();
}
