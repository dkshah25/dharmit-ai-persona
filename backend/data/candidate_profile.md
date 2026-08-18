# Candidate Profile: Dharmit Shah

## Overview
Dharmit Shah is a highly skilled Full-Stack AI Engineer with extensive experience in developing, optimizing, and deploying LLM applications, retrieval-augmented generation (RAG) pipelines, and responsive web applications. He combines strong software engineering foundations (Python, FastAPI, Next.js, React) with hands-on expertise in vector databases, prompt engineering, agentic workflows, and automated evaluation suites.

---

## Why You Should Hire Dharmit Shah
1. **Production-Grade AI Experience:** He has built and deployed robust RAG pipelines featuring custom TF-IDF fallback embeddings, strict similarity threshold guardrails, and dynamic multi-provider model rotation.
2. **Full-Stack Engineering Capability:** Fluent in frontend development (React, Next.js, clean CSS layouts) and backend architectures (FastAPI, Python, Uvicorn, API design).
3. **Automated Evals & Quality Control:** Experienced in building custom evaluation suites (LLM-as-a-judge pipelines) to objectively measure accuracy, latency, and hallucination rates.
4. **Reliability-First Mindset:** He writes code with robust exception handling, fallback clients, and automated recovery loops to handle real-world API rate limits (HTTP 429) and outages.
5. **Practical Problem Solver:** Builds functional, end-to-end applications rather than simple minimum viable products, focusing on performance, clean design, and user experience.

---

## Technical Skills
- **AI & Machine Learning:** RAG Pipelines, Vector Databases (ChromaDB), Semantic Embeddings (OpenAI, local TF-IDF fallback), Prompt Engineering, Guardrails (Adversarial Prompt Defense, Prompt Injection Protection).
- **Backend Development:** Python, FastAPI, Uvicorn, Node.js, Express, REST APIs, HTTP protocols, asynchronous Python (`asyncio`, `httpx`).
- **Frontend Development:** JavaScript (ES6+), React, Next.js, HTML5, Vanilla CSS, Tailwind CSS.
- **Tools & Databases:** Git/GitHub, Docker, SQL, JSON/JSONL, YAML, Render, Cal.com (Scheduling integrations), Vapi (Voice AI integration).

---

## AI & Software Engineering Projects

### 1. ScholarMind (AI-Powered Educational Platform)
- **Problem:** Students struggle to retrieve precise, grounded answers from complex course syllabi and lecture slides.
- **Solution:** Developed an educational assistant that leverages a RAG pipeline to answer user queries grounded exclusively in indexed course materials.
- **Architecture:** PDF parser extractors convert document contents, which are chunked using `RecursiveCharacterTextSplitter`. Chunks are indexed into ChromaDB. The backend matches user queries using semantic search and feeds context to the LLM.
- **Technologies:** Next.js, FastAPI, Python, ChromaDB, OpenAI/Groq API.
- **Engineering Decisions & Tradeoffs:** Selected a pure-python vector store structure to maximize lightweight deployment flexibility while keeping high semantic similarity accuracy.
- **Impact/Result:** Reduced answer lookup latency to under 2 seconds and achieved zero hallucinations on out-of-syllabus queries.

### 2. MarketMind (Financial Agent Platform)
- **Problem:** Individual investors spend hours reading financial reports, news, and valuation sheets to make trading decisions.
- **Solution:** Built a multi-agent financial platform that analyzes company metrics, performs valuation formulas, and synthesizes news sentiment.
- **Architecture:** Multi-agent system utilizing LLM tool calls (`check_available_slots`, financial formulas).
- **Technologies:** React, FastAPI, Python, tool-calling APIs.
- **Impact/Result:** Allowed users to generate structured equity research sheets in under 10 seconds.

### 3. Symbi-GPT (Agentic Workflow System)
- **Problem:** Standard chat interfaces fail at complex, multi-step tasks requiring software tools.
- **Solution:** Designed a custom agentic workflow engine that translates complex prompts into sequential tool executions.
- **Technologies:** Python, OpenAI Tool-calling API.
- **Impact/Result:** Achieved robust task completion rates for multi-step agent actions.

---

## Professional Experience & Internships
- **Software Engineering Intern / AI Engineer:** Worked on indexing documents, developing custom API endpoints, setting up automated evaluation test cases, and implementing rate-limiting safety guardrails.
- **Key Contributions:** Successfully designed a model rotation sequence supporting instant provider switching (from Groq to Gemini to OpenAI) to maintain 99.9% uptime against quota constraints.

---

## Engineering Strengths & Tradeoffs
- **Reliable Model Routing:** Dharmit believes in designing systems that don't fail under heavy load. His fallback rotation sequence switches providers immediately when quota limits (HTTP 429) are encountered, avoiding unproductive retry loops.
- **Clean Ingestion Pipelines:** Wipes old indexes before rebuilding to avoid stale document duplicates.
- **Grounding over Hallucination:** Prefers strict similarity thresholds, returning `"I do not have enough information in my knowledge base to answer that accurately"` rather than risk making up facts.
