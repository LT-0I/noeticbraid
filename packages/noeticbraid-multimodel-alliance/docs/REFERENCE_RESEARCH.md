# Reference Research

The implementation borrows patterns, not code or runtime dependencies, from well-known open-source multi-agent projects.

| Project | Link | Adopted idea | What was not adopted |
|---|---|---|---|
| Microsoft Agent Framework | https://github.com/microsoft/agent-framework | Separate orchestration decision from actual agent invocation; keep handoff metadata explicit. | No dependency or framework runtime. |
| Microsoft AutoGen | https://github.com/microsoft/autogen | Role-based multi-agent conversation and reviewer/adversary separation. | No chat runtime, no model execution adapter. |
| LangGraph multi-agent workflows | https://www.langchain.com/blog/langgraph-multi-agent-workflows | Treat supervisor/graph routing as a deterministic control layer. | No graph engine dependency. |
| OpenAI Swarm | https://github.com/openai/swarm | Lightweight handoff concept and context variables map well to `selected_models[].invocation`. | No Swarm dependency; no model call layer. |
| CrewAI | https://github.com/crewAIInc/crewAI | Clear distinction between role/goal and flow/task sequencing. | No CrewAI dependency or autonomous crew runtime. |

Design conclusion: SP-B should stay small and auditable. The reusable essence is explicit role selection, handoff metadata, debate records, and convergence without majority vote. Actual invocation belongs to SP-C2, and source aggregation belongs to SP-H.
