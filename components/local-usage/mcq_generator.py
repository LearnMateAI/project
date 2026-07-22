from huggingface_hub import hf_hub_download
# pyrefly: ignore [missing-import]
from llama_cpp import Llama
import json
import re
import os
from typing import List, Dict

class QuestionGeneratorLocal:
    def __init__(self, 
                 repo_id="bartowski/Qwen2.5-7B-Instruct-GGUF", 
                 filename="Qwen2.5-7B-Instruct-Q4_K_M.gguf"):
        """
        Initialize the Local CPU Question Generator using llama.cpp and quantized GGUF models.
        
        Args:
            repo_id: Hugging Face repo containing the GGUF model
            filename: The specific quantized GGUF file to download (Q4_K_M is recommended for balance of speed/quality on 8GB RAM)
        """
        print(f"Downloading/Loading local model (this may take a few minutes the first time): {filename}...")
        
        # Download the model from Hugging Face if not already downloaded to the local cache
        model_path = hf_hub_download(repo_id=repo_id, filename=filename)
        print(f"Model found at: {model_path}")
        
        print("Initializing Llama CPP Engine for CPU inference...")
        # Initialize the model on CPU
        # n_ctx is the context window (max tokens it can handle at once)
        # n_threads utilizes multi-core CPU for faster inference
        self.llm = Llama(
            model_path=model_path,
            n_ctx=2048,
            n_threads=os.cpu_count() or 4,  
            verbose=False
        )
        print("Local model initialized successfully and ready for offline CPU inference!")
    
    def generate_short_answer_questions(
        self, 
        text: str, 
        num_questions: int = 5,
        max_new_tokens: int = 512,
        temperature: float = 0.7
    ) -> List[Dict]:
        """
        Generate short answer questions from input text completely offline.
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
        
        # Using Qwen's ChatML format
        prompt = (
            "<|im_start|>system\nYou are an expert question generator.<|im_end|>\n"
            f"<|im_start|>user\n{prompt_template}<|im_end|>\n"
            "<|im_start|>assistant\n"
        )
        
        print("Running inference locally on CPU (this may take 1-3 minutes depending on your processor)...")
        
        # Generate the response
        output = self.llm(
            prompt,
            max_tokens=max_new_tokens,
            temperature=temperature,
            stop=["<|im_end|>", "<|endoftext|>"]
        )
        
        generated_content = output['choices'][0]['text'].strip()
        
        # Parse the JSON response
        try:
            # Find JSON array in the response
            json_match = re.search(r'\[.*\]', generated_content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            else:
                return json.loads(generated_content)
        except json.JSONDecodeError:
            print(f"Error parsing JSON. Raw output was: \n{generated_content}")
            return [{
                "question": "Failed to generate questions. Check the raw output.",
                "answer": "N/A"
            }]
