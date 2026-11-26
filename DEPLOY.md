# Put the website online for free (Hugging Face Spaces + Groq)

The website is `app.py`. On your computer it uses Ollama; online it uses the
free Groq API, because a free Space has no GPU and is too small for a local model.

Cost: **free**. Hugging Face "CPU basic" Spaces are free, and Groq's free tier
for `openai/gpt-oss-120b` gives roughly 1,000 requests and 200,000 tokens a
day. One summary uses about 4 to 8 requests, so expect around 100 summaries a
day for everyone together. The app caps this itself (see "Limits" below).

---

## 1. Get a Groq API key (once)

1. Sign up at https://console.groq.com (Google sign-in works).
2. Go to **API Keys** -> **Create API Key**, name it `research-assistant-space`.
3. Copy the key (starts with `gsk_`). You only see it once.

**Never** paste the key into code, a chat, a commit or a screenshot. If it
leaks, delete it on the API Keys page and create a new one.

## 2. Create the Space (once)

1. Sign up at https://huggingface.co.
2. Click your profile picture -> **New Space**.
3. Fill in:
   - **Space name:** `research-paper-assistant`
   - **SDK:** Gradio, template **Blank**
   - **Hardware:** CPU basic (free)
   - **Visibility:** Public (anyone with the link can use it)
4. Click **Create Space**.

## 3. Add the key as a secret (once)

In the Space: **Settings** -> **Variables and secrets** -> **New secret**
- Name: `GROQ_API_KEY`
- Value: your `gsk_...` key

Secrets are hidden from visitors and never appear in the code. Optional
extra settings (as **variables**, not secrets):

| Name | Default | Meaning |
|------|---------|---------|
| `LLM_MODEL` | `openai/gpt-oss-120b` | Groq model; `openai/gpt-oss-20b` is faster |
| `WEB_MAX_PER_USER_PER_HOUR` | `5` | summaries per visitor per hour |
| `WEB_MAX_PER_DAY` | `100` | summaries per day for the whole site |
| `APP_PASSWORD` | (none) | if set, visitors must log in as `guest` with this password (secret) |

## 4. Upload the code

The Space is its own git repository. From PowerShell in the project folder:

```powershell
git remote add space https://huggingface.co/spaces/<your-hf-username>/research-paper-assistant
git push space main --force
```

The first push asks you to sign in: use your Hugging Face **username**, and as
the password a **write access token** from https://huggingface.co/settings/tokens
(New token -> type Write). `--force` replaces the Space's starter README.

The Space then builds (2 to 4 minutes, watch the **Logs** tab) and shows the app.

## 5. Share it

Your link is `https://huggingface.co/spaces/<your-hf-username>/research-paper-assistant`.

## Updating the website later

After changing the code:
```powershell
git push origin main     # GitHub
git push space main      # the website rebuilds automatically
```

---

## Limits and how the key is protected

- The key lives only in the Space secret; the code reads `GROQ_API_KEY`.
- Each visitor (by IP address) gets `WEB_MAX_PER_USER_PER_HOUR` summaries per hour.
- The whole site stops at `WEB_MAX_PER_DAY` summaries per day.
- At most 2 summaries run at the same time; others wait in a queue.
- When Groq's free quota runs out, visitors see "the free AI quota is used up,
  try again later" instead of an error.
- Counters reset when the Space restarts. A free Space sleeps after ~48 hours
  without visitors and wakes on the next visit (takes about a minute).
- The paper library on the Space is temporary and shared by all visitors; it
  only speeds up repeated topics.

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Space shows "Build error" | Open the **Logs** tab; usually a typo in the README header. |
| "API key is missing or invalid" | The secret name must be exactly `GROQ_API_KEY`; after adding it, click **Restart Space**. |
| "free AI quota is used up" | Groq's daily limit is reached; it resets daily. Lower `WEB_MAX_PER_DAY` or switch `LLM_MODEL` to `openai/gpt-oss-20b`. |
| `git push space` asks for a password and fails | Use a Hugging Face **write token**, not your account password. |

## Run the website on your own computer

```powershell
.\.venv\Scripts\pip install gradio
.\.venv\Scripts\python app.py
```
Open http://127.0.0.1:7860. It uses your `.env` settings (Ollama by default).
