import requests
import subprocess
import sys
import json
import os


def generate_search_query(user_input: str) -> str:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return user_input

    url = "https://api.groq.com/openai/v1/chat/completions"

    system_instruction = (
        "You are a GitHub Search Query Generator. "
        "Convert the user's intent into a precise GitHub search string using qualifiers "
        "(e.g., 'language:rust topic:cli sort:stars'). "
        "Rules: \n"
        "1. Output ONLY the query string.\n"
        "2. Do NOT use Markdown (no backticks).\n"
        "3. Do NOT explain your answer."
    )

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_input},
        ],
        "temperature": 0.1,  # Low temperature for deterministic results
    }

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        response.raise_for_status()  # Raise error for 4xx/5xx

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        return content.strip().replace("`", "").replace('"', "")

    except Exception as e:
        return user_input


def get_token_from_cli():
    try:
        result = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True
        )  # we run this so that we can get more calls
        token = result.stdout.strip()

        if not token:
            raise Exception("No token found. Run 'gh auth login' first.")
        return token

    except FileNotFoundError:
        print("Error: GitHub CLI ('gh') is not installed.")
        sys.exit(1)


TOKEN = get_token_from_cli()

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github.v3+json",
}


def contents(repo: str) -> list[str]:
    api_contents = f"https://api.github.com/repos/{repo}/contents"

    response = requests.get(api_contents, headers=headers)

    if response.status_code != 200:
        print(response.text)
        limit = response.headers.get("X-RateLimit-Limit")
        print(limit)
        raise Exception(f"Error: {response.status_code}")
    return response.json()


def has_active_actions(repo_full_name):
    url = f"https://api.github.com/repos/{repo_full_name}/actions/runs?per_page=1"

    resp = requests.get(url, headers=headers)

    if resp.status_code == 200:
        data = resp.json()
        # if 'total_count' > 0, they have run Actions at least once.
        return data.get("total_count", 0) > 0
    return False


def search(query: str, limit: int = 5) -> list[str]:
    if limit > 50:
        raise Exception(
            "Limit must be less than or equal to 50. Please reduce the limit and try again."
        )
    api_search = (
        f"https://api.github.com/search/repositories?q={query}&per_page={limit}"
    )

    response = requests.get(api_search)
    return response.json()["items"]


def main():
    useful_repos = list()
    for repo in search("numpy", limit=5):
        if has_active_actions(repo["full_name"]):  # CI action detected
            useful_repos.append(repo)

    print(json.dumps(useful_repos, indent=4))

    # for file in repo_files:
    #     print(f"{file['name']}")


if __name__ == "__main__":
    main()
