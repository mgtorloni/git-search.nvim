import requests
import subprocess
import sys
import json
import os
import aiohttp
import asyncio


def generate_search_query(user_input: str) -> str:
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("Error: GROQ_API_KEY environment variable is not set.")
        return user_input

    url = "https://api.groq.com/openai/v1/chat/completions"

    system_instruction = (
        "You are a GitHub Search Query Generator. "
        "Convert the user's intent into a precise GitHub search string.\n"
        "Rules:\n"
        "1. Output ONLY the query string.\n"
        '2. ONLY quote values if they strictly contain spaces (e.g. topic:"data science"). NEVER quote single words (e.g. topic:python).\n'
        "3. Use keywords instead of strict topics if the topic name is uncertain.\n"
        "4. Do NOT use Markdown or explain your answer."
    )

    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_input},
        ],
        "temperature": 0.1,  # low creativity
    }

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]

        return content.strip().replace(
            "`", ""
        )  # if the llm was bad we remove backticks manually

    except Exception as e:
        print(f"DEBUG ERROR: {e}")

        if "response" in locals():
            print(f"DEBUG RESPONSE: {response.text}")

        return user_input


def get_token_from_cli():
    try:
        result = subprocess.run(
            ["gh", "auth", "token"], capture_output=True, text=True
        )  # we try to run this so that we can get more calls raising the number of results we can get
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


# dead code right now, but may become useful
def contents(repo: str) -> list[str]:
    api_contents = f"https://api.github.com/repos/{repo}/contents"

    response = requests.get(api_contents, headers=headers)

    if response.status_code != 200:
        print(response.text)
        limit = response.headers.get("X-RateLimit-Limit")
        print(limit)
        raise Exception(f"Error: {response.status_code}")
    return response.json()


async def has_active_actions(session, repo_full_name, headers):
    url = f"https://api.github.com/repos/{repo_full_name}/actions/runs?per_page=1"

    try:
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                # if 'total_count' > 0, they have run Actions at least once.
                return data.get("total_count", 0) > 0
        return False
    except Exception:
        return False


def search(query: str, limit: int = 5) -> list[str]:
    if limit > 50:  # no one needs more than 50 results
        raise Exception(
            "Limit must be less than or equal to 50. Please reduce the limit and try again."
        )
    url = "https://api.github.com/search/repositories"

    params = {"q": query, "per_page": limit}

    response = requests.get(
        url, params=params, headers=headers
    )  # let requests handle encoding otherwise if we have spaces in the query it will break

    if response.status_code != 200:
        print(f"Error searching GitHub: {response.status_code}")
        print(response.json())
        return []
    return response.json().get("items", [])


async def process_repos(results, headers) -> list[str]:
    async with aiohttp.ClientSession() as session:
        tasks = [
            has_active_actions(session, repo["full_name"], headers) for repo in results
        ]

        results_flags = await asyncio.gather(*tasks)

        useful_repos = [
            repo for repo, has_actions in zip(results, results_flags) if has_actions
        ]
        return useful_repos


def main():
    useful_repos = list()
    query = generate_search_query(sys.argv[1])
    print(repr(query))
    results = search(query, limit=10)

    if not results:
        print("No results found. :(")
        return

    useful_repos = asyncio.run(process_repos(results, headers))

    for repo in useful_repos:
        print(json.dumps(repo))


if __name__ == "__main__":
    main()
