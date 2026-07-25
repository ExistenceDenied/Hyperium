from ollama import chat

response = chat(
    model="qwen3",
    messages=[{"role": "user", "content": "Say hello in one sentence."}],
)
print(response["message"]["content"])
