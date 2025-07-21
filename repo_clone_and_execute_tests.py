import json
import os
import shutil
import subprocess
import stat
import time
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass
from git_repo import get_repo_names


@dataclass
class DetailedTestResults:
    """Parse and structure test results from JSON data."""

    def __init__(self, json_data: Dict[str, Any]):
        self.json_data = json_data
        self.passed = json_data.get("passed", 0)
        self.failed = json_data.get("failed", 0)
        self.skipped = json_data.get("skipped", 0)
        self.error = json_data.get("error", 0)
        self.total = json_data.get("total", 0)
        self.duration = json_data.get("duration", 0.0)
        self.test_details = json_data.get("test_details", [])


class RepoTestRunner:
    """Clones repositories and runs tests using Docker Compose."""

    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.repos_dir = self.base_dir / "repos"
        self.results_dir = self.base_dir / "results"
        self.docker_available = self._check_docker_availability()

        # Create directories
        self.repos_dir.mkdir(exist_ok=True)
        self.results_dir.mkdir(exist_ok=True)

    def _check_docker_availability(self) -> bool:
        """Check if Docker is available and running."""
        try:
            result = subprocess.run(
                ["docker", "version"], capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except (
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
            FileNotFoundError,
        ):
            return False

    def _remove_readonly(self, func, path, _):
        """Error handler for removing read-only files on Windows."""
        os.chmod(path, stat.S_IWRITE)
        func(path)

    def _safe_remove_directory(self, path: Path) -> bool:
        """Safely remove directory with Windows-compatible handling."""
        if not path.exists():
            return True

        max_retries = 3
        for attempt in range(max_retries):
            try:
                # First try to make all files writable
                for root, dirs, files in os.walk(path):
                    for name in files:
                        file_path = os.path.join(root, name)
                        try:
                            os.chmod(file_path, stat.S_IWRITE)
                        except OSError:
                            pass

                # Remove the directory
                shutil.rmtree(path, onerror=self._remove_readonly)
                return True

            except (OSError, PermissionError) as e:
                if attempt < max_retries - 1:
                    print(
                        f"   Retry {attempt + 1}/{max_retries} for removing {path.name}..."
                    )
                    time.sleep(1)  # Wait before retry
                    continue
                else:
                    print(f"   Warning: Could not remove {path}: {e}")
                    return False

        return False

    def _clone_repo_locally(self, org_name: str, repo_name: str) -> bool:
        """Clone repository to local repos directory."""
        repo_path = self.repos_dir / repo_name

        if repo_path.exists():
            print(f"   Cleaning up existing repository...")
            if not self._safe_remove_directory(repo_path):
                print(
                    f"   Warning: Could not completely clean {repo_name}, continuing anyway..."
                )

        clone_url = f"https://github.com/{org_name}/{repo_name}.git"
        try:
            print(f"   Cloning from {clone_url}...")
            subprocess.run(
                ["git", "clone", clone_url, str(repo_path)],
                capture_output=True,
                text=True,
                check=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to clone {repo_name}: {e.stderr}")
            return False

    def _run_tests_with_compose(self, repo_name: str) -> Dict[str, Any]:
        """Run tests using Docker Compose."""
        repo_path = self.repos_dir / repo_name
        results_file = self.results_dir / f"{repo_name}_results.json"
        test_scripts_path = self.base_dir / "repo_test_scripts"
        docker_script_path = self.base_dir / "docker_test_script.sh"

        try:
            # Build the test environment
            print(f"   Building Docker environment...")
            subprocess.run(
                ["docker-compose", "build", "test-runner"],
                cwd=self.base_dir,
                check=True,
                capture_output=True,
            )

            # Run tests in the container using the script
            cmd = [
                "docker-compose",
                "run",
                "--rm",
                "-v",
                f"{repo_path}:/workspace/current_repo",
                "-v",
                f"{test_scripts_path}:/workspace/test_scripts",
                "-v",
                f"{results_file.parent}:/workspace/results",
                "-v",
                f"{docker_script_path}:/workspace/docker_test_script.sh",
                "test-runner",
                "bash",
                "/workspace/docker_test_script.sh",
                repo_name,
            ]

            print(f"   Executing tests in Docker container...")
            result = subprocess.run(
                cmd,
                cwd=self.base_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",  # Handle encoding errors gracefully
            )

            # Read results
            results_data = None
            test_success = False

            if results_file.exists():
                try:
                    with open(results_file, "r", encoding="utf-8") as f:
                        results_data = json.load(f)
                    print(f"   ✅ Results file found and loaded successfully")

                    # Determine success based on test results, not just container exit code
                    if isinstance(results_data, dict):
                        failed_count = results_data.get("failed", 0)
                        error_count = results_data.get("error", 0)
                        total_count = results_data.get("total", 0)

                        # Success if there are tests and no failures/errors
                        test_success = (
                            total_count > 0 and failed_count == 0 and error_count == 0
                        )
                        print(
                            f"   Test analysis: {total_count} total, {failed_count} failed, {error_count} errors -> {'SUCCESS' if test_success else 'FAILURE'}"
                        )

                except json.JSONDecodeError as e:
                    results_data = {"error": f"Failed to parse JSON: {str(e)}"}
                    print(f"   ⚠️ JSON decode error: {e}")
            else:
                print(f"   ⚠️ Results file {results_file} not found")
                results_data = {"error": "Results file not created"}

            return {
                "repo_name": repo_name,
                "success": test_success,  # Use test results for success, not container exit code
                "exit_code": result.returncode,
                "output": result.stdout,
                "error_output": result.stderr,
                "results_data": results_data,
            }

        except subprocess.CalledProcessError as e:
            return {
                "repo_name": repo_name,
                "success": False,
                "error": f"Docker compose failed: {e.stderr}",
                "exit_code": e.returncode,
            }

    def clone_and_test_repo(
        self, repo_url: str, org_name: str, repo_name: str
    ) -> Dict[str, Any]:
        """Clone a repository and run tests."""
        # Check Docker availability first
        if not self.docker_available:
            return {
                "repo_name": repo_name,
                "success": False,
                "error": "Docker is not available or not running. Please start Docker Desktop and try again.",
                "exit_code": -1,
            }

        # Clone repository locally first
        if not self._clone_repo_locally(org_name, repo_name):
            return {
                "repo_name": repo_name,
                "success": False,
                "error": "Failed to clone repository",
                "exit_code": -1,
            }

        # Run tests using Docker Compose only
        print(f"   Using Docker Compose for testing...")
        return self._run_tests_with_compose(repo_name)

    def run_tests_for_repos(
        self, repo_names: List[str], org_name: str
    ) -> List[Dict[str, Any]]:
        """Run tests for multiple repositories."""
        results = []

        for repo_name in repo_names:
            print(f"🔄 Processing repository: {repo_name}")
            repo_url = f"https://github.com/{org_name}/{repo_name}"
            result = self.clone_and_test_repo(repo_url, org_name, repo_name)
            results.append(result)

            # Display results for this repo
            self._display_repo_results(result)
            print("-" * 50)

        return results

    def _display_repo_results(self, result: Dict[str, Any]):
        """Display formatted results for a single repository."""
        repo_name = result["repo_name"]
        print(f"\n📦 Repository: {repo_name} (tested with: docker)")

        if not result["success"]:
            print(f"   ❌ Failed (exit code: {result.get('exit_code', 'unknown')})")
            if "error" in result:
                print(f"   Error: {result['error']}")
            return

        results_data = result.get("results_data")
        if results_data and not isinstance(results_data.get("error"), str):
            detailed_results = DetailedTestResults(results_data)

            print("📊 Detailed Test Results:")
            print(f"   Passed:   {detailed_results.passed}")
            print(f"   Failed:   {detailed_results.failed}")
            print(f"   Skipped:  {detailed_results.skipped}")
            print(f"   Errors:   {detailed_results.error}")
            print(f"   Total:    {detailed_results.total}")
            print(f"   Duration: {detailed_results.duration:.2f}s")

            # Show individual test details if available
            if detailed_results.test_details:
                print("\n📋 Individual Test Results:")
                for test in detailed_results.test_details:
                    status = "✅" if test.get("outcome") == "passed" else "❌"
                    print(
                        f"   {status} {test.get('nodeid', 'unknown')} - {test.get('outcome', 'unknown')}"
                    )
        else:
            print(
                f"   ⚠️ Test completed but results parsing failed (exit code: {result['exit_code']})"
            )
            if results_data and isinstance(results_data.get("error"), str):
                print(f"   JSON Error: {results_data['error']}")

    def cleanup(self):
        """Clean up temporary files and containers."""
        try:
            subprocess.run(
                ["docker-compose", "down", "-v"],
                cwd=self.base_dir,
                capture_output=True,
            )
        except subprocess.CalledProcessError:
            pass

        # Clean up repos directory with safe removal
        print("Cleaning up repositories...")
        for repo_dir in self.repos_dir.iterdir():
            if repo_dir.is_dir():
                self._safe_remove_directory(repo_dir)

        # Optionally clean up repos directory
        # shutil.rmtree(self.repos_dir, ignore_errors=True)


def main():
    """Main function to run tests on repositories."""
    try:
        # Get repository names using the existing git_repo module
        repo_names = [name for name in get_repo_names() if name != "eval"]

        if not repo_names:
            print("No repositories found.")
            return

        print(f"Found {len(repo_names)} repositories to test.")

        # Initialize test runner
        runner = RepoTestRunner()

        # Check Docker availability and exit if not available
        if not runner.docker_available:
            print("\n❌ Docker is not available or not running.")
            print("   Please start Docker Desktop and ensure it's running.")
            print("   This tool requires Docker to run tests in isolation.")
            print("\nExiting...")
            return
        else:
            print(
                "\n✅ Docker is available. Tests will run in containerized environment.\n"
            )

        # Get organization name (assuming first repo URL structure)
        from git_repo import GitRepoFetcher

        fetcher = GitRepoFetcher()

        # Try to get org name from environment or assume from first repo
        org_name = os.getenv("GITHUB_ORG")
        if not org_name:
            org_url = os.getenv("GITHUB_ORG_URL")
            if org_url:
                org_name = fetcher.get_org_from_url(org_url)

        if not org_name:
            raise ValueError(
                "Could not determine organization name. Set GITHUB_ORG or GITHUB_ORG_URL environment variable."
            )

        # Run tests for all repositories
        all_results = runner.run_tests_for_repos(repo_names, org_name)

        # Summary
        successful = sum(1 for r in all_results if r["success"])
        print(
            f"\n🎯 Summary: {successful}/{len(all_results)} repositories tested successfully"
        )

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
