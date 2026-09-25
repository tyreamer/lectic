export const Footer = () => {
  return (
    <footer className="py-12 border-t border-warm-200 bg-white">
      <div className="section-container">
        <div className="flex flex-col md:flex-row items-center justify-between gap-6">
          {/* Brand */}
          <div className="flex items-center gap-2 text-warm-500 text-[14px]">
            <span className="text-lg">📚</span>
            <span className="font-medium text-warm-700">Expertise Compiler</span>
            <span className="text-warm-300">·</span>
            <span>Your knowledge, ready to work</span>
          </div>

          {/* Links */}
          <div className="flex items-center gap-6 text-[13px] text-warm-400">
            <a href="#how-it-works" className="hover:text-warm-700 transition-colors">How it works</a>
            <a href="#examples" className="hover:text-warm-700 transition-colors">Examples</a>
            <a href="#different" className="hover:text-warm-700 transition-colors">Why it's different</a>
            <a href="#waitlist" className="hover:text-warm-700 transition-colors">Get access</a>
          </div>
        </div>

        <div className="mt-8 pt-6 border-t border-warm-100 flex flex-col sm:flex-row items-center justify-between gap-4 text-[12px] text-warm-400">
          <p>&copy; {new Date().getFullYear()} Expertise Compiler. MIT Licensed.</p>
          <p>Works with Codex, Claude Code, and local LLMs. No hosted service required.</p>
        </div>
      </div>
    </footer>
  );
};
