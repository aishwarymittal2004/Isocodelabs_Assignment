import aranya from "@/assets/project-aranya.jpg";
import vista from "@/assets/project-vista.jpg";
import interior from "@/assets/interior.jpg";
import hero from "@/assets/hero.jpg";

export const images = { aranya, vista, interior, hero };

export type Config = { type: "2 BHK" | "3 BHK"; carpet: string; price: string; available: number };
export type Project = {
  id: "aranya" | "vista";
  name: string;
  tagline: string;
  locality: string;
  image: string;
  gallery: string[];
  priceRange: string;
  possession: string;
  units: number;
  towers: number;
  rera: string;
  configs: Config[];
  amenities: string[];
  pending: string[];
};

export const projects: Project[] = [
  {
    id: "aranya",
    name: "Aranya Residences",
    tagline: "Low-rise homes set within a two-acre courtyard garden.",
    locality: "Shela, Ahmedabad",
    image: aranya,
    gallery: [aranya, interior, hero],
    priceRange: "₹65 L – ₹92 L",
    possession: "Dec 2027",
    units: 180,
    towers: 3,
    rera: "PR/GJ/AHMEDABAD/XXXX/2025 (illustrative)",
    configs: [
      { type: "2 BHK", carpet: "742 sq ft", price: "₹65 L – ₹72 L", available: 34 },
      { type: "3 BHK", carpet: "1,064 sq ft", price: "₹84 L – ₹92 L", available: 21 },
    ],
    amenities: ["Courtyard garden", "Clubhouse", "Lap pool", "Children's play area", "Co-working lounge", "EV charging"],
    pending: ["Final maintenance charges", "Parking allocation policy"],
  },
  {
    id: "vista",
    name: "Vista Heights",
    tagline: "A 24-storey tower with a sky garden and open city views.",
    locality: "Science City Road, Ahmedabad",
    image: vista,
    gallery: [vista, interior, hero],
    priceRange: "₹78 L – ₹1.2 Cr",
    possession: "Jun 2028",
    units: 240,
    towers: 2,
    rera: "PR/GJ/AHMEDABAD/YYYY/2025 (illustrative)",
    configs: [
      { type: "2 BHK", carpet: "810 sq ft", price: "₹78 L – ₹88 L", available: 41 },
      { type: "3 BHK", carpet: "1,240 sq ft", price: "₹1.02 Cr – ₹1.2 Cr", available: 18 },
    ],
    amenities: ["Sky garden", "Infinity pool", "Gym", "Indoor games", "Banquet hall", "24×7 security"],
    pending: ["Floor-rise pricing", "Club membership fees"],
  },
];

export const getProject = (id: string) => projects.find((p) => p.id === id);

export const slotTimes = ["10:00 AM", "11:30 AM", "1:00 PM", "3:00 PM", "4:30 PM", "6:00 PM"];
/** Deterministic illustrative availability: returns unavailable slot indexes for a day offset. */
export const unavailableFor = (day: number) => [(day * 2) % 6, (day * 5 + 1) % 6].filter((_, i) => i < (day % 3) + 1);
/** One slot that looks free but conflicts on confirm, to demo recovery. */
export const conflictSlot = (day: number) => (day * 3 + 2) % 6;

export type LeadStatus = "New" | "Contacted" | "Handoff requested" | "Visit booked" | "Visited" | "Not interested";
export type Concern = { kind: "Explicit" | "Needs clarification" | "Mismatch"; topic: string; evidence: string };
export type Lead = {
  id: string;
  name: string;
  source: "Website" | "99acres" | "MagicBricks" | "Instagram" | "Walk-in" | "Referral";
  project: Project["id"];
  config: string;
  budget: string;
  status: LeadStatus;
  exec: string;
  consent: "Granted" | "Not given" | "Withdrawn";
  duplicate?: boolean;
  received: string;
  firstResponse: string;
  concerns: Concern[];
  transcript: { from: "buyer" | "ai" | "exec"; text: string; time: string }[];
  handoff?: string;
  nextAction: string;
};

export const executives = ["Riya Shah", "Karan Patel", "Neha Desai", "Arjun Mehta", "Pooja Trivedi"];

export const leads: Lead[] = [
  {
    id: "L-2041", name: "Buyer A. (sample)", source: "Website", project: "aranya", config: "3 BHK", budget: "₹85–90 L",
    status: "Handoff requested", exec: "Riya Shah", consent: "Granted", received: "Today, 9:12 AM", firstResponse: "2 min (AI)",
    concerns: [
      { kind: "Explicit", topic: "Home loan pending", evidence: "“I like the 3 BHK, but my home loan is still pending.”" },
      { kind: "Needs clarification", topic: "Possession timeline", evidence: "“Dec 2027 feels a little far.”" },
    ],
    transcript: [
      { from: "buyer", text: "What is the price for 3 BHK in Aranya?", time: "9:12" },
      { from: "ai", text: "The published range for the 3 BHK (1,064 sq ft carpet) is ₹84 L – ₹92 L.", time: "9:12" },
      { from: "buyer", text: "I like the 3 BHK, but my home loan is still pending.", time: "9:14" },
      { from: "ai", text: "That's an important step. I can share approved payment-plan information, or connect you with someone from the team.", time: "9:14" },
      { from: "buyer", text: "Dec 2027 feels a little far. Can I talk to someone?", time: "9:16" },
    ],
    handoff: "Buyer interested in 3 BHK at Aranya, budget ₹85–90 L. Loan approval pending (stated). Asked about possession date — unclear whether timeline is a blocker. Prefers a call after 6 PM.",
    nextAction: "Call after 6 PM; share payment plan and construction-linked schedule.",
  },
  {
    id: "L-2040", name: "Buyer B. (sample)", source: "99acres", project: "vista", config: "2 BHK", budget: "₹80 L",
    status: "Visit booked", exec: "Karan Patel", consent: "Granted", received: "Today, 8:40 AM", firstResponse: "1 min (AI)",
    concerns: [{ kind: "Needs clarification", topic: "Commute", evidence: "“How far is it from SG Highway?”" }],
    transcript: [
      { from: "buyer", text: "How far is it from SG Highway?", time: "8:40" },
      { from: "ai", text: "Vista Heights is on Science City Road. I don't have verified travel times, so I'd rather not guess — the team can share route details during a visit.", time: "8:41" },
      { from: "buyer", text: "OK, book a visit on Saturday.", time: "8:43" },
    ],
    nextAction: "Confirm Saturday 11:30 AM visit by WhatsApp a day before.",
  },
  {
    id: "L-2039", name: "Buyer C. (sample)", source: "Instagram", project: "aranya", config: "2 BHK", budget: "₹55 L",
    status: "Contacted", exec: "Neha Desai", consent: "Granted", duplicate: true, received: "Yesterday", firstResponse: "4 min (AI)",
    concerns: [{ kind: "Mismatch", topic: "Budget below published range", evidence: "“My max budget is 55 lakh.”" }],
    transcript: [
      { from: "buyer", text: "My max budget is 55 lakh. Anything in Aranya?", time: "18:02" },
      { from: "ai", text: "The lowest published price at Aranya is ₹65 L, so it may not fit that budget. I can still share details if useful.", time: "18:02" },
    ],
    nextAction: "Possible duplicate of L-1987 — merge before follow-up.",
  },
  {
    id: "L-2038", name: "Buyer D. (sample)", source: "MagicBricks", project: "vista", config: "3 BHK", budget: "₹1.1 Cr",
    status: "New", exec: "Unassigned", consent: "Not given", received: "Yesterday", firstResponse: "—",
    concerns: [], transcript: [{ from: "buyer", text: "Enquiry form submitted (no message).", time: "16:20" }],
    nextAction: "Assign executive; contact only through portal until consent is given.",
  },
  {
    id: "L-2037", name: "Buyer E. (sample)", source: "Referral", project: "aranya", config: "3 BHK", budget: "₹90 L",
    status: "Visited", exec: "Arjun Mehta", consent: "Granted", received: "2 days ago", firstResponse: "11 min",
    concerns: [{ kind: "Explicit", topic: "Wants east-facing unit", evidence: "“We prefer east facing.”" }],
    transcript: [{ from: "buyer", text: "We prefer east facing. Are any left?", time: "11:05" }],
    nextAction: "Share east-facing 3 BHK inventory list.",
  },
  {
    id: "L-2036", name: "Buyer F. (sample)", source: "Walk-in", project: "vista", config: "2 BHK", budget: "₹85 L",
    status: "Not interested", exec: "Pooja Trivedi", consent: "Withdrawn", received: "3 days ago", firstResponse: "6 min",
    concerns: [], transcript: [{ from: "buyer", text: "Please stop contacting me, thanks.", time: "10:00" }],
    nextAction: "No action — consent withdrawn.",
  },
];

export const getLead = (id: string) => leads.find((l) => l.id === id);

export type Visit = { id: string; lead: string; project: Project["id"]; date: string; time: string; exec: string; status: "Upcoming" | "Confirmed" | "Cancelled" | "Attended" | "No-show" };
export const visits: Visit[] = [
  { id: "SV-3108", lead: "L-2040", project: "vista", date: "Sat, 7 Nov", time: "11:30 AM", exec: "Karan Patel", status: "Confirmed" },
  { id: "SV-3107", lead: "L-2041", project: "aranya", date: "Sun, 8 Nov", time: "4:30 PM", exec: "Riya Shah", status: "Upcoming" },
  { id: "SV-3101", lead: "L-2037", project: "aranya", date: "Mon, 2 Nov", time: "1:00 PM", exec: "Arjun Mehta", status: "Attended" },
  { id: "SV-3099", lead: "L-2036", project: "vista", date: "Sun, 1 Nov", time: "10:00 AM", exec: "Pooja Trivedi", status: "Cancelled" },
  { id: "SV-3095", lead: "L-2039", project: "aranya", date: "Sat, 31 Oct", time: "3:00 PM", exec: "Neha Desai", status: "No-show" },
];

export const sources = [
  { name: "Website + AI", leads: 980, response: "2 min", booked: 128, visited: 94 },
  { name: "99acres", leads: 760, response: "6 h", booked: 52, visited: 36 },
  { name: "MagicBricks", leads: 540, response: "9 h", booked: 31, visited: 20 },
  { name: "Instagram", leads: 450, response: "14 h", booked: 18, visited: 11 },
  { name: "Referral", leads: 170, response: "1 h", booked: 24, visited: 19 },
  { name: "Walk-in", leads: 100, response: "—", booked: 22, visited: 22 },
];
