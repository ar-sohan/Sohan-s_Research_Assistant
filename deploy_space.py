"""Upload the website to a Hugging Face Space without using git.

    .\\.venv\\Scripts\\python deploy_space.py

The first time, it asks for a Hugging Face token (create one at
https://huggingface.co/settings/tokens, type "Write"). Paste it and press
Enter; it is invisible while you paste. The token is saved by huggingface_hub
on this computer, never in this project.

Only the files the website needs are uploaded: never .env, .venv or data/.
"""

import sys

from huggingface_hub import HfApi, login
from huggingface_hub.errors import HfHubHTTPError

SPACE_ID = sys.argv[1] if len(sys.argv) > 1 else "MdArifShahriar/research-paper-assistant"

UPLOAD = ["app.py", "README.md", "requirements.txt", "paper_agent/**/*.py"]
NEVER = [".env", ".env.*", ".venv/**", "data/**", "**/__pycache__/**"]


def main() -> None:
    api = HfApi()
    try:
        user = api.whoami()["name"]
    except Exception:  # noqa: BLE001 - not logged in yet
        print("Paste your Hugging Face WRITE token (it stays invisible), then press Enter.")
        login(add_to_git_credential=False)
        user = api.whoami()["name"]
    print(f"Signed in as {user}. Uploading to https://huggingface.co/spaces/{SPACE_ID} ...")
    try:
        api.upload_folder(
            repo_id=SPACE_ID, repo_type="space", folder_path=".",
            allow_patterns=UPLOAD, ignore_patterns=NEVER,
            commit_message="Deploy research paper assistant",
        )
    except HfHubHTTPError as e:
        print(f"\nUpload failed: {e}\n"
              "Most likely the token is read-only. Create a new token with type 'Write' at\n"
              "https://huggingface.co/settings/tokens, then run:  .\\.venv\\Scripts\\hf auth logout\n"
              "and run this script again.")
        sys.exit(1)
    print("Done. The Space is building; open it in 2-4 minutes.")


if __name__ == "__main__":
    main()
