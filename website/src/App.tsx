import { Navbar } from './components/Navbar';
import { HeroSection } from './components/HeroSection';
import { ProblemSection } from './components/ProblemSection';
import { SolutionSection } from './components/SolutionSection';
import { UseCasesSection } from './components/UseCasesSection';
import { ComparisonSection } from './components/ComparisonSection';
import { PromptsSection } from './components/PromptsSection';
import { WaitlistSection } from './components/WaitlistSection';
import { Footer } from './components/Footer';

export function App() {
  return (
    <div className="min-h-screen bg-[#FBFBFA] text-warm-900">
      <Navbar />
      <main>
        <HeroSection />
        <ProblemSection />
        <SolutionSection />
        <UseCasesSection />
        <ComparisonSection />
        <PromptsSection />
        <WaitlistSection />
      </main>
      <Footer />
    </div>
  );
}

export default App;
