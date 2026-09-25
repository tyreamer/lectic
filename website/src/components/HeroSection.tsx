import { useState, useEffect, useRef } from 'react';
import { ArrowRight, FileText, BookOpen, Video, Briefcase, Plus, ChevronRight } from 'lucide-react';

interface Collection {
  name: string;
  sources: number;
  icon: React.ReactNode;
  active?: boolean;
}

const COLLECTIONS: Collection[] = [
  { name: 'Startup Strategy', sources: 42, icon: <Briefcase className="w-3.5 h-3.5" />, active: true },
  { name: 'OAuth2 & Zero Trust', sources: 8, icon: <FileText className="w-3.5 h-3.5" /> },
  { name: 'Portrait Lighting', sources: 14, icon: <Video className="w-3.5 h-3.5" /> },
  { name: 'Incident Runbooks', sources: 29, icon: <BookOpen className="w-3.5 h-3.5" /> },
];

const PROMPT_TEXT = 'Review my landing page copy using this collection.';

const RESULT_LINES = [
  { type: 'heading', text: 'Landing Page Review — Startup Strategy Collection' },
  { type: 'gap', text: '' },
  { type: 'subheading', text: '1. Hero headline' },
  { type: 'body', text: 'Your current headline claims "revolutionary AI platform." Source #4 (SaaStr 2024 Talk, 18:20) notes that technical buyers bounce when the problem isn\'t framed in their daily work. Consider switching to a direct outcome: what does the user get done?' },
  { type: 'source', text: 'Source: SaaStr 2024 Talk @ 18:20' },
  { type: 'gap', text: '' },
  { type: 'subheading', text: '2. Social proof placement' },
  { type: 'body', text: 'The logos section is below the fold. Source #12 (Homepage Teardowns, §3) recommends placing proof within the first viewport for B2B, especially when the product category is new.' },
  { type: 'source', text: 'Source: Homepage Teardowns 2024 §3' },
  { type: 'gap', text: '' },
  { type: 'subheading', text: '3. CTA clarity' },
  { type: 'body', text: '"Get started" is generic. Two sources agree: match the CTA to the user\'s actual next step. If it\'s a waitlist, say "Request an invite." If it\'s a demo, say "See it work."' },
  { type: 'source', text: 'Sources: Positioning Masterclass @ 34:10, Board Memo §7' },
];

export const HeroSection = () => {
  const [promptIndex, setPromptIndex] = useState(0);
  const [isTypingDone, setIsTypingDone] = useState(false);
  const [visibleLines, setVisibleLines] = useState(0);
  const [hasStarted, setHasStarted] = useState(false);
  const resultRef = useRef<HTMLDivElement>(null);

  // Start animation after mount
  useEffect(() => {
    const timer = setTimeout(() => setHasStarted(true), 800);
    return () => clearTimeout(timer);
  }, []);

  // Typing animation
  useEffect(() => {
    if (!hasStarted) return;
    if (promptIndex < PROMPT_TEXT.length) {
      const timer = setTimeout(() => setPromptIndex((i) => i + 1), 38);
      return () => clearTimeout(timer);
    } else {
      const timer = setTimeout(() => setIsTypingDone(true), 600);
      return () => clearTimeout(timer);
    }
  }, [promptIndex, hasStarted]);

  // Streaming result lines
  useEffect(() => {
    if (!isTypingDone) return;
    if (visibleLines < RESULT_LINES.length) {
      const delay = RESULT_LINES[visibleLines].type === 'gap' ? 100 : 180;
      const timer = setTimeout(() => {
        setVisibleLines((v) => v + 1);
        // Scroll the result panel down
        if (resultRef.current) {
          resultRef.current.scrollTop = resultRef.current.scrollHeight;
        }
      }, delay);
      return () => clearTimeout(timer);
    }
  }, [visibleLines, isTypingDone]);

  return (
    <section className="pt-28 pb-16 md:pt-36 md:pb-24">
      <div className="section-container">
        {/* Text */}
        <div className="text-center max-w-2xl mx-auto mb-12 md:mb-16">
          <h1 className="text-4xl sm:text-5xl md:text-[56px] font-extrabold tracking-tight text-warm-900 leading-[1.1] mb-5">
            Your knowledge,{' '}
            <span className="text-warm-900">ready to work.</span>
          </h1>
          <p className="text-lg sm:text-xl text-warm-500 leading-relaxed max-w-lg mx-auto">
            Save videos, transcripts, docs, and courses. Then use what they teach to review, decide, plan, learn, or create — without starting over every time.
          </p>

          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mt-8">
            <a
              href="#waitlist"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-lg bg-warm-900 text-white text-[15px] font-semibold hover:bg-warm-800 transition-colors"
            >
              Request an invite
              <ArrowRight className="w-4 h-4" />
            </a>
            <a
              href="#how-it-works"
              className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-lg bg-white text-warm-700 text-[15px] font-medium border border-warm-200 hover:border-warm-300 hover:bg-warm-50 transition-colors"
            >
              See how it works
            </a>
          </div>
        </div>

        {/* Product Window */}
        <div className="max-w-4xl mx-auto">
          <div className="product-window overflow-hidden">
            {/* Title bar */}
            <div className="flex items-center gap-2 px-4 py-3 bg-warm-50 border-b border-warm-200">
              <div className="flex gap-1.5">
                <span className="w-3 h-3 rounded-full bg-[#FF5F57]" />
                <span className="w-3 h-3 rounded-full bg-[#FEBC2E]" />
                <span className="w-3 h-3 rounded-full bg-[#28C840]" />
              </div>
              <div className="ml-3 text-[12px] text-warm-400 font-mono">
                Expertise Compiler
              </div>
            </div>

            <div className="flex min-h-[420px] md:min-h-[480px]">
              {/* Sidebar */}
              <div className="hidden sm:flex flex-col w-56 border-r border-warm-200 bg-warm-50/50 p-3 shrink-0">
                <div className="text-[11px] font-semibold text-warm-400 uppercase tracking-wider px-2 mb-2">
                  Collections
                </div>
                <div className="space-y-0.5 flex-1">
                  {COLLECTIONS.map((col) => (
                    <button
                      key={col.name}
                      className={`w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-left text-[13px] transition-colors ${
                        col.active
                          ? 'bg-warm-200/70 text-warm-900 font-medium'
                          : 'text-warm-500 hover:bg-warm-100 hover:text-warm-700'
                      }`}
                    >
                      <span className="text-warm-400">{col.icon}</span>
                      <span className="flex-1 truncate">{col.name}</span>
                      <span className="text-[11px] text-warm-400 font-mono">{col.sources}</span>
                    </button>
                  ))}
                </div>
                <button className="flex items-center gap-1.5 px-2.5 py-2 text-[13px] text-warm-400 hover:text-warm-600 transition-colors mt-2">
                  <Plus className="w-3.5 h-3.5" />
                  <span>New collection</span>
                </button>
              </div>

              {/* Main content area */}
              <div className="flex-1 flex flex-col">
                {/* Collection header */}
                <div className="px-5 py-3 border-b border-warm-200 flex items-center justify-between">
                  <div className="flex items-center gap-2 text-[13px]">
                    <span className="font-semibold text-warm-900">Startup Strategy</span>
                    <span className="text-warm-400">·</span>
                    <span className="text-warm-400">42 sources</span>
                    <span className="text-warm-400">·</span>
                    <span className="text-warm-400 font-mono text-[11px]">v1.1</span>
                  </div>
                </div>

                {/* Result area */}
                <div ref={resultRef} className="flex-1 px-5 py-4 overflow-y-auto">
                  {isTypingDone && visibleLines > 0 && (
                    <div className="space-y-1">
                      {RESULT_LINES.slice(0, visibleLines).map((line, i) => {
                        if (line.type === 'gap') return <div key={i} className="h-2" />;
                        if (line.type === 'heading')
                          return (
                            <h4 key={i} className="text-[14px] font-semibold text-warm-900 pb-1 stream-in">
                              {line.text}
                            </h4>
                          );
                        if (line.type === 'subheading')
                          return (
                            <p key={i} className="text-[13px] font-semibold text-warm-700 stream-in">
                              {line.text}
                            </p>
                          );
                        if (line.type === 'source')
                          return (
                            <p key={i} className="text-[11px] font-mono text-amber-600 bg-amber-50 inline-block px-2 py-0.5 rounded mt-0.5 mb-1 stream-in">
                              {line.text}
                            </p>
                          );
                        return (
                          <p key={i} className="text-[13px] text-warm-600 leading-relaxed stream-in">
                            {line.text}
                          </p>
                        );
                      })}
                      {visibleLines < RESULT_LINES.length && (
                        <span className="inline-block w-2 h-4 bg-warm-400 cursor-blink ml-0.5 rounded-sm" />
                      )}
                    </div>
                  )}
                  {!isTypingDone && (
                    <div className="flex items-center justify-center h-full">
                      <p className="text-sm text-warm-300">
                        {hasStarted ? '' : ''}
                      </p>
                    </div>
                  )}
                </div>

                {/* Input bar */}
                <div className="px-4 py-3 border-t border-warm-200 bg-white">
                  <div className="flex items-center gap-2 px-3 py-2.5 rounded-lg border border-warm-200 bg-warm-50">
                    <ChevronRight className="w-4 h-4 text-warm-300 shrink-0" />
                    <div className="flex-1 text-[13px] text-warm-700 font-mono">
                      {hasStarted ? PROMPT_TEXT.slice(0, promptIndex) : ''}
                      {!isTypingDone && hasStarted && (
                        <span className="inline-block w-[2px] h-4 bg-warm-900 cursor-blink ml-px align-text-bottom" />
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Caption below product */}
          <p className="text-center text-[15px] text-warm-500 mt-6 font-medium">
            Same knowledge. New job. No rebuilding context.
          </p>
        </div>
      </div>
    </section>
  );
};
