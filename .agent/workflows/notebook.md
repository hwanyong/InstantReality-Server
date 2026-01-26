---
description: Deep research and knowledge management using Google NotebookLM
---

# 📚 NotebookLM Research Agent

This workflow leverages Google's NotebookLM to provide source-grounded, hallucination-free answers based on your document library. It automates the "Smart Add" process and deep inquiry loops.

## 🛠️ Step 1: Environment & Auth Check
First, verify the skill's authentication status.
1. **Check Status**:
   `python .agent/skills/notebooklm/scripts/run.py auth_manager.py status`
   - *Cwd*: `.agent/skills/notebooklm`
2. **Authenticate (if needed)**:
   - If `Authenticated: False`, initiate browser login.
   - `python .agent/skills/notebooklm/scripts/run.py auth_manager.py setup`
   - **User Action**: Log in to Google when the browser window appears.

## 📥 Step 2: Context Setup (Smart Ingest vs. Retrieval)
Determine whether to add new knowledge or query existing notebooks.

### Scenario A: New Notebook URL Provided (Smart Ingest)
If the user provides a URL, the agent probes it first to generate metadata automatically.
1. **Probe Content**:
   `python .agent/skills/notebooklm/scripts/run.py ask_question.py --notebook-url "[URL]" --question "Summarize the key topics, purpose, and content of this notebook in 3 sentences."`
2. **Auto-Register**:
   - Use the summary to populate the add command.
   `python .agent/skills/notebooklm/scripts/run.py notebook_manager.py add --url "[URL]" --name "[Recommended Name]" --description "[Summary]" --topics "[Keywords]"`

### Scenario B: Existing Knowledge Base
// turbo
1. **List Notebooks**:
   `python .agent/skills/notebooklm/scripts/run.py notebook_manager.py list`
2. **Activate**:
   - Select the most relevant notebook ID.
   `python .agent/skills/notebooklm/scripts/run.py notebook_manager.py activate --id [ID]`

## 🔍 Step 3: Deep Inquiry Loop
Don't stop at the first answer. Dig deeper if the information is incomplete.

1. **Initial Query**:
   `python .agent/skills/notebooklm/scripts/run.py ask_question.py --question "[User Question]"`
2. **Analyze & Follow-up**:
   - **CRITICAL**: If the answer ends with "Is that all you need?", **DO NOT** stop if the user's intent isn't fully satisfied.
   - **Action**: Check for gaps. If missing details, ask:
   `python .agent/skills/notebooklm/scripts/run.py ask_question.py --question "Regarding [Missing Point], please elaborate..."`
3. **Synthesize**:
   - Combine all responses into a final answer for the user.

## 🧹 Step 4: Cleanup
Release browser resources while keeping the library intact.
// turbo
`python .agent/skills/notebooklm/scripts/run.py cleanup_manager.py --preserve-library`
