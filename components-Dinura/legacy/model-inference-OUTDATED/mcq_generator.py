"""
MCQ Generator using Hugging Face Inference API
Generate multiple-choice questions from input text without downloading models locally
"""

from huggingface_hub import InferenceClient
from dotenv import load_dotenv
import json
import re
import os
import time
from typing import List, Dict, Optional

# Load .env file from project root
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))


class QuestionGenerator:
    def __init__(self, model_name="Qwen/Qwen2.5-7B-Instruct"):
        """
        Initialize the Question Generator with the specified model using Hugging Face API
        
        Args:
            model_name: Hugging Face model name (default: "Qwen/Qwen2.5-72B-Instruct")
        """
        print(f"Connecting to Hugging Face API for model: {model_name}...")
        
        # Use HF_TOKEN from environment variables if present
        token = os.environ.get("HF_TOKEN")
        if not token:
            print("Warning: HF_TOKEN environment variable not found. You may face rate limits.")
            
        self.client = InferenceClient(model=model_name, token=token)
        self.model_name = model_name
        print("API Client initialized successfully!")
    
    def _call_api_with_retry(
        self,
        messages: List[Dict],
        max_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        max_retries: int = 5,
        initial_wait: float = 10.0
    ) -> str:
        """
        Call the HF Inference API with retry logic and exponential backoff.
        
        Args:
            messages: Chat messages to send
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Top-p sampling parameter
            max_retries: Maximum number of retry attempts
            initial_wait: Initial wait time in seconds (doubles each retry)
            
        Returns:
            Generated text content from the API
            
        Raises:
            Exception: If all retries are exhausted
        """
        last_error = None
        wait_time = initial_wait
        
        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.chat_completion(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                last_error = e
                error_str = str(e)
                
                # Check if it's a 503 (service unavailable) - worth retrying
                if "503" in error_str:
                    if attempt < max_retries:
                        print(f"  [RETRY] Attempt {attempt}/{max_retries} failed (503 - Server Unavailable).")
                        print(f"     Retrying in {wait_time:.0f}s...")
                        time.sleep(wait_time)
                        wait_time *= 2  # Exponential backoff
                        continue
                
                # Check if it's a 429 (rate limited) - worth retrying
                if "429" in error_str:
                    if attempt < max_retries:
                        print(f"  [RETRY] Attempt {attempt}/{max_retries} failed (429 - Rate Limited).")
                        print(f"     Retrying in {wait_time:.0f}s...")
                        time.sleep(wait_time)
                        wait_time *= 2
                        continue
                
                # For other errors, don't retry
                print(f"  [ERROR] Non-retryable error: {e}")
                raise
        
        # All retries exhausted
        raise Exception(f"All {max_retries} attempts failed. Last error: {last_error}")
    
    def generate_mcqs(
        self, 
        text: str, 
        num_questions: int = 5,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9,
        do_sample: bool = True
    ) -> List[Dict]:
        """
        Generate multiple-choice questions from input text
        
        Args:
            text: Input text to generate questions from
            num_questions: Number of questions to generate
            max_new_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            top_p: Top-p sampling parameter
            do_sample: Whether to use sampling or greedy decoding
            
        Returns:
            List of dictionaries containing questions, options, and answers
        """
        
        # Prepare the prompt
        prompt_template = f"""You are an expert MCQ generator. Based on the following text, generate {num_questions} multiple-choice questions.

Text: {text}

Generate {num_questions} multiple-choice questions in the following JSON format:
[
    {{
        "question": "Question text here",
        "options": ["A. Option 1", "B. Option 2", "C. Option 3", "D. Option 4"],
        "correct_answer": "A"
    }}
]

Make sure:
1. Each question tests understanding of the text
2. All options are plausible
3. There is exactly one correct answer
4. Questions cover different aspects of the text
5. Include the correct answer letter (A, B, C, or D)

Return only the JSON array, no other text.
"""
        
        messages = [
            {"role": "user", "content": prompt_template}
        ]
        
        # Generate response via API with retry logic
        print("Generating MCQs via API...")
        try:
            generated_content = self._call_api_with_retry(
                messages=messages,
                max_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p
            )
        except Exception as e:
            print(f"[ERROR] API Error after retries: {e}")
            return [{
                "question": "Failed to connect to API. The model may be temporarily unavailable.",
                "options": ["A. N/A", "B. N/A", "C. N/A", "D. N/A"],
                "correct_answer": "A"
            }]
        
        # Parse the JSON response
        try:
            # Find JSON array in the response
            json_match = re.search(r'\[.*\]', generated_content, re.DOTALL)
            if json_match:
                mcqs = json.loads(json_match.group())
                return mcqs
            else:
                # Fallback: try to parse the entire response
                mcqs = json.loads(generated_content)
                return mcqs
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            print(f"Response was: {generated_content}")
            # Return a simple error message
            return [{
                "question": "Failed to generate MCQs. Please check the output format.",
                "options": ["A. N/A", "B. N/A", "C. N/A", "D. N/A"],
                "correct_answer": "A"
            }]

    def generate_short_answer_questions(
        self, 
        text: str, 
        num_questions: int = 5,
        max_new_tokens: int = 512,
        temperature: float = 0.7,
        top_p: float = 0.9
    ) -> List[Dict]:
        """
        Generate short answer questions from input text
        """
        
        # Prepare the prompt
        prompt_template = f"""You are an expert question generator. Based on the following text, generate {num_questions} short-answer questions along with their answers.

Text: {text}

Generate {num_questions} short-answer questions in the following JSON format:
[
    {{
        "question": "Question text here",
        "answer": "Short answer here"
    }}
]

Make sure:
1. Each question tests understanding of the text
2. The answers are concise and directly based on the text

Return ONLY the JSON array, no other text.
"""
        
        messages = [
            {"role": "user", "content": prompt_template}
        ]
        
        print("Generating Short Answer Questions via API...")
        try:
            generated_content = self._call_api_with_retry(
                messages=messages,
                max_tokens=max_new_tokens,
                temperature=temperature,
                top_p=top_p
            )
        except Exception as e:
            print(f"[ERROR] API Error after retries: {e}")
            return [{
                "question": "Failed to connect to API. The model may be temporarily unavailable.",
                "answer": "N/A"
            }]
        
        # Parse the JSON response
        try:
            # Find JSON array in the response
            json_match = re.search(r'\[.*\]', generated_content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return json.loads(generated_content)
        except json.JSONDecodeError as e:
            print(f"Error parsing JSON: {e}")
            print(f"Response was: {generated_content}")
            return [{
                "question": "Failed to generate questions. Please check the output format.",
                "answer": "N/A"
            }]
    
    def generate_mcqs_with_context(
        self,
        text: str,
        context: str = "",
        num_questions: int = 5,
        difficulty: str = "medium"
    ) -> List[Dict]:
        """
        Generate MCQs with additional context and difficulty level
        
        Args:
            text: Input text
            context: Additional context or instructions
            num_questions: Number of questions
            difficulty: Difficulty level (easy, medium, hard)
            
        Returns:
            List of MCQs
        """
        
        prompt_template = f"""You are an expert MCQ generator. Generate {num_questions} {difficulty} difficulty multiple-choice questions.

Context: {context if context else 'Generate questions based solely on the text below.'}

Text: {text}

Generate {num_questions} well-structured multiple-choice questions in this JSON format:
[
    {{
        "question": "Clear question text",
        "options": ["A. option1", "B. option2", "C. option3", "D. option4"],
        "correct_answer": "A"
    }}
]

Return only the JSON array.
"""
        
        messages = [
            {"role": "user", "content": prompt_template}
        ]
        
        try:
            generated_content = self._call_api_with_retry(
                messages=messages,
                max_tokens=512,
                temperature=0.8,
                top_p=0.95
            )
        except Exception as e:
            print(f"❌ API Error after retries: {e}")
            return []
        
        try:
            json_match = re.search(r'\[.*\]', generated_content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return json.loads(generated_content)
        except json.JSONDecodeError:
            return []


def main():
    """Example usage of Question Generator"""
    
    # Initialize the generator
    generator = QuestionGenerator()
    
    # Sample text for demonstration
    sample_text = """
    Artificial Intelligence (AI) is the simulation of human intelligence in machines 
    that are programmed to think and learn. Machine learning is a subset of AI that 
    enables systems to learn and improve from experience without being explicitly 
    programmed. Deep learning, a further subset of machine learning, uses neural 
    networks with multiple layers to analyze various factors of data. 
    Natural Language Processing (NLP) is another branch of AI that deals with 
    the interaction between computers and humans using natural language.
    The development of AI has led to significant advancements in healthcare, 
    transportation, and education.
    """
    
    # Generate MCQs
    mcqs = generator.generate_mcqs(
        text=sample_text,
        num_questions=3,
        max_new_tokens=512,
        temperature=0.7,
        do_sample=True
    )
    
    # Display the MCQs
    print("\n" + "="*80)
    print("GENERATED MCQs")
    print("="*80)
    
    for i, mcq in enumerate(mcqs, 1):
        print(f"\nQ{i}. {mcq.get('question', 'No question provided')}")
        if 'options' in mcq:
            for option in mcq['options']:
                print(f"   {option}")
        print(f"   Correct Answer: {mcq.get('correct_answer', 'N/A')}")
    
    # Optionally, save to file
    with open("generated_mcqs.json", "w") as f:
        json.dump(mcqs, f, indent=2)
    print("\nMCQs saved to generated_mcqs.json")


if __name__ == "__main__":
    main()