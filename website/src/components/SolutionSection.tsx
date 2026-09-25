import { FolderOpen, MessageCircle, CheckCircle } from 'lucide-react';

export const SolutionSection = () => {
  const steps = [
    {
      number: '1',
      icon: <FolderOpen className="w-5 h-5" />,
      title: 'Collect what you trust',
      description: 'Drop in transcripts, docs, notes, or video captions. They\'re saved privately on your machine as an immutable collection you can name and reuse.',
      detail: '.txt, .md, .vtt, .srt — all local, all yours',
    },
    {
      number: '2',
      icon: <MessageCircle className="w-5 h-5" />,
      title: 'Tell it what you need',
      description: 'Say "Review this design," "Teach me identity checks," or "Help me pick between these two markets." No forms, no prompt templates.',
      detail: 'Natural language — your AI figures out the intent',
    },
    {
      number: '3',
      icon: <CheckCircle className="w-5 h-5" />,
      title: 'Get work you can use',
      description: 'It applies the procedures and criteria from the sources — with line-by-line citations, explicit limits, and zero hallucinated steps.',
      detail: 'Not a summary — a real deliverable backed by evidence',
    },
  ];

  return (
    <section id="how-it-works" className="py-20 md:py-28">
      <div className="section-container">
        <div className="max-w-2xl mx-auto text-center mb-14">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-warm-900 tracking-tight leading-tight mb-4">
            Save it once. Put it to work forever.
          </h2>
          <p className="text-base sm:text-lg text-warm-500 leading-relaxed">
            No prompt engineering. No model fine-tuning. Point it at content you trust and tell it what to do.
          </p>
        </div>

        <div className="max-w-4xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-6">
          {steps.map((step) => (
            <div
              key={step.number}
              className="relative p-6 rounded-xl bg-white border border-warm-200 card-shadow hover:card-shadow-hover transition-shadow duration-200"
            >
              <div className="flex items-center gap-3 mb-4">
                <span className="w-8 h-8 rounded-full bg-warm-100 text-warm-500 flex items-center justify-center text-[13px] font-bold">
                  {step.number}
                </span>
                <div className="text-warm-400">
                  {step.icon}
                </div>
              </div>

              <h3 className="text-[16px] font-bold text-warm-900 mb-2">{step.title}</h3>
              <p className="text-[13px] text-warm-500 leading-relaxed mb-4">{step.description}</p>

              <p className="text-[12px] text-warm-400 font-mono">{step.detail}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};
