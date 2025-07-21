import requests
from typing import List, Optional
from urllib.parse import urlparse
import os
from dotenv import load_dotenv

load_dotenv()


class GitRepoFetcher:
    """Fetches repository names from GitHub organizations or URLs."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.session = requests.Session()
        if self.token:
            self.session.headers.update({"Authorization": f"token {self.token}"})

    def get_repos_from_org(self, org_name: str) -> List[str]:
        """Get all repository names from a GitHub organization."""
        repos = []
        page = 1

        while True:
            url = f"https://api.github.com/orgs/{org_name}/repos"
            params = {"page": page, "per_page": 100, "type": "all"}

            response = self.session.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            if not data:
                break

            repos.extend([repo["name"] for repo in data])
            page += 1

        return repos

    def get_repo_from_url(self, url: str) -> Optional[str]:
        """Extract repo name from GitHub URL."""
        parsed = urlparse(url)

        if parsed.netloc not in ["github.com", "www.github.com"]:
            return None

        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) >= 2:
            return path_parts[1]

        return None

    def get_org_from_url(self, url: str) -> Optional[str]:
        """Extract org name from GitHub URL."""
        parsed = urlparse(url)

        if parsed.netloc not in ["github.com", "www.github.com"]:
            return None

        path_parts = parsed.path.strip("/").split("/")
        if len(path_parts) >= 1:
            return path_parts[0]

        return None


def get_repo_names(
    org_or_url: Optional[str] = None, token: Optional[str] = None
) -> List[str]:
    """Get repo names from org name, URL, or environment variables."""
    if org_or_url is None:
        org_or_url = os.getenv("GITHUB_ORG_URL")
        if not org_or_url:
            raise ValueError(
                "No organization or URL provided and GITHUB_ORG_URL not set"
            )

    fetcher = GitRepoFetcher(token)

    if org_or_url.startswith(("http://", "https://")):
        org_name = fetcher.get_org_from_url(org_or_url)
        if org_name:
            return fetcher.get_repos_from_org(org_name)
        else:
            repo_name = fetcher.get_repo_from_url(org_or_url)
            return [repo_name] if repo_name else []
    else:
        return fetcher.get_repos_from_org(org_or_url)


# Example usage
if __name__ == "__main__":
    # Example: Get all repos using environment variables
    try:
        repos = get_repo_names()
        print(f"Found {len(repos)} repositories from environment settings")
        for repo in repos[:5]:  # Show first 5 repos
            print(f"  - {repo}")
    except ValueError as e:
        print(f"Error: {e}")
