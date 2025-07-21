from git_repo import get_repo_names


repos = get_repo_names()
print(f"Found {len(repos)} repositories from environment settings")

for repo in repos[:5]:  # Show first 5 repos
    print(f"  - {repo}")
