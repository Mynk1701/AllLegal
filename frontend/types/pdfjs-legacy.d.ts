// The pdfjs-dist legacy build (which ships the polyfills v6 needs for older/
// current browsers — e.g. Map.prototype.getOrInsertComputed) has no bundled
// .d.ts. Re-point its subpath at the package's main type declarations so the
// runtime import stays fully typed.
declare module 'pdfjs-dist/legacy/build/pdf.mjs' {
  export * from 'pdfjs-dist';
}
