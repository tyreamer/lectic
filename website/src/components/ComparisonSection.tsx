import { Check, Minus } from 'lucide-react';

interface ComparisonRow {
  dimension: string;
  typical: string;
  compiler: string;
}

const ROWS: ComparisonRow[] = [
  {
    dimension: 'Your sources',
    typical: 'Chunked into vectors, then discarded',
    compiler: 'Preserved in full with byte-level hashes',
  },
  {
    dimension: 'Between sessions',
    typical: 'Context lost when you close the tab',
    compiler: 'Collections saved locally, reusable forever',
  },
  {
    dimension: 'What you get back',
    typical: 'A conversational paragraph',
    compiler: 'A structured deliverable with citations',
  },
  {
    dimension: 'Conflicting sources',
    typical: 'Smoothed into a generic consensus',
    compiler: 'Disagreements preserved with explicit rules',
  },
  {
    dimension: 'Traceability',
    typical: 'No way to tell what came from where',
    compiler: 'Every claim linked to a source line span',
  },
  {
    dimension: 'Reuse',
    typical: 'Re-upload and re-explain next time',
    compiler: 'Same collection, different goal, zero setup',
  },
];

export const ComparisonSection = () => {
  return (
    <section id="different" className="py-20 md:py-28 border-t border-warm-100">
      <div className="section-container">
        <div className="max-w-2xl mx-auto text-center mb-14">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-warm-900 tracking-tight leading-tight mb-4">
            Why this isn't just chat<br />over documents.
          </h2>
          <p className="text-base sm:text-lg text-warm-500 leading-relaxed">
            Standard AI chats forget everything and hallucinate freely. Expertise Compiler keeps your sources intact and gives you work you can actually verify.
          </p>
        </div>

        <div className="max-w-3xl mx-auto">
          {/* Table header */}
          <div className="grid grid-cols-12 gap-4 pb-3 mb-1 text-[12px] font-semibold uppercase tracking-wider">
            <div className="col-span-3 text-warm-400" />
            <div className="col-span-4 text-warm-400 flex items-center gap-1.5 pl-4">
              <Minus className="w-3.5 h-3.5 text-warm-300" />
              Standard AI chat
            </div>
            <div className="col-span-5 text-warm-700 flex items-center gap-1.5 pl-4">
              <Check className="w-3.5 h-3.5 text-amber-600" />
              Expertise Compiler
            </div>
          </div>

          {/* Rows */}
          <div className="space-y-1">
            {ROWS.map((row, i) => (
              <div
                key={row.dimension}
                className={`grid grid-cols-12 gap-4 py-4 px-1 rounded-lg transition-colors hover:bg-warm-50 ${
                  i < ROWS.length - 1 ? 'border-b border-warm-100' : ''
                }`}
              >
                <div className="col-span-3 text-[13px] font-semibold text-warm-800">
                  {row.dimension}
                </div>
                <div className="col-span-4 text-[13px] text-warm-400 pl-4">
                  {row.typical}
                </div>
                <div className="col-span-5 text-[13px] text-warm-700 font-medium pl-4">
                  {row.compiler}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};
