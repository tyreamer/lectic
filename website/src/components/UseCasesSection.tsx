import { Shield, GraduationCap, Compass, BookOpen } from 'lucide-react';

interface UseCase {
  icon: React.ReactNode;
  title: string;
  persona: string;
  scenario: string;
  result: string;
  sourceHint: string;
}

const USE_CASES: UseCase[] = [
  {
    icon: <Shield className="w-5 h-5" />,
    title: 'The design reviewer',
    persona: 'For engineers and architects',
    scenario: 'Ingest your company\'s security RFCs and architecture talks. Run your next PR or design doc through it before sending to the team.',
    result: 'Gets a line-by-line critique that catches the same issues a senior reviewer would — citing the specific RFC sections and talk timestamps.',
    sourceHint: '8 sources · OAuth2 & Zero Trust',
  },
  {
    icon: <GraduationCap className="w-5 h-5" />,
    title: 'The personalized coach',
    persona: 'For learners and practitioners',
    scenario: 'Ingest a 10-hour video masterclass on portrait photography. Ask it to evaluate your work.',
    result: 'Gets specific feedback like "your key light is at 6 o\'clock — move it to 2 o\'clock" with the exact timestamp where the instructor explains why.',
    sourceHint: '14 sources · Portrait Lighting Masterclass',
  },
  {
    icon: <Compass className="w-5 h-5" />,
    title: 'The decision memo',
    persona: 'For founders and operators',
    scenario: 'Collect investor memos, SaaS metrics talks, and competitive analysis into one collection. Ask it to evaluate your two expansion options.',
    result: 'Gets a conditional recommendation with explicit trade-offs, sourced from your trusted material — not generic advice from training data.',
    sourceHint: '42 sources · Startup Strategy',
  },
  {
    icon: <BookOpen className="w-5 h-5" />,
    title: 'The institutional runbook',
    persona: 'For teams and organizations',
    scenario: 'Keep team incident recordings and postmortems alive as a permanent collection. When a new engineer joins, point them at it.',
    result: 'New hires get onboarded with the real war stories and procedures, not a stale wiki page nobody updates.',
    sourceHint: '29 sources · Incident Runbooks',
  },
];

export const UseCasesSection = () => {
  return (
    <section id="examples" className="py-20 md:py-28 bg-warm-50 border-t border-warm-100">
      <div className="section-container">
        <div className="max-w-2xl mx-auto text-center mb-14">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-warm-900 tracking-tight leading-tight mb-4">
            Built for people who do real work<br />with their knowledge.
          </h2>
          <p className="text-base sm:text-lg text-warm-500 leading-relaxed">
            The same system works across disciplines. What changes is the content you trust.
          </p>
        </div>

        <div className="max-w-4xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-5">
          {USE_CASES.map((uc) => (
            <div
              key={uc.title}
              className="p-6 rounded-xl bg-white border border-warm-200 card-shadow hover:card-shadow-hover transition-shadow duration-200 group"
            >
              <div className="flex items-start gap-3 mb-4">
                <div className="p-2 rounded-lg bg-warm-100 text-warm-500 group-hover:text-amber-600 transition-colors shrink-0">
                  {uc.icon}
                </div>
                <div>
                  <h3 className="text-[15px] font-bold text-warm-900">{uc.title}</h3>
                  <p className="text-[12px] text-warm-400">{uc.persona}</p>
                </div>
              </div>

              <p className="text-[13px] text-warm-600 leading-relaxed mb-3">
                {uc.scenario}
              </p>

              <p className="text-[13px] text-warm-500 leading-relaxed mb-4 pl-3 border-l-2 border-amber-200 italic">
                {uc.result}
              </p>

              <p className="text-[11px] font-mono text-warm-400">
                {uc.sourceHint}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};
