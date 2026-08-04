# import os
# from dotenv import load_dotenv
# from retriever import DocumentRetriever
# from answer_generator import AnswerGenerator

# load_dotenv()

# def main():
#     # Remind the user to set their API token if it's missing
#     if not os.environ.get("HF_TOKEN"):
#         print("\n[!] WARNING: 'HF_TOKEN' environment variable is not set.")


#     print("=" * 50)
#     print("PDF Knowledge Base Query Agent (HF Serverless API)")
#     print("Type 'exit' or 'quit' to stop.")
#     print("=" * 50)

#     retriever = DocumentRetriever()
#     generator = AnswerGenerator()

#     while True:
#         query = input("\nAsk a question: ").strip()
#         if not query:
#             continue
#         if query.lower() in ["exit", "quit"]:
#             print("Exiting query loop.")
#             break

#         # 1. Retrieve Context
#         results = retriever.retrieve(query, top_k=3)
        
#         if not results:
#             print("No relevant context found.")
#             continue

#         # 2. Generate Answer
#         print("\nThinking (Pinging Hugging Face Cloud)...")
#         answer = generator.generate_answer(query, results)
        
#         # 3. Display Results
#         print("\n--- Answer ---")
#         print(answer.strip())
        
#         print("\n--- Sources Used ---")
#         for i, res in enumerate(results, start=1):
#             print(f"[{i}] Page {res['page_number']} (Score: {res['score']:.4f})")

# if __name__ == "__main__":
#     main()

import os
import sys
from retriever import DocumentRetriever
from answer_generator import AnswerGenerator

# Import the new general knowledge generator
from non_PDF_answer_generator import GeneralAnswerGenerator

# context-window/ holds the chat-history helpers (rolling session + query rewriting)
sys.path.append(os.path.join(os.path.dirname(__file__), "context-window"))
from session import ChatSession
from query_rewriter import QueryRewriter

def main():
    print("=" * 50)
    print("Hybrid Knowledge Base Query Agent (Local CPU Inference)")
    print("Type 'exit' or 'quit' to stop.")
    print("=" * 50)

    retriever = DocumentRetriever()

    # Initialize both options
    pdf_generator = AnswerGenerator()
    general_generator = GeneralAnswerGenerator()

    # Chat history + follow-up question rewriting, so answers stay correlated across turns
    session = ChatSession(max_turns=6)
    rewriter = QueryRewriter()

    # Set a threshold to determine if context is relevant
    RELEVANCE_THRESHOLD = 0.25

    while True:
        query = input("\nAsk a question: ").strip()
        if not query:
            continue
        if query.lower() in ["exit", "quit"]:
            print("Exiting query loop.")
            break

        history = session.get_history()

        # 0. Resolve follow-up references (e.g. "he", "that") before retrieval
        standalone_query = rewriter.rewrite(history, query)

        # 1. Retrieve Context
        results = retriever.retrieve(standalone_query, top_k=3)

        # 2. Check if we have results AND the best result is above our threshold
        if results and results[0]['score'] >= RELEVANCE_THRESHOLD:
            # --- OPTION 1: Use PDF Context ---
            print(f"\nThinking (Using PDF Context - Top Score: {results[0]['score']:.4f})...")
            answer = pdf_generator.generate_answer(query, results, history=history)

            print("\n--- Answer ---")
            print(answer.strip())

            print("\n--- Sources Used ---")
            for i, res in enumerate(results, start=1):
                print(f"[{i}] Page {res['page_number']} (Score: {res['score']:.4f})")

        else:
            # --- OPTION 2: Fallback to General LLM Knowledge ---
            best_score = results[0]['score'] if results else 0.0
            print(f"\nThinking (Using General Knowledge - PDF Score too low: {best_score:.4f})...")

            answer = general_generator.generate_answer(query, history=history)

            print("\n--- Answer ---")
            print(answer.strip())
            print("\n--- Sources Used ---")
            print("General LLM Knowledge (No matching PDF data found)")

        # 3. Remember this turn for future context
        session.add_turn("user", query)
        session.add_turn("assistant", answer.strip())

if __name__ == "__main__":
    main()