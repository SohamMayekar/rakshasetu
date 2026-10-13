export const navLinks = [
  { href: "#top", label: "Overview" },
  { href: "#how-it-works", label: "How it works" },
  { href: "#pillars", label: "Core pillars" },
  { href: "#stakeholders", label: "Who it serves" },
  { href: "#case-study", label: "Live case dossier" },
  { href: "#field-stories", label: "Field operations" },
  { href: "#faq", label: "Questions" },
];

export const hero = {
  eyebrow: "District Disaster Response Infrastructure · India",
  headingLines: ["One family. One team.", "Until safe."],
  body: "Every call for help—flood, cyclone, landslide, building collapse, or fire—reaches the district control room once, gets one response crew, and is followed until the family confirms they are safe.",
  primaryCta: { label: "I need help", href: "/r" },
  secondaryCta: { label: "Control Room", href: "/login" },
  responderCta: { label: "Rescue Team App", href: "/responder" },
  featured: {
    label: "Active Demonstration Incident",
    title: "Bihar Floods · Gopalganj District Desk",
    badge: "Boat 5 Active",
    href: "/login",
  },
};

export const metricsIntro = {
  tag: "ACCOUNTABILITY",
  heading: "Numbers that protect lives, not just statistics.",
  body: "During severe floods and cyclones, the critical point of failure is dropped calls, duplicate crew dispatch, and silent teams. RakshaSetu ensures every distress report is accounted for.",
};

export const metrics = [
  {
    label: "Caller Words Preserved",
    value: 100,
    suffix: "%",
    detail: "Every extracted fact cites the caller's verbatim words beside it.",
  },
  {
    label: "Lost Distress Requests",
    value: 0,
    suffix: "",
    detail: "Automated deduplication merges separate calls into one household.",
  },
  {
    label: "Intake-to-Dispatch",
    value: 60,
    suffix: "s",
    detail: "Rapid triage turnaround from citizen report to boat assignment.",
  },
  {
    label: "Intake Channels",
    value: 4,
    suffix: "",
    detail: "Spoken voice calls, forwarded SMS, spreadsheets, and radio logs.",
  },
];

export const statement = {
  id: "doctrine",
  tag: "THE CORE DOCTRINE",
  lead: "A request for help is never just a ticket.",
  accent: "Calls, forwards and spreadsheets",
  rest: "converge into one accountable family dossier, and the mission closes only when",
  accentTwo: "the family confirms",
  tail: "they are safe.",
};

export const servicesIntro = {
  tag: "THE SIX PILLARS",
  heading: "Six operational disciplines of modern disaster command.",
  body: "Built for the frantic first 72 hours of sudden-onset catastrophe. Tested against real emergency workflows in Indian districts.",
};

export const pillars = [
  {
    slug: "voice-intake",
    number: "01",
    name: "Voice & Multi-Lingual Intake",
    summary: "Citizens speak naturally in Hindi, English, or dialect without an app or account. Speech-to-text preserves original phrasing verbatim.",
    points: ["No password required", "Zero app install", "Understands regional dialects", "Accessible from basic smartphones"],
    image: "pillar.1",
  },
  {
    slug: "family-deduplication",
    number: "02",
    name: "One Family, One Case",
    summary: "When multiple relatives call about the same stranded household, reports are clustered into one dossier to prevent wasteful duplicate boat runs.",
    points: ["Automated household grouping", "Preserves all caller numbers", "Unified count of people & infants", "Clear linkage evidence"],
    image: "pillar.2",
  },
  {
    slug: "landmark-search",
    number: "03",
    name: "Honest Landmark Circles",
    summary: "When GPS pins fail in waist-deep water, landmark names (e.g., 'near primary school') draw an honest search radius rather than pretend exact coordinates.",
    points: ["OpenStreetMap landmark cross-ref", "Configurable search radiuses", "Visual water contour mapping", "Realistic search perimeters"],
    image: "pillar.3",
  },
  {
    slug: "field-pwa",
    number: "04",
    name: "Offline Field Crew PWA",
    summary: "Rescue boats and SDRF crews receive assigned cases on low-spec phones. Functions smoothly through intermittent network dropouts.",
    points: ["Works with weak 2G signal", "One-tap status updates", "Survivor roster tracking", "Battery-efficient high contrast"],
    image: "pillar.4",
  },
  {
    slug: "silence-watchdog",
    number: "05",
    name: "The Silence Watchdog",
    summary: "If an assigned rescue team goes quiet for over 30 minutes, the control room desk triggers an alert. Silence is treated as an active crisis.",
    points: ["Automated overdue timers", "Visual desk escalations", "Never silently reassigned", "Duty officer accountability"],
    image: "pillar.5",
  },
  {
    slug: "family-confirmation",
    number: "06",
    name: "Family Confirmation Loop",
    summary: "Rescuers record who they brought out, but the final mark of safety requires the citizen or family to confirm everyone is secure.",
    points: ["Two-way confirmation gate", "Survivor count audit", "Closure requires human sign-off", "Immutable timestamp log"],
    image: "pillar.6",
  },
];

export const stakeholderCards = [
  {
    index: "01",
    label: "FOR CITIZENS IN DANGER",
    title: "Zero passwords. Speak or type from any phone.",
    body: "When floodwaters rise in the middle of the night, no one should have to download an app or create an account. One link allows anyone to speak or write what is happening, where they are, and how many people need help.",
    points: [
      "Zero account registration",
      "Speak in Hindi or English",
      "Live SMS tracking link",
      "Family safety confirmation",
    ],
    image: "stack.1",
    action: { label: "Ask for help now", href: "/r" },
  },
  {
    index: "02",
    label: "FOR RESCUE BOATS & SDRF/NDRF",
    title: "Offline-first responder console for boats and ground crews.",
    body: "Field teams navigate directly to honest search perimeters, review caller notes (elderly, diabetic, infants), mark who was boarded, and log evacuation points even when the cellular tower goes offline.",
    points: [
      "Offline cache & sync",
      "Exact medical notes & headcounts",
      "One-tap victim accounting",
      "Live radio & battery check-in",
    ],
    image: "stack.2",
    action: { label: "Open team app", href: "/responder" },
  },
  {
    index: "03",
    label: "FOR DISTRICT DUTY OFFICERS",
    title: "One unified command desk for the entire disaster.",
    body: "Duty officers monitor triage queues ordered by urgent human need (P1 to P4), watch overdue team promises on an interactive GIS map, and coordinate district resources without losing sight of any family.",
    points: [
      "National & district layer maps",
      "Promise staleness alerts",
      "Spreadsheet & CSV bulk ingest",
      "Full auditable decision trail",
    ],
    image: "stack.3",
    action: { label: "Open control room", href: "/login" },
  },
];

export const marqueeItems = [
  "ONE FAMILY · ONE CASE",
  "ZERO CITIZEN PASSWORDS",
  "HONEST LANDMARK SEARCH CIRCLES",
  "VOICE INTAKE IN HINDI & ENGLISH",
  "SILENCE STAYS VISIBLE",
  "FAMILY CONFIRMS SAFETY",
  "AUDITABLE WORDS BESIDE FACTS",
  "DISTRICT COMMAND CONTROL ROOM",
];

export const fieldStories = [
  {
    issue: "GOPALGANJ · FLOOD RUN 04",
    role: "District Duty Officer",
    author: "Rakesh Verma, Sub-Divisional Magistrate",
    pullQuote: "“In the 2024 flood, we had 4,000 spreadsheet rows and no idea which family was already rescued. RakshaSetu turned that chaotic pile into 800 accountable family cases in hours.”",
    summary: "Commanded the Gandak River basin flood control room across 14 inundated panchayats.",
    year: "2026",
  },
  {
    issue: "SDRF UNIT 2 · BRAVO BOAT",
    role: "Boat Commander",
    author: "Inspector Arvind Kumar, SDRF",
    pullQuote: "“When the network cut out on the river, the app held the offline search circle. We found the six family members right behind the submerged panchayat bhavan.”",
    summary: "Led 18 boat sorties across 48 continuous hours of flood evacuation operations.",
    year: "2026",
  },
  {
    issue: "CITIZEN CONFIRMATION · THAWE",
    role: "Rescued Citizen",
    author: "Sunita Devi & Family",
    pullQuote: "“I spoke my message into my brother's phone in Hindi. Two hours later the boat team called my name. When we reached dry land, I pressed 'Safe' on the message.”",
    summary: "Evacuated with 4 family members and an elderly grandmother during water surge.",
    year: "2026",
  },
];

export const faqs = [
  {
    question: "What exactly is RakshaSetu?",
    answer: "RakshaSetu is a district control room's rescue coordination platform built specifically for the critical first two weeks of a disaster. It unifies voice calls, text forwards, volunteer spreadsheets, and radio logs into single family dossiers and tracks each case until the family confirms they are safe.",
  },
  {
    question: "Does AI make life-or-death decisions on who gets rescued?",
    answer: "No. In RakshaSetu, AI is strictly bounded to speech-to-text transcription and extracting structured facts alongside the caller's verbatim words. Priority is determined by deterministic safety rules, and actual rescue dispatch decisions are always made by human officers in the control room.",
  },
  {
    question: "Can someone ask for help without registering or signing in?",
    answer: "Yes. The public reporter interface (/r) is completely frictionless. Citizens do not need an account, password, or verification code. Anyone in distress can speak or type their emergency directly from any phone browser.",
  },
  {
    question: "How does RakshaSetu find people without accurate GPS map pins?",
    answer: "During floods or power outages, GPS signals frequently fail. RakshaSetu identifies mentioned landmarks (such as schools, temples, mobile towers) and matches them against OpenStreetMap data to draw an honest search circle rather than pretending to possess an exact coordinate.",
  },
  {
    question: "What happens if a field rescue boat loses cellular connection?",
    answer: "The rescue crew's web application (/responder) is an offline-capable Progressive Web App (PWA). It caches assignments, map boundaries, and family member details locally on the device, allowing crews to continue rescue operations and sync their logs once connection is restored.",
  },
  {
    question: "Is the data in this demonstration real?",
    answer: "All names, phone numbers, and family stories shown in this demonstration are synthetic to safeguard privacy. Geographic coordinates and landmark names reference real OpenStreetMap locations in Bihar and other vulnerable flood plains.",
  },
];

export const footerContent = {
  tagline: "One family. One team. Until safe.",
  summary: "India's district emergency coordination platform. Connecting citizen distress calls with accountable rescue teams until every family is verified secure.",
  hotlines: [
    { label: "National Emergency Number", number: "112" },
    { label: "Disaster Management Helpline", number: "1070" },
    { label: "State Emergency Desk", number: "1077" },
  ],
  links: [
    { label: "Ask for help (Citizen)", href: "/r" },
    { label: "Rescue Team App", href: "/responder" },
    { label: "Control Room Login", href: "/login" },
    { label: "All Incidents Map", href: "/?door=1" },
  ],
};
