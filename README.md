# Kno AI-Educate

## Inspiration

I'm currently working full-time while pursuing a part-time Master's in AI. Balancing both made me realize how inefficient my study sessions were — I needed a tool that could adapt to _my_ pace and help me truly understand complex material, not just skim through it.

At the same time, the rapid evolution of LLMs and Agentic AI fascinated me. I wanted to go beyond reading papers and tutorials — I wanted to **learn by building**. Kno became the intersection of a personal need and a technical curiosity: a project that solves my own problem while pushing me to explore cutting-edge AI technologies.

## What It Does

Kno transforms any study material into a **personalized AI-powered learning experience**. Upload a PDF, and Kno handles the rest:

1. **Onboarding** — A conversational AI agent learns your learning style, goals, and preferences to personalize your experience.
2. **Pre-Assessment** — AI reads your material and generates a tailored quiz to gauge your current understanding, identifying
   knowledge gaps before you start.
3. **Active Learning** — An adaptive workspace where you study with:
   - A **split-pane PDF reader** with AI-powered highlights, notes, and annotations
   - A **live AI tutor** you can talk to in real-time with voice and screen sharing — it sees what you see and teaches accordingly
   - An **Excalidraw whiteboard** for visual thinking and problem-solving
4. **Post-Assessment** — A targeted quiz focused on your weak concepts, with comparative feedback showing how much you've improved.

Every step is powered by specialized AI agents that collaborate behind the scenes to deliver a learning experience tailored to you.

## How We Built It

I started by diving deep into the **Gemini API documentation**, the **ADK framework**, and various blog posts on agentic
architectures. Research came first — understanding what was possible before writing a single line of code.

One of the key tools in my workflow was **Antigravity**. It allowed me to prototype and explore different ideas rapidly, test
architectural approaches, and pivot quickly when something didn't work. This speed was critical in a hackathon setting where time
is limited and experimentation is everything.

From there, I built the platform as **six microservices**, each handling a distinct part of the learning pipeline:

| Service                      | Role                                                            |
| ---------------------------- | --------------------------------------------------------------- |
| **Backend API**              | Knowledge and document management, Firebase auth, Cloud Storage |
| **Onboarding Agent**         | Conversational preference learning via Gemini                   |
| **Pre-Assessment Agent**     | PDF-based MCQ generation and assessment marking                 |
| **Pre-Active-Learn Service** | Material caching, concept extraction, session management        |
| **Live Tutoring Agent**      | Real-time voice and video tutoring via WebSocket                |

**Tech stack:** React 19, TypeScript, Tailwind CSS v4, FastAPI, PostgreSQL, Google Gemini (Flash, Pro, 2.5 native audio), Google
ADK, Firebase, Google Cloud Run, and Google Cloud Storage.

## Challenges We Ran Into

The hardest part was figuring out **how to architect an Agentic AI application**. Unlike traditional software, there's no
established playbook for structuring multi-agent systems — how agents communicate, how to manage state across sessions, and how to
orchestrate tool calls effectively.

I also attempted to integrate the **Agent-to-Agent (A2A) protocol**, but ran into persistent dependency conflicts that ultimately
forced me to take a different approach. Learning when to pivot instead of pushing through a blocker was a valuable lesson in
itself.

## Accomplishments That We're Proud Of

- **End-to-end adaptive learning pipeline** — Built a complete study flow from onboarding to post-assessment, where AI personalizes
  every step based on the student's actual understanding.
- **Live AI tutoring with voice and screen sharing** — Integrated Gemini 2.5 Flash native audio for real-time, two-way voice
  conversations where the AI can see what you're reading.
- **Multi-agent orchestration** — Designed and deployed six microservices with specialized AI agents that collaborate — from
  generating quiz questions to creating interactive animations to marking assessments with personalized feedback.
- **Built solo, while studying and working full-time** — This entire platform was built by one person during a hackathon, proving
  that the current AI tooling genuinely empowers individual developers to build ambitious products.
- **Production-deployed** — Not just a demo. The full stack is deployed on Google Cloud Run with Firebase Hosting, Cloud SQL, and
  Cloud Storage — ready for real users.

## What We Learned

- **Agentic AI is a mindset shift.** Designing systems where AI agents use tools and make decisions is fundamentally different from
  traditional API calls. You're no longer writing logic — you're writing _instructions_ and trusting the model to execute.
- **Prompt engineering for agents is an art.** Getting agents to reliably call the right tools, in the right order, with the right
  parameters required careful iteration. Small changes in system instructions led to dramatically different behaviors.
- **The Gemini ecosystem is powerful but fast-moving.** Working with ADK, context caching, native audio, and image generation meant
  navigating new APIs with limited community resources. Reading source code became more useful than searching for tutorials.
- **Caching matters at scale.** Implementing Gemini's context caching for PDF materials significantly reduced token usage and
  response latency — a practical lesson in building cost-efficient AI applications.

## What's Next for Kno - AI Educate

- **An AI orchestrator agent** that guides you through concepts with hints, explanations, and interactive animations
- **Collaborative learning** — Enable study groups where multiple students can join the same AI-tutored session, discuss concepts
  together, and track group progress.
- **Spaced repetition system** — Use assessment results and concept mastery data to automatically schedule review sessions at
  optimal intervals for long-term retention.
- **Multi-modal material support** — Expand beyond PDFs to support lecture videos, slides, and audio recordings as learning
  materials.
- **Progress analytics dashboard** — Visualize learning progress over time with concept mastery heatmaps, assessment score trends,
  and personalized study recommendations.
- **Mobile experience** — Build a responsive mobile-first interface so students can learn on the go, with offline support for
  downloaded materials.
- **A2A protocol integration** — Revisit the Agent-to-Agent protocol to enable seamless inter-agent communication, allowing agents
  to dynamically discover and collaborate with each other without hardcoded orchestration.
