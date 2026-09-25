import { useState, useEffect } from 'react';
import { Menu, X, ArrowRight } from 'lucide-react';

export const Navbar = () => {
  const [isScrolled, setIsScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setIsScrolled(window.scrollY > 8);
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const links = [
    { label: 'How it works', href: '#how-it-works' },
    { label: 'Examples', href: '#examples' },
    { label: 'Why it\'s different', href: '#different' },
    { label: 'Prompts', href: '#prompts' },
  ];

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-200 ${
        isScrolled
          ? 'bg-[#FBFBFA]/90 backdrop-blur-md border-b border-warm-200 shadow-sm'
          : 'bg-transparent'
      }`}
    >
      <div className="section-container flex items-center justify-between h-16">
        {/* Logo */}
        <a href="#" className="flex items-center gap-2.5 text-warm-900 font-semibold text-[15px] tracking-tight">
          <span className="text-xl">📚</span>
          <span>Expertise Compiler</span>
          <span className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-amber-100 text-amber-700 border border-amber-200">
            Early Access
          </span>
        </a>

        {/* Desktop Nav */}
        <nav className="hidden md:flex items-center gap-8">
          {links.map((link) => (
            <a
              key={link.label}
              href={link.href}
              className="text-[13px] text-warm-500 hover:text-warm-900 transition-colors font-medium"
            >
              {link.label}
            </a>
          ))}
        </nav>

        {/* CTA */}
        <div className="hidden md:flex items-center gap-3">
          <a
            href="#waitlist"
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-warm-900 text-white text-[13px] font-medium hover:bg-warm-800 transition-colors"
          >
            Get early access
            <ArrowRight className="w-3.5 h-3.5" />
          </a>
        </div>

        {/* Mobile toggle */}
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="md:hidden p-2 text-warm-600 hover:text-warm-900"
          aria-label="Toggle menu"
        >
          {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
      </div>

      {/* Mobile Menu */}
      {mobileOpen && (
        <div className="md:hidden bg-white border-b border-warm-200 px-6 pb-4">
          {links.map((link) => (
            <a
              key={link.label}
              href={link.href}
              onClick={() => setMobileOpen(false)}
              className="block py-2.5 text-sm text-warm-600 hover:text-warm-900 font-medium"
            >
              {link.label}
            </a>
          ))}
          <a
            href="#waitlist"
            onClick={() => setMobileOpen(false)}
            className="mt-2 inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-warm-900 text-white text-sm font-medium"
          >
            Get early access
            <ArrowRight className="w-3.5 h-3.5" />
          </a>
        </div>
      )}
    </header>
  );
};
