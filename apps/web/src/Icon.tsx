import type { ReactNode } from "react";

// Inline SVGs keep UI symbols independent of the device's fonts and emoji support.
const drawings: Record<string, ReactNode> = {
  chat: <path d="M21 11a8 8 0 0 1-8 8H8l-5 3V11a9 9 0 0 1 18 0Z" />,
  code: <><path d="m8 6-6 6 6 6m8-12 6 6-6 6m-3-15-2 18" /></>,
  seed: <><path d="M12 21V11M12 16C5 16 3 12 3 7c6 0 9 3 9 9ZM12 11c0-6 3-9 9-9 0 6-3 9-9 9Z" /></>,
  note: <><rect x="4" y="3" width="16" height="18" rx="2" /><path d="M8 8h8M8 12h8m-8 4h5" /></>,
  url: <><path d="m10 13 4-4m-6 6-1 1a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m2 2 1-1a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0" transform="translate(1 1)" /></>,
  upload: <><path d="M12 16V3m-5 5 5-5 5 5M4 15v5a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-5" /></>,
  file: <><path d="M14 2H5a1 1 0 0 0-1 1v18a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V8l-6-6Zm0 0v6h6M8 13h8m-8 4h6" /></>,
  pack: <><path d="m12 2 10 5-10 5L2 7l10-5Zm-10 10 10 5 10-5M2 17l10 5 10-5" /></>,
  video: <><rect x="2" y="4" width="20" height="16" rx="3" /><path d="m10 8 6 4-6 4V8Z" /></>,
  make: <><path d="m14 5 5 5M4 20l5-1L21 7a2 2 0 0 0-5-5L4 14v6Z" /></>,
  solve: <path d="M14 3a6 6 0 0 0-7 8l-5 5a3 3 0 0 0 4 4l5-5a6 6 0 0 0 8-7l-4 4-3-3 4-4Z" />,
  learn: <><path d="M12 5C9 3 5 3 2 4v15c3-1 7-1 10 1 3-2 7-2 10-1V4c-3-1-7-1-10 1Zm0 0v15" /></>,
  sparkle: <><path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5L12 3Z" /></>,
  brand: <path d="M12 1v22M1 12h22M4 4l16 16M4 20 20 4" />,
  right: <path d="M3 12h18m-7-7 7 7-7 7" />,
  left: <path d="M21 12H3m7-7-7 7 7 7" />,
  share: <path d="M5 19 19 5M5 5h14v14" />,
  download: <path d="M12 3v13m-5-5 5 5 5-5M4 18v3h16v-3" />,
  check: <path d="m4 12 5 5L20 6" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  logout: <path d="M9 3H3v18h6m5-14 5 5-5 5M7 12h12" />,
};

export function Glyph({ name }: { name: string }) {
  return <svg className="glyph" data-icon={name} viewBox="0 0 24 24" width="1em" height="1em"
    fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"
    aria-hidden="true" focusable="false">{drawings[name] || drawings.file}</svg>;
}

export default function Icon({ name }: { name: string }) {
  return <span className={"icon " + name} aria-hidden="true"><Glyph name={name} /></span>;
}
