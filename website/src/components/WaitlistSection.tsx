import { useState } from 'react';
import { ArrowRight, Check } from 'lucide-react';

export const WaitlistSection = () => {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !email.includes('@')) return;
    // In a real app, this would POST to an API
    setSubmitted(true);
  };

  return (
    <section id="waitlist" className="py-20 md:py-28 border-t border-warm-100">
      <div className="section-container">
        <div className="max-w-lg mx-auto text-center">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-warm-900 tracking-tight leading-tight mb-4">
            Your knowledge shouldn't<br />start from scratch.
          </h2>
          <p className="text-base sm:text-lg text-warm-500 leading-relaxed mb-8">
            We're currently in private alpha with engineers, researchers, and operators. Drop your email to join the queue.
          </p>

          {!submitted ? (
            <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row gap-3 max-w-md mx-auto">
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@work.com"
                required
                className="flex-1 px-4 py-3 rounded-lg border border-warm-200 bg-white text-warm-900 text-[14px] placeholder-warm-400 outline-none focus:border-warm-400 focus:ring-2 focus:ring-warm-200 transition-all"
              />
              <button
                type="submit"
                className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-lg bg-warm-900 text-white text-[14px] font-semibold hover:bg-warm-800 transition-colors shrink-0 cursor-pointer"
              >
                Request invite
                <ArrowRight className="w-4 h-4" />
              </button>
            </form>
          ) : (
            <div className="flex items-center justify-center gap-2 text-[15px] text-warm-700 font-medium py-3">
              <Check className="w-5 h-5 text-green-600" />
              <span>You're on the list. We'll be in touch soon.</span>
            </div>
          )}

          <p className="text-[12px] text-warm-400 mt-4">
            No spam. Private alpha invites sent weekly.
          </p>
        </div>
      </div>
    </section>
  );
};
