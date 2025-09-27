import requests
import asyncio
import os
import base64
from pr_agent.log import get_logger
from pr_agent.custom_handlers.jira_testcase_handler import GitLabMRHelper

class Coding_standards_Handler:
    def __init__(self, merge_request_url=None):
        """
        Initialize the API reader with configuration from environment variables.
        
        Environment variables required:
        - For Confluence:
            JIRA_DOMAIN: The Jira domain (e.g., "blackduck")
            JIRA_EMAIL: Email for Confluence Basic Auth
            JIRA_API_TOKEN: API token for Confluence
            CONFLUENCE_ID: The Confluence page ID to fetch
        - For GitLab repository:
            gitlab__personal_access_token: GitLab personal access token
            CODING_STANDARDS_FILE: Path to coding standards file in repository (default: CODING_STANDARDS.md)
        - For source selection:
            GITLAB_CODING_STANDARDS: If "true", fetch from GitLab repository
            CONFLUENCE_CODING_STANDARDS: If "true", fetch from Confluence
            
        Args:
            merge_request_url (str, optional): URL to the GitLab merge request
                Required when GITLAB_CODING_STANDARDS=true
        """
        # Source selection flags
        self.use_gitlab = self._parse_bool_env("GITLAB_CODING_STANDARDS")
        self.use_confluence = self._parse_bool_env("CONFLUENCE_CODING_STANDARDS", default=True)  # Default to Confluence if not specified
        
        # GitLab configuration
        self.repository_url = merge_request_url if merge_request_url else None  # Only set if provided
        self.gitlab_token = os.getenv("gitlab__personal_access_token")  
        self.coding_standards_file = os.getenv("CODING_STANDARDS_FILE", "CODING_STANDARDS.md")
        self.gitlab_branch = os.getenv("GITLAB_BRANCH", "main")
        
        # Confluence configuration
        self.jira_domain = os.getenv("JIRA_DOMAIN")
        self.email = os.getenv("JIRA_EMAIL")
        self.auth_token = os.getenv("JIRA_API_TOKEN")
        self.confluence_id = os.getenv("CONFLUENCE_ID")
        
        # Validate configuration based on selected sources
        if self.use_confluence:
            if not self.jira_domain:
                raise ValueError("JIRA_DOMAIN environment variable is required for Confluence")
            if not self.email:
                raise ValueError("JIRA_EMAIL environment variable is required for Confluence")
            if not self.auth_token:
                raise ValueError("JIRA_API_TOKEN environment variable is required for Confluence")
            if not self.confluence_id:
                raise ValueError("CONFLUENCE_ID environment variable is required for Confluence")
                
            base_url = f"https://{self.jira_domain}.atlassian.net"
            self.base_url = f"{base_url}/wiki/rest/api"
            self.headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            # Set up Confluence Basic Auth
            credentials = f"{self.email}:{self.auth_token}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            self.headers["Authorization"] = f"Basic {encoded_credentials}"
            
        if self.use_gitlab:
            if not self.gitlab_token:
                raise ValueError("gitlab__personal_access_token environment variable is required for GitLab")
            if not self.repository_url:
                raise ValueError("merge_request_url parameter is required when GITLAB_CODING_STANDARDS=true")
    
    def _parse_bool_env(self, env_var_name, default=False):
        """
        Parse boolean environment variables (true/false, yes/no, 1/0)
        
        Args:
            env_var_name (str): Name of environment variable
            default (bool): Default value if env var is not set
            
        Returns:
            bool: Parsed boolean value
        """
        value = os.getenv(env_var_name, str(default).lower())
        return value.lower() in ('true', 'yes', '1', 't', 'y')
    
    def fetch_content_by_id(self, content_id):
        """
        Fetches content from API by ID and returns title and body storage value.
        
        Args:
            content_id (str): The ID of the content to fetch
            
        Returns:
            dict: Contains 'title' and 'body_value' fields, or error info
        """
        url = f"{self.base_url}/content/{content_id}?expand=body.storage"
        
        try:
            response = requests.get(url, headers=self.headers, verify=False)
            if response.status_code == 200:
                data = response.json()
                
                # Extract title
                title = data.get("title", "No title available")
                
                # Extract body storage value
                body_value = ""
                body = data.get("body", {})
                if body:
                    storage = body.get("storage", {})
                    if storage:
                        body_value = storage.get("value", "No content available")
                
                return {
                    "id": content_id,
                    "title": title,
                    "body_value": body_value,
                    "status": "success"
                }
            else:
                return {
                    "id": content_id,
                    "error": f"API request failed: {response.status_code} - {response.text}",
                    "status": "error"
                }
                
        except Exception as e:
            return {
                "id": content_id,
                "error": f"Exception occurred: {str(e)}",
                "status": "error"
            }
    
    async def fetch_content_async(self, content_id):
        """
        Async version of fetch_content_by_id.
        
        Args:
            content_id (str): The ID of the content to fetch
            
        Returns:
            dict: Contains 'title' and 'body_value' fields, or error info
        """
        return await asyncio.to_thread(self.fetch_content_by_id, content_id)
    
    async def fetch_configured_content(self):
        """
        Fetches the content using the configured CONFLUENCE_ID from environment.
        
        Returns:
            dict: Contains 'title' and 'body_value' fields, or error info
        """
        return await self.fetch_content_async(self.confluence_id)
    
    def get_configured_content(self):
        """
        Synchronous version to fetch the configured Confluence page.
        
        Returns:
            dict: Contains 'title' and 'body_value' fields, or error info
        """
        return self.fetch_content_by_id(self.confluence_id)
    
    def fetch_multiple_contents(self, content_ids):
        """
        Fetches multiple contents by their IDs.
        
        Args:
            content_ids (list): List of content IDs to fetch
            
        Returns:
            list: List of content dictionaries
        """
        results = []
        for content_id in content_ids:
            result = self.fetch_content_by_id(content_id)
            results.append(result)
        return results
    
    async def fetch_multiple_contents_async(self, content_ids):
        """
        Async version to fetch multiple contents concurrently.
        
        Args:
            content_ids (list): List of content IDs to fetch
            
        Returns:
            list: List of content dictionaries
        """
        tasks = [self.fetch_content_async(content_id) for content_id in content_ids]
        return await asyncio.gather(*tasks)
    
    def get_contents_markdown(self, contents):
        """
        Converts content list to markdown format for human-readable output.
        
        Args:
            contents (list): List of content dictionaries
            
        Returns:
            str: Markdown formatted string
        """
        if not contents:
            return "No content found."
        
        lines = []
        for content in contents:
            if content.get("status") == "error":
                lines.append(f"- **{content.get('id')}**: Error - {content.get('error')}")
            else:
                title = content.get('title', 'No title')
                body_preview = content.get('body_value', '')[:200]  # First 200 chars
                if len(content.get('body_value', '')) > 200:
                    body_preview += "..."
                
                lines.append(f"- **{content.get('id')}**: {title}")
                lines.append(f"  - Content: {body_preview}")
            lines.append("")  # Blank line between items
        
        return "\n".join(lines)
        
    def fetch_coding_standards_from_gitlab(self, branch=None):
        """
        Fetches coding standards from a GitLab repository file.
        The repository_url parameter should be a merge request URL.
        
        Args:
            branch (str, optional): Branch name (defaults to source branch of MR)
            
        Returns:
            dict: Contains 'title' and 'body_value' fields, or error info
        """
        if not self.repository_url or not self.gitlab_token:
            return {
                "id": "gitlab-coding-standards",
                "error": "GitLab merge request URL or token not provided",
                "status": "error"
            }
            
        try:
            # Initialize GitLab helper from imported class with MR URL
            gitlab_helper = GitLabMRHelper(self.repository_url, self.gitlab_token)
            
            # Use source branch from MR if branch not specified
            branch_to_use = branch or gitlab_helper.source_branch or self.gitlab_branch
            
            # Get the file content
            file_content = gitlab_helper.get_file_content(self.coding_standards_file)
            
            if not file_content:
                return {
                    "id": "gitlab-coding-standards",
                    "error": f"Failed to retrieve coding standards file: {self.coding_standards_file}",
                    "status": "error"
                }
                
            return {
                "id": "gitlab-coding-standards",
                "title": f"Coding Standards from {self.coding_standards_file}",
                "body_value": file_content,
                "status": "success"
            }
            
        except Exception as e:
            get_logger().error(f"Error retrieving coding standards from GitLab: {e}")
            return {
                "id": "gitlab-coding-standards",
                "error": f"Exception retrieving coding standards: {str(e)}",
                "status": "error"
            }
    
    async def fetch_coding_standards_from_gitlab_async(self, branch=None):
        """
        Async version of fetch_coding_standards_from_gitlab.
        
        Args:
            branch (str, optional): Branch name (defaults to self.gitlab_branch)
            
        Returns:
            dict: Contains 'title' and 'body_value' fields, or error info
        """
        return await asyncio.to_thread(self.fetch_coding_standards_from_gitlab, branch)

    async def fetch_coding_standards(self):
        """
        Fetches coding standards from the configured source (GitLab or Confluence).
        
        Returns:
            dict: Contains 'title', 'body_value', and 'source' fields, or error info
        """
        result = None
        
        if self.use_gitlab:
            get_logger().info("Fetching coding standards from GitLab repository")
            result = await self.fetch_coding_standards_from_gitlab_async()
            if result and result.get('status') == 'success':
                result['source'] = 'gitlab'
                return result
                
        if self.use_confluence:
            get_logger().info("Fetching coding standards from Confluence")
            result = await self.fetch_configured_content()
            if result and result.get('status') == 'success':
                result['source'] = 'confluence'
                return result
        
        # If we reach here, both sources failed or were not configured
        if result:
            # Return the last error
            return result
        else:
            return {
                "id": "coding-standards",
                "error": "No valid source configured for coding standards",
                "status": "error"
            }
    
    def get_coding_standards(self):
        """
        Synchronous version to fetch coding standards from configured source.
        
        Returns:
            dict: Contains 'title', 'body_value', and 'source' fields, or error info
        """
        result = None
        
        if self.use_gitlab:
            get_logger().info("Fetching coding standards from GitLab repository")
            result = self.fetch_coding_standards_from_gitlab()
            if result and result.get('status') == 'success':
                result['source'] = 'gitlab'
                return result
                
        if self.use_confluence:
            get_logger().info("Fetching coding standards from Confluence")
            result = self.get_configured_content()
            if result and result.get('status') == 'success':
                result['source'] = 'confluence'
                return result
        
        # If we reach here, both sources failed or were not configured
        if result:
            # Return the last error
            return result
        else:
            return {
                "id": "coding-standards",
                "error": "No valid source configured for coding standards",
                "status": "error"
            }

# Example usage:
async def example_usage():
    """
    Example of how to use the Coding_standards_Handler class.
    
    Required environment variables depend on configuration:
    - For Confluence:
        CONFLUENCE_CODING_STANDARDS=true
        JIRA_DOMAIN (e.g., "blackduck")
        JIRA_EMAIL (your Confluence email)
        JIRA_API_TOKEN (your Confluence API token)
        CONFLUENCE_ID (the page ID to fetch)
        
    - For GitLab:
        GITLAB_CODING_STANDARDS=true
        gitlab__personal_access_token (your GitLab token)
        merge_request_url parameter
        CODING_STANDARDS_FILE (path to coding standards file, default: CODING_STANDARDS.md)
    """
    try:
        # Example 1: Using only Confluence (default)
        # os.environ["CONFLUENCE_CODING_STANDARDS"] = "true"
        # os.environ["GITLAB_CODING_STANDARDS"] = "false"
        # handler = Coding_standards_Handler()  # No merge_request_url needed
        
        # Example 2: Using both sources (GitLab first, then Confluence as fallback)
        # os.environ["GITLAB_CODING_STANDARDS"] = "true"
        # os.environ["CONFLUENCE_CODING_STANDARDS"] = "true"
        # mr_url = "https://gitlab.com/your-org/your-repo/-/merge_requests/123"
        # handler = Coding_standards_Handler(merge_request_url=mr_url)
        
        # Example 3: Using only GitLab
        os.environ["GITLAB_CODING_STANDARDS"] = "true"
        os.environ["CONFLUENCE_CODING_STANDARDS"] = "false"
        mr_url = "https://gitlab.com/your-org/your-repo/-/merge_requests/123"
        handler = Coding_standards_Handler(merge_request_url=mr_url)
        
        # Fetch coding standards from configured source (GitLab or Confluence)
        content = await handler.fetch_coding_standards()
        print(f"Coding standards from {content.get('source')}: {content.get('title')}")
        
        # Convert to markdown for human-readable output
        markdown = handler.get_contents_markdown([content])
        print(markdown)
        
        return content
        
    except ValueError as e:
        print(f"Configuration error: {e}")
        return None

# Synchronous example:
def sync_example():
    """
    Synchronous example to fetch coding standards from configured source.
    """
    try:
        # If using only Confluence, no need for merge_request_url
        if os.getenv("GITLAB_CODING_STANDARDS", "").lower() != "true":
            handler = Coding_standards_Handler()  # No merge_request_url needed
        else:
            # Using GitLab requires merge_request_url
            mr_url = "https://gitlab.com/your-org/your-repo/-/merge_requests/123"
            handler = Coding_standards_Handler(merge_request_url=mr_url)
        content = handler.get_coding_standards()
        return content
    except ValueError as e:
        print(f"Configuration error: {e}")
        return None
