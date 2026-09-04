# Gemma 2 2B as **judge**

Same GGUF as the generator candidate. **Never load it as generator and judge in one process.**

Full fetch / eval / `.env` steps: [../../01_generators/gemma2-2b](../../01_generators/gemma2-2b).

Pair only with Qwen or Phi as the generator. Use Llama or Granite if Gemma is the generator.
