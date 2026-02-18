# Demo Video Guide — 3 Minutes

## Assets

**Screen recordings (already captured):**
- Web app: literature review
- Web app: claim verification
- Slack: /research
- Slack: /check-claim
- Claude Code: MCP research

**Slides (PPT — 4 existing + 1 to create):**
- Slide 0: **Title slide** (CREATE THIS — "Research Orchestration System", subtitle, your name, built with line, stats line)
- Slide 1: Research orchestration loop architecture (2 agents)
- Slide 2: Research agent detail
- Slide 3: Peer review agent detail
- Slide 4: Claim verification agent architecture

**Slides to use in video:** Slide 0, Slide 1, Slide 4
**Slides to skip:** Slide 2 and 3 — too granular for 3 minutes. Judges can see these in the repo.

**Optional:** Create a Slide 5 closing slide — same as title slide but swap subtitle for key stats: "3 agents · 21-34 tool calls · ~98% citation accuracy · 4 interfaces"

---

## Software

- **Recording slides + face:** OBS Studio or just PowerPoint's built-in "Record Slide Show" (simpler — records your face + slides + audio together, exports as MP4)
- **Editing:** CapCut (free, simple speed ramping + text overlays + splicing clips)

---

## Video Structure

```
0:00 ──── Slides + face: Title + Problem ────────── 20 sec
0:20 ──── Slides + face: Research Loop Architecture  25 sec
0:45 ──── Screen rec: Web app literature review ──── 40 sec
1:25 ──── Slides + face: Claim Verif Architecture ── 15 sec
1:40 ──── Screen rec: Web app claim verification ─── 30 sec
2:10 ──── Screen rec: Slack + Claude Code MCP ────── 30 sec
2:40 ──── Slides + face: Closing ────────────────── 15 sec
                                            TOTAL: ~2:55
```

---

## Section-by-Section Script

### 0:00–0:20 | Title + Problem (Slide 0 → present over it)

**On screen:** Title slide with your face

**Say:**

> "Writing a literature review takes researchers weeks — reading papers, extracting findings, tracking contradictions, cross-checking claims. I built the Research Orchestration System — a multi-step, multi-agent system using Elastic Agent Builder to automate that entire process over a corpus of 200 AI research papers indexed in Elasticsearch."

---

### 0:20–0:45 | Research Loop Architecture (Slide 1 → present over it)

**On screen:** Research orchestration loop diagram with your face

**Say:**

> "Three agents work together. The Research Agent runs a six-step pipeline — it plans sub-questions, scopes the corpus with ES|QL analytics, finds key papers by citation count, retrieves evidence using hybrid search across 5,000 full-text chunks, cross-checks for contradictions, and writes a structured report.
>
> Then the Peer Review Agent takes over — it batch-verifies every reference with an ES|QL query, spot-checks claims against source text, identifies missing high-impact papers, and issues a pass or revision needed verdict. If it disagrees with the research, it sends specific feedback and the Research Agent revises — agents that plan, execute, review, and verify each other's work."

**Tip:** Point at/gesture toward the relevant parts of the diagram as you describe each agent.

---

### 0:45–1:25 | Web App: Literature Review (screen recording, sped up)

**On screen:** Web app screen recording, sped up 10-16x

**Text overlay:** "Sped up — real time: ~3 min"

**Voiceover (record separately, lay over the sped-up footage):**

> "Here's the web app in action. I submit a research topic and the agent begins its pipeline. You can see the live reasoning trace — every thinking step and tool call streams in real time.
>
> The Research Agent is calling search_papers, top_cited, corpus_overview — these are custom tools I built in Agent Builder using index search and ES|QL.
>
> Now the Peer Review Agent takes over, independently verifying the draft.
>
> And here's the final report — structured sections with confidence tags, contradictions, research gaps, and a full references section. Every citation traces back to a real paper in Elasticsearch."

**What to show:** Start from empty state → topic typed → reasoning trace streaming (sped up) → peer review verdict → final report (slow scroll through sections for last 5-8 seconds at normal speed).

---

### 1:25–1:40 | Claim Verification Architecture (Slide 4 → present over it)

**On screen:** Claim verification agent diagram with your face

**Say:**

> "The system also has a Claim Verification mode. You give it a specific claim and it checks whether the broader literature agrees. It searches for corroborating and contradicting evidence, assesses nuances, and produces a structured verdict."

---

### 1:40–2:10 | Web App: Claim Verification (screen recording, sped up)

**On screen:** Web app screen recording, sped up 10-16x

**Text overlay:** "Sped up — real time: ~2 min"

**Voiceover:**

> "I'll submit a claim — 'Chain-of-thought prompting significantly improves reasoning in LLM agents.' The agent finds papers on both sides, evaluates the conditions where the claim holds, and delivers a verdict.
>
> Partially Supported with Moderate confidence — it found corroborating evidence but also papers that challenge the claim in specific contexts. This is the kind of nuance that takes hours to uncover manually."

**What to show:** Mode toggle to "Verify Claim" → claim typed → reasoning trace (sped up) → verdict + report (slow scroll for last 5 seconds at normal speed).

---

### 2:10–2:40 | Slack + Claude Code MCP (screen recordings, sped up)

**On screen:** Slack recording → Claude Code recording, each sped up

**Text overlay:** "Slack" then "Claude Code (MCP)"

**Voiceover:**

> "The same agents work wherever researchers already are. In Slack — slash commands for both literature review and claim verification. Progress streams into a thread with the full report.
>
> And in Claude Code through MCP — the agents appear as native tools. Same backend, same agents, same Elasticsearch corpus — three interfaces into one system."

**What to show:**
- Slack /research (sped up, ~10 sec) — show the command, thread updating, final report
- Slack /check-claim (sped up, ~5 sec) — quick flash showing it works
- Claude Code MCP (sped up, ~10 sec) — show the tool call and result

---

### 2:40–2:55 | Closing (Slide 0 or Slide 5 → present over it)

**On screen:** Title slide or closing slide with your face

**Say:**

> "The Research Orchestration System turns weeks of literature review into minutes — three agents that combine search, reasoning, and tools across 21 to 34 tool calls per review. Currently running on 200 Agentic AI papers, but the system is corpus-agnostic — works with any research domain indexed in Elasticsearch. Built entirely on Elastic Agent Builder. Thanks for watching."

---

## Recording Plan

You need to record **3 separate clips**, then splice them together:

**Clip 1 — Slide presentation with face (all slide sections combined)**

Open your PPT in presentation mode. Record yourself presenting through the slides in order:
1. Title slide → say the 0:00–0:20 script
2. Research loop architecture → say the 0:20–0:45 script
3. Claim verification architecture → say the 1:25–1:40 script
4. Closing slide → say the 2:40–2:55 script

Record this as one continuous take. You'll cut it into pieces during editing.

**Clip 2 — Voiceover audio for screen recordings**

Record JUST your voice (no video needed) reading the voiceover scripts for:
- Web app literature review (0:45–1:25)
- Web app claim verification (1:40–2:10)
- Slack + MCP (2:10–2:40)

**Clip 3 — Already done.** You have all the screen recordings.

---

## Editing Steps (CapCut)

1. Import all clips: slide presentation, voiceover audio, all 5 screen recordings
2. Cut the slide presentation into 4 pieces (one per slide section)
3. Arrange on timeline in order: slides → screen rec → slides → screen rec → screen rec → slides
4. Speed up all screen recordings to fit the time windows (10-16x)
5. Lay voiceover audio over the sped-up screen recordings
6. Add text overlays: "Sped up — real time: ~3 min" on screen recording sections
7. Trim to under 3:00
8. Export 1080p MP4

---

## Checklist

- [ ] Title slide created (Slide 0)
- [ ] Optional closing slide created (Slide 5 with key stats)
- [ ] Slide presentation + face recorded (one take through all slides)
- [ ] Voiceover audio recorded for screen recording sections
- [ ] All clips imported into CapCut
- [ ] Screen recordings sped up to fit time windows
- [ ] Text overlays added ("Sped up" labels)
- [ ] Total length: 2:45–2:55
- [ ] Audio levels consistent across slides and voiceover
- [ ] Exported 1080p MP4
