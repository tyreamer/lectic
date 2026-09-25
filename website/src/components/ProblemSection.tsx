import { Upload, MessageSquare, RotateCcw, X as XIcon } from 'lucide-react';

export const ProblemSection = () => {
  const painPoints = [
    {
      icon: <Upload className="w-4 h-4" />,
      label: 'Re-uploading the same files',
      detail: 'Every new chat session starts from zero. Drag-and-drop the same PDFs, transcripts, and notes you uploaded last week.',
    },
    {
      icon: <MessageSquare className="w-4 h-4" />,
      label: 'Re-explaining what matters',
      detail: 'Spend the first 10 minutes telling the AI what to focus on, what to ignore, and how to think about the material.',
    },
    {
      icon: <RotateCcw className="w-4 h-4" />,
      label: 'Reconstructing the method',
      detail: 'You had a great process working last time. But the session is gone, so you reverse-engineer it from memory.',
    },
    {
      icon: <XIcon className="w-4 h-4" />,
      label: 'Losing context when you close the tab',
      detail: 'The moment you leave, everything evaporates. Citations, reasoning, the approach that finally worked — all gone.',
    },
  ];

  return (
    <section className="py-20 md:py-28 bg-white border-t border-warm-100">
      <div className="section-container">
        <div className="max-w-2xl mx-auto text-center mb-14">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-warm-900 tracking-tight leading-tight mb-4">
            Content is everywhere.<br />
            Usable expertise is not.
          </h2>
          <p className="text-base sm:text-lg text-warm-500 leading-relaxed">
            You already have the material — favorite experts, company playbooks, training recordings, conference talks, transcripts, docs. But every time you open an AI chat, you're back at square one.
          </p>
        </div>

        <div className="max-w-3xl mx-auto grid grid-cols-1 sm:grid-cols-2 gap-4">
          {painPoints.map((point) => (
            <div
              key={point.label}
              className="p-5 rounded-xl bg-warm-50 border border-warm-200 hover:border-warm-300 transition-colors"
            >
              <div className="flex items-start gap-3">
                <div className="p-2 rounded-lg bg-warm-200/60 text-warm-500 shrink-0 mt-0.5">
                  {point.icon}
                </div>
                <div>
                  <p className="text-[14px] font-semibold text-warm-800 mb-1">{point.label}</p>
                  <p className="text-[13px] text-warm-500 leading-relaxed">{point.detail}</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        <p className="text-center text-[14px] text-warm-400 mt-10 max-w-md mx-auto">
          Chatbots treat your knowledge like temporary scratch paper. You deserve something that remembers.
        </p>
      </div>
    </section>
  );
};
