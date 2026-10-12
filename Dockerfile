# PSE-Kali web console — container for free hosting (Hugging Face Spaces / Render / Fly).
# DEMO MODE by default: mock backend, no real tools execute — safe to expose.
# For a live demo set PSE_BACKEND to an API model + provide the key as a secret.
FROM python:3.11-slim

WORKDIR /app
COPY . /app

# Kernel is stdlib; pyyaml for config. Uncomment a backend for a live demo.
RUN pip install --no-cache-dir pyyaml
#   pip install anthropic        # PSE_BACKEND=claude:claude-opus-4-8
#   pip install mistralai        # PSE_BACKEND=mistral:mistral-large-latest
#   pip install llama-cpp-python # PSE_BACKEND=gguf:models/<model>.gguf (needs RAM)

# Safe public defaults. Hosts (Render/HF) override PORT.
ENV PSE_BACKEND=mock
ENV PORT=7860
EXPOSE 7860

CMD ["python", "webapp/server.py", "--host", "0.0.0.0"]
