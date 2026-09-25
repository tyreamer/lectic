import urllib.request
import re
import sys

# Try multiple ports
for port in [4175, 4176, 4177]:
    try:
        html = urllib.request.urlopen(f'http://localhost:{port}/').read().decode('utf-8')
        break
    except Exception:
        html = None

if html is None:
    print("Could not connect to any preview server")
    sys.exit(1)

print(f"Connected on port {port} (index.html: {len(html)} bytes)")

required = [
    "Your knowledge, ready to work",
    "Expertise Compiler",
    "without starting over every time",
    "Content is everywhere",
    "Usable expertise is not",
    "Save it once. Put it to work forever",
    "Built for people who do real work",
    "Why this isn't just chat",
    "Simple prompts. Real deliverables",
    "Your knowledge shouldn",
    "start from scratch",
    "Save these videos as Enterprise Architecture",
    "Use my Enterprise Architecture collection to review this design",
    "Help me decide between these two markets using my startup strategy collection",
    "Turn these photography tutorials into a coach that critiques my portraits",
    "Use this product strategy collection to improve my homepage",
    "The design reviewer",
    "The personalized coach",
    "The decision memo",
    "The institutional runbook",
    "Same knowledge. New job. No rebuilding context",
    "Request an invite",
]

# Load JS bundle content too
assets = re.findall(r'(?:src|href)="(/assets/[^"]+)"', html)
bundle_text = html
for a in assets:
    res = urllib.request.urlopen(f'http://localhost:{port}' + a)
    content = res.read().decode('utf-8', errors='ignore')
    print(f"  Asset {a}: {res.status}, {len(content)} bytes")
    bundle_text += "\n" + content

missing = []
for req in required:
    if req.lower() in bundle_text.lower():
        print(f"  [PASS] {req}")
    else:
        print(f"  [FAIL] {req}")
        missing.append(req)

# Verify NO cyberpunk slop remains
slop_terms = [
    "glow-cyan",
    "glow-violet",
    "animate-pulse-glow",
    "glass-panel-glow",
    "particle",
    "scanline",
    "holographic",
    "cyberpunk",
    "neon",
    "compile intelligence in real time",
    "universal compiler for human expertise",
    "unlock",
    "amplify",
    "AI-powered",
    "endless possibilities",
]

found_slop = []
for term in slop_terms:
    if term.lower() in bundle_text.lower():
        found_slop.append(term)

if found_slop:
    print(f"\n  [WARN] Found leftover cyberpunk/slop terms: {found_slop}")

if missing:
    print(f"\nFAILED — missing content: {missing}")
    sys.exit(1)

print(f"\nALL {len(required)} CHECKS PASSED!")
sys.exit(0)
