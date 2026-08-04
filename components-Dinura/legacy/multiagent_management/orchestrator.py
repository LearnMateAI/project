"""
Orchestrates the chat agent and the evaluator agent as a generate -> judge -> regenerate loop.

Per turn:
    1. rewrite the follow-up into a standalone question (QueryRewriter)
    2. retrieve context (DocumentRetriever) and pick a generator the way chat.py does:
       above RELEVANCE_THRESHOLD -> AnswerGenerator (PDF-grounded)
       below it                  -> GeneralAnswerGenerator (general knowledge)
    3. judge the reply with chat_msg_evaluator, which applies the strict grounded rubric
       only when context was actually retrieved
    4. if the score is below the threshold, feed the regeneration instruction back and
       regenerate exactly once
    5. return the last attempt -- the regenerated reply is shown whether or not it cleared
       the threshold -- and record it in the shared ChatSession

Two ~3B models plus the MiniLM embedder are resident at once (Qwen2.5 generating, Llama 3.2
judging), so expect roughly 5 GB of RAM and ~40s for a judged turn on CPU.

Imports need care: chat-agent/ has a hyphen, so it cannot be imported as a package, and its
modules default to cwd-relative paths ("./qdrant_data", "models/qwen...gguf"). Both folders
go on sys.path and every path is passed in absolute, so this runs from any directory.

Run:  python orchestrator.py
"""

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_COMPONENTS = os.path.dirname(_HERE)
CHAT_AGENT_DIR = os.path.join(_COMPONENTS, "chat-agent")
EVALUATOR_DIR = os.path.join(_COMPONENTS, "evaluator_agent")

for _path in (CHAT_AGENT_DIR, os.path.join(CHAT_AGENT_DIR, "context-window"), EVALUATOR_DIR):
    if _path not in sys.path:
        sys.path.insert(0, _path)

# chat-agent side
from answer_generator import AnswerGenerator
from non_PDF_answer_generator import GeneralAnswerGenerator
from query_rewriter import QueryRewriter
from retriever import DocumentRetriever
from session import ChatSession

# evaluator side
import chat_msg_evaluator
from agent import DEFAULT_THRESHOLD, EvaluatorLLM

# Absolute equivalents of the chat agent's cwd-relative defaults.
CHAT_MODEL_PATH = os.path.join(CHAT_AGENT_DIR, "models", "qwen2.5-3b-instruct-q4_k_m.gguf")
QDRANT_PATH = os.path.join(CHAT_AGENT_DIR, "qdrant_data_v2")

# Same cutoff chat.py uses to choose between PDF context and general knowledge.
RELEVANCE_THRESHOLD = 0.25


def _revision_query(query: str, instruction: str, previous_reply: str) -> str:
    """
    Fold the evaluator's instruction into the next generation attempt.

    The chat agent's generators take no "instruction" argument, so the feedback rides along
    inside the question. That keeps chat-agent/ untouched by this orchestration layer.
    """
    return (
        f"{query}\n\n"
        "[REVISION REQUIRED] Your previous reply was rejected by an evaluator.\n"
        f'Previous reply:\n"""\n{previous_reply}\n"""\n'
        f"Required fix: {instruction}\n"
        "Answer the original question again, corrected. Do not mention this instruction "
        "or the fact that you are revising."
    )


class Orchestrator:
    """Runs one chat turn through generation and evaluation, retrying on a low score."""

    # One generation plus at most one regeneration. Raising this is not just slower: the
    # judge is a 3B model, so extra rounds tend to oscillate rather than converge.
    MAX_ATTEMPTS = 2

    def __init__(self, threshold: int = DEFAULT_THRESHOLD, max_attempts: int = MAX_ATTEMPTS,
                 max_turns: int = 6, verbose: bool = True):
        self.threshold = threshold
        self.max_attempts = max_attempts
        self.verbose = verbose

        self._log("[*] Starting chat agent...")
        self.retriever = DocumentRetriever(db_path=QDRANT_PATH)
        self.pdf_generator = AnswerGenerator(model_path=CHAT_MODEL_PATH)
        self.general_generator = GeneralAnswerGenerator(model_path=CHAT_MODEL_PATH)
        self.rewriter = QueryRewriter(model_path=CHAT_MODEL_PATH)
        self.session = ChatSession(max_turns=max_turns)

        self._log("[*] Starting evaluator agent...")
        self.evaluator = EvaluatorLLM()

    def close(self):
        """
        Release the Qdrant file lock explicitly.

        Left to the garbage collector it runs during interpreter shutdown, where
        qdrant-client's __del__ touches already-torn-down modules and prints a spurious
        traceback after an otherwise clean exit.
        """
        try:
            self.retriever.client.close()
        except Exception:
            pass

    def _log(self, message: str):
        if self.verbose:
            print(message)

    def _generate(self, query: str, contexts: list, history: list) -> str:
        """Route to the same generator chat.py would have chosen for this turn."""
        if contexts:
            return self.pdf_generator.generate_answer(query, contexts, history=history)
        return self.general_generator.generate_answer(query, history=history)

    def ask(self, query: str) -> dict:
        """
        Handle one user message end to end.

        Returns a trace of the whole turn:
            {query, standalone_query, mode, contexts, attempts, reply, verdict, accepted}
        where `attempts` is [{reply, verdict}, ...] in order and `reply`/`verdict` are the
        LAST attempt -- once a regeneration has run, its output is what the caller gets,
        pass or fail. `accepted` reports whether that final reply cleared the threshold, so
        a caller that wants to flag unreviewed output can still branch on it, and every
        earlier attempt stays in `attempts` for inspection.
        """
        history = self.session.get_history()

        # Resolve follow-up references before retrieval, exactly as chat.py does.
        standalone_query = self.rewriter.rewrite(history, query)

        results = self.retriever.retrieve(standalone_query, top_k=3)
        grounded = bool(results) and results[0]["score"] >= RELEVANCE_THRESHOLD
        contexts = results if grounded else None

        best_score = results[0]["score"] if results else 0.0
        if grounded:
            self._log(f"[*] PDF mode (top retrieval score {best_score:.4f})")
        else:
            self._log(f"[*] General mode (top retrieval score {best_score:.4f})")

        attempts = []
        generation_input = query

        for attempt in range(1, self.max_attempts + 1):
            self._log(f"[*] Generating (attempt {attempt}/{self.max_attempts})...")
            reply = self._generate(generation_input, contexts, history).strip()

            self._log("[*] Evaluating...")
            # Always judge against the original question, never the revision wrapper.
            verdict = chat_msg_evaluator.evaluate_reply(
                self.evaluator, query, reply,
                contexts=contexts, history=history, threshold=self.threshold,
            )
            attempts.append({"reply": reply, "verdict": verdict})
            self._log(f"[*] Score {verdict['score']}/100 -> {'PASS' if verdict['passed'] else 'REGENERATE'}")

            if verdict["passed"] or attempt == self.max_attempts:
                break

            self._log(f"[*] Feedback: {verdict['regeneration_instruction']}")
            generation_input = _revision_query(query, verdict["regeneration_instruction"], reply)

        # Show the regenerated reply on its own merits: the last attempt is the answer,
        # whether it cleared the threshold or not. Earlier attempts stay in `attempts`.
        final = attempts[-1]

        self.session.add_turn("user", query)
        self.session.add_turn("assistant", final["reply"])

        return {
            "query": query,
            "standalone_query": standalone_query,
            "mode": "pdf" if grounded else "general",
            "contexts": results,
            "attempts": attempts,
            "reply": final["reply"],
            "verdict": final["verdict"],
            "accepted": final["verdict"]["passed"],
        }


def main():
    print("=" * 60)
    print("Multi-Agent Orchestrator  (chat agent + evaluator agent, local CPU)")
    print("Type 'exit' or 'quit' to stop.")
    print("=" * 60)

    orchestrator = Orchestrator()

    try:
        _repl(orchestrator)
    finally:
        orchestrator.close()


def _repl(orchestrator: "Orchestrator"):
    while True:
        query = input("\nAsk a question: ").strip()
        if not query:
            continue
        if query.lower() in ("exit", "quit"):
            print("Exiting orchestrator.")
            break

        result = orchestrator.ask(query)
        verdict = result["verdict"]

        print("\n--- Answer ---")
        print(result["reply"])

        print("\n--- Evaluation ---")
        attempts = result["attempts"]
        if len(attempts) > 1:
            trail = " -> ".join(str(a["verdict"]["score"]) for a in attempts)
            print(f"Regenerated once. Scores: {trail} (showing the regenerated reply)")
        status = "accepted" if result["accepted"] else "BELOW THRESHOLD - shown anyway"
        print(f"Score {verdict['score']}/100 (threshold {verdict['threshold']}) - {status}")
        print(f"Reasoning: {verdict['reasoning']}")
        if not result["accepted"]:
            print(f"Unresolved: {verdict['regeneration_instruction']}")

        if result["mode"] == "pdf":
            print("\n--- Sources Used ---")
            for i, ctx in enumerate(result["contexts"], start=1):
                print(f"[{i}] Page {ctx['page_number']} (Score: {ctx['score']:.4f})")
        else:
            print("\n--- Sources Used ---")
            print("General LLM Knowledge (no matching PDF data found)")


if __name__ == "__main__":
    main()
