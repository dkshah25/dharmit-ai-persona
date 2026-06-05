import os
import json
import base64
import requests
from pypdf import PdfReader
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_USERNAME = "dkshah25"

def get_github_headers():
    headers = {
        "Accept": "application/vnd.github.v3+json"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers

def github_request_get(url):
    """
    Wrapper for GitHub API GET requests.
    If the provided token is invalid (401), falls back to unauthenticated public requests.
    """
    headers = get_github_headers()
    response = requests.get(url, headers=headers)
    if response.status_code == 401 and GITHUB_TOKEN:
        print("[Ingestion Warning] GitHub Token in env is invalid (401 Bad Credentials). Retrying without token authentication...")
        public_headers = {
            "Accept": "application/vnd.github.v3+json"
        }
        response = requests.get(url, headers=public_headers)
    return response

def fetch_repositories(username):
    url = f"https://api.github.com/users/{username}/repos?per_page=100&type=owner"
    print(f"Fetching repositories for {username}...")
    response = github_request_get(url)
    if response.status_code != 200:
        print(f"Error fetching repositories: {response.status_code} - {response.text}")
        return []
    repos = response.json()
    print(f"Found {len(repos)} repositories.")
    return repos

def fetch_readme(username, repo_name):
    url = f"https://api.github.com/repos/{username}/{repo_name}/readme"
    response = github_request_get(url)
    if response.status_code != 200:
        # Try raw fallback
        for branch in ["main", "master"]:
            raw_url = f"https://raw.githubusercontent.com/{username}/{repo_name}/{branch}/README.md"
            raw_res = requests.get(raw_url)
            if raw_res.status_code == 200:
                return raw_res.text
        return ""
    
    data = response.json()
    content_b64 = data.get("content", "")
    if content_b64:
        try:
            return base64.b64decode(content_b64).decode("utf-8", errors="ignore")
        except Exception as e:
            print(f"Error decoding README for {repo_name}: {e}")
    
    # Try using download URL if content is missing
    download_url = data.get("download_url")
    if download_url:
        dl_response = github_request_get(download_url)
        if dl_response.status_code == 200:
            return dl_response.text
            
    return ""

def fetch_languages(username, repo_name):
    url = f"https://api.github.com/repos/{username}/{repo_name}/languages"
    response = github_request_get(url)
    if response.status_code == 200:
        return response.json()
    return {}

def fetch_commits(username, repo_name, max_commits=15):
    url = f"https://api.github.com/repos/{username}/{repo_name}/commits?per_page={max_commits}"
    response = github_request_get(url)
    if response.status_code != 200:
        return []
    
    commits_data = response.json()
    commits = []
    if isinstance(commits_data, list):
        for c in commits_data:
            if isinstance(c, dict):
                commit_info = c.get("commit", {})
                sha = c.get("sha", "")[:7]
                author = commit_info.get("author", {})
                message = commit_info.get("message", "")
                date = author.get("date", "")
                author_name = author.get("name", "")
                commits.append({
                    "sha": sha,
                    "author": author_name,
                    "date": date,
                    "message": message
                })
    return commits

def parse_resume(pdf_path):
    print(f"Parsing resume PDF at {pdf_path}...")
    if not os.path.exists(pdf_path):
        print(f"Resume PDF not found at {pdf_path}. Skipping resume extraction.")
        return ""
    
    try:
        reader = PdfReader(pdf_path)
        text = ""
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text += f"\n--- Page {i+1} ---\n" + page_text
        print(f"Successfully extracted {len(text)} characters from resume.")
        return text
    except Exception as e:
        print(f"Error parsing resume PDF: {e}")
        return ""

def ingest_data(resume_pdf_path, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Process Resume
    resume_text = parse_resume(resume_pdf_path)
    if resume_text:
        resume_data = {
            "source": "resume",
            "content": resume_text,
            "metadata": {
                "title": "Resume of Dharmit Shah",
                "source": "resume"
            }
        }
        with open(os.path.join(output_dir, "resume.json"), "w", encoding="utf-8") as f:
            json.dump(resume_data, f, indent=2)
        print("Resume parsed and saved.")
    
    # 2. Process GitHub
    repos = fetch_repositories(GITHUB_USERNAME)
    github_documents = []
    
    for repo in repos:
        repo_name = repo.get("name")
        description = repo.get("description") or ""
        html_url = repo.get("html_url")
        topics = repo.get("topics") or []
        stars = repo.get("stargazers_count", 0)
        forks = repo.get("forks_count", 0)
        watchers = repo.get("watchers_count", 0)
        created_at = repo.get("created_at")
        updated_at = repo.get("updated_at")
        
        print(f"Processing repository: {repo_name}...")
        
        # Fetch README
        readme_content = fetch_readme(GITHUB_USERNAME, repo_name)
        
        # Fetch Languages
        languages = fetch_languages(GITHUB_USERNAME, repo_name)
        languages_str = ", ".join(languages.keys()) if languages else "None specified"
        
        # Fetch Commit History
        commits = fetch_commits(GITHUB_USERNAME, repo_name)
        
        # Build structured repository document
        repo_doc = {
            "source": "github",
            "repository": repo_name,
            "url": html_url,
            "description": description,
            "languages": list(languages.keys()),
            "topics": topics,
            "stats": {
                "stars": stars,
                "forks": forks,
                "watchers": watchers
            },
            "timestamps": {
                "created_at": created_at,
                "updated_at": updated_at
            },
            "commits": commits,
            "readme": readme_content,
            "metadata": {
                "source": "github",
                "repository": repo_name,
                "url": html_url,
                "languages": languages_str,
                "topics": ", ".join(topics)
            }
        }
        
        github_documents.append(repo_doc)
        
        # Save individual repo document
        safe_name = repo_name.replace("/", "_")
        with open(os.path.join(output_dir, f"repo_{safe_name}.json"), "w", encoding="utf-8") as f:
            json.dump(repo_doc, f, indent=2)
            
    print(f"Ingested {len(github_documents)} GitHub repositories.")
    return len(github_documents)

if __name__ == "__main__":
    workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    resume_path = os.path.join(workspace_dir, "data", "resume.pdf")
    output_path = os.path.join(workspace_dir, "data", "processed")
    ingest_data(resume_path, output_path)
