import { useState } from 'react';
import { ChevronRight } from 'lucide-react';

interface PromptExample {
  prompt: string;
  collection: string;
  result: string;
}

const PROMPTS: PromptExample[] = [
  {
    prompt: 'Save these videos as Enterprise Architecture.',
    collection: 'Enterprise Architecture · 3 sources added',
    result: 'Saved 3 files (142 segments) as "Enterprise Architecture." Active revision: 1. Ready for review, teaching, or decision queries whenever you need it.',
  },
  {
    prompt: 'Use my Enterprise Architecture collection to review this design.',
    collection: 'Enterprise Architecture · 8 sources',
    result: 'Your session cache in §3.2 omits tenant isolation. The security RFC (§8.4) requires verifying token claims before upstream proxying. Recommend adding Redis-based revocation checks or limiting cache TTL to ≤ 60 seconds.',
  },
  {
    prompt: 'Use the same collection to teach a junior architect about identity checks.',
    collection: 'Enterprise Architecture · 8 sources',
    result: 'Lesson: mTLS authenticates the node, but bearer tokens authenticate the principal. If your service trusts any mesh packet without inspecting the JWT, a compromised sidecar exposes all user data. Exercise: examine gateway-stub.go line 48 and identify the missing scope validation.',
  },
  {
    prompt: 'Help me decide between these two markets using my startup strategy collection.',
    collection: 'Startup Strategy · 42 sources',
    result: 'Recommendation: Prioritize Mid-Market US. Source evidence shows enterprise sales cycles in EMEA require on-prem telemetry proxies that increase support costs by 40% when engineering headcount is under 15. Two sources agree on this threshold; one dissents for markets with existing channel partners.',
  },
  {
    prompt: 'Turn these photography tutorials into a coach that critiques my portraits.',
    collection: 'Portrait Lighting · 14 sources',
    result: '1. Handheld blur detected: 1/60s on an 85mm lens exceeds the handheld threshold. Increase ISO by one stop to reach 1/160s. 2. Key light angle: catchlight is at 6 o\'clock rather than 10 or 2 o\'clock, flattening facial contours. Move your diffusion scrim 45° off-axis.',
  },
  {
    prompt: 'Use this product strategy collection to improve my homepage.',
    collection: 'Product & Positioning · 6 sources',
    result: 'Your hero headline claims "next generation AI platform." Source #4 (Stanford lecture, 18:20) notes that technical buyers bounce when the problem isn\'t framed in daily work terms. Replace with a direct outcome. Also: move social proof above the fold per source #2 recommendation.',
  },
];

export const PromptsSection = () => {
  const [selected, setSelected] = useState(0);

  const current = PROMPTS[selected];

  return (
    <section id="prompts" className="py-20 md:py-28 bg-warm-900 text-white">
      <div className="section-container">
        <div className="max-w-2xl mx-auto text-center mb-14">
          <h2 className="text-3xl sm:text-4xl font-extrabold tracking-tight leading-tight mb-4 text-white">
            Simple prompts. Real deliverables.
          </h2>
          <p className="text-base sm:text-lg text-warm-400 leading-relaxed">
            You don't configure a pipeline or fill out forms. Talk naturally and get actual work back.
          </p>
        </div>

        <div className="max-w-4xl mx-auto">
          {/* Prompt pills */}
          <div className="flex flex-wrap gap-2 mb-8 justify-center">
            {PROMPTS.map((p, i) => (
              <button
                key={i}
                onClick={() => setSelected(i)}
                className={`px-3.5 py-2 rounded-lg text-[12px] sm:text-[13px] font-medium text-left transition-colors border ${
                  selected === i
                    ? 'bg-white/10 border-white/20 text-white'
                    : 'bg-transparent border-white/10 text-warm-400 hover:text-white hover:border-white/20'
                }`}
              >
                "{p.prompt.length > 50 ? p.prompt.slice(0, 50) + '…' : p.prompt}"
              </button>
            ))}
          </div>

          {/* Selected prompt & result */}
          <div className="rounded-xl border border-white/10 overflow-hidden">
            {/* User prompt */}
            <div className="px-6 py-4 bg-white/5 border-b border-white/10">
              <div className="flex items-start gap-2">
                <ChevronRight className="w-4 h-4 text-warm-400 mt-0.5 shrink-0" />
                <div>
                  <p className="text-[14px] sm:text-[15px] font-mono text-white font-medium">
                    "{current.prompt}"
                  </p>
                  <p className="text-[12px] text-warm-500 mt-1 font-mono">
                    {current.collection}
                  </p>
                </div>
              </div>
            </div>

            {/* Result */}
            <div className="px-6 py-5 bg-warm-900">
              <p className="text-[13px] sm:text-[14px] text-warm-300 leading-relaxed whitespace-pre-line">
                {current.result}
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
