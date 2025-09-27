import os
import re
import base64
import asyncio
import requests
from pr_agent.custom_handlers.jira_testcase_handler import GitLabMRHelper
from pr_agent.log import get_logger

class ConfluenceMRHandler:
    def __init__(self, merge_request_url=None):
        """
        Initialize the handler to fetch Confluence content using ID from MR description.
        
        Environment variables required:
        - For Confluence:
            JIRA_DOMAIN: The Jira domain (e.g., "blackduck")
            JIRA_EMAIL: Email for Confluence Basic Auth
            JIRA_API_TOKEN: API token for Confluence
            ENABLE_MR_CONFLUENCE: If "true", will look for Confluence ID in MR description
        - For GitLab repository:
            gitlab__personal_access_token: GitLab personal access token
            
        Args:
            merge_request_url (str): URL to the GitLab merge request containing Confluence ID
        """
        # Check if MR Confluence lookup is enabled
        self.use_mr_confluence = self._parse_bool_env("ENABLE_MR_CONFLUENCE", False)
        
        # Initialize attributes to None first
        self.gitlab_helper = None
        self.repository_url = None
        self.gitlab_token = None
        self.jira_domain = None
        self.email = None
        self.auth_token = None
        self.base_url = None
        self.headers = None
        
        if not self.use_mr_confluence:
            return
            
        if not merge_request_url:
            raise ValueError("merge_request_url is required to extract Confluence ID when ENABLE_MR_CONFLUENCE is true")
            
        self.repository_url = merge_request_url
        self.gitlab_token = os.getenv("gitlab__personal_access_token")
        
        # Initialize GitLab helper
        if not self.gitlab_token:
            raise ValueError("gitlab__personal_access_token environment variable is required for GitLab")
        self.gitlab_helper = GitLabMRHelper(merge_request_url, self.gitlab_token)
        
        # Initialize Confluence configuration
        self.jira_domain = os.getenv("JIRA_DOMAIN")
        self.email = os.getenv("JIRA_EMAIL")
        self.auth_token = os.getenv("JIRA_API_TOKEN")
        
        # Validate required environment variables
        if not self.jira_domain:
            raise ValueError("JIRA_DOMAIN environment variable is required")
        if not self.email:
            raise ValueError("JIRA_EMAIL environment variable is required")
        if not self.auth_token:
            raise ValueError("JIRA_API_TOKEN environment variable is required")
            
        # Set up Confluence API configuration
        base_url = f"https://{self.jira_domain}.atlassian.net"
        self.base_url = f"{base_url}/wiki/rest/api"
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Set up Basic Auth
        credentials = f"{self.email}:{self.auth_token}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        self.headers["Authorization"] = f"Basic {encoded_credentials}"
        
    def _parse_bool_env(self, env_var_name, default=False):
        """Parse boolean environment variables."""
        value = os.getenv(env_var_name, str(default).lower())
        return value.lower() in ('true', 'yes', '1', 't', 'y')
    
    def fetch_content_by_id(self, content_id):
        """
        Fetches content from Confluence API by ID and returns title and body storage value.
        
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
                
    def extract_confluence_id(self, description):
        """
        Extracts Confluence page ID from MR description.
        Expected format in description: [confluence-id: 123456]
        
        Args:
            description (str): The MR description text
            
        Returns:
            str: The extracted Confluence ID, or None if not found
        """
        pattern = r'\[confluence-id:\s*(\d+)\]'
        match = re.search(pattern, description)
        if match:
            return match.group(1)
        return None

    def get_confluence_content(self):
        """
        Extracts Confluence ID from MR description and fetches the corresponding content.
        If ENABLE_MR_CONFLUENCE is not set to true, returns empty result without error.
        
        Returns:
            dict: Contains 'title' and 'body_value' fields, or error info
        """
        # If MR Confluence lookup is not enabled, return empty result
        if not self.use_mr_confluence:
            return {
                "id": "confluence-content",
                "title": "",
                "body_value": "",
                "status": "success"
            }
            
        try:
            # Get MR description
            mr_description = self.gitlab_helper.get_mr_description()
            
            # Extract Confluence ID
            confluence_id = self.extract_confluence_id(mr_description)
            if not confluence_id:
                return {
                    "id": "confluence-content",
                    "error": "No Confluence ID found in MR description. Expected format: [confluence-id: 123456]",
                    "status": "error"
                }
            # Fetch content directly using our own implementation
            return self.fetch_content_by_id(confluence_id)
            
        except Exception as e:
            get_logger().error(f"Error fetching Confluence content: {e}")
            return {
                "id": "confluence-content",
                "error": f"Error fetching Confluence content: {str(e)}",
                "status": "error"
            }
    
    async def get_confluence_content_async(self):
        """
        Async version to fetch Confluence content using ID from MR description.
        
        Returns:
            dict: Contains 'title' and 'body_value' fields, or error info
        """
        return await asyncio.to_thread(self.get_confluence_content)

# Example usage:
def example_usage():
    """
    Example of how to use the ConfluenceMRHandler class.
    
    Required environment variables:
    - gitlab__personal_access_token (your GitLab token)
    - JIRA_DOMAIN (e.g., "blackduck")
    - JIRA_EMAIL (your Confluence email)
    - JIRA_API_TOKEN (your Confluence API token)
    
    The MR description should contain the Confluence ID in this format:
    [confluence-id: 123456]
    """
    try:
        # Initialize with MR URL
        mr_url = "https://gitlab.com/your-org/your-repo/-/merge_requests/123"
        handler = ConfluenceMRHandler(merge_request_url=mr_url)
        
        # Get Confluence content
        content = handler.get_confluence_content()
        
        # Print results
        if content.get('status') == 'success':
            print(f"Title: {content.get('title')}")
            print(f"Content: {content.get('body_value')}")
        else:
            print(f"Error: {content.get('error')}")
        
        return content
        
    except ValueError as e:
        print(f"Configuration error: {e}")
        return None

# Async example:
async def async_example():
    """
    Async example of using the ConfluenceMRHandler class.
    """
    try:
        mr_url = "https://gitlab.com/your-org/your-repo/-/merge_requests/123"
        handler = ConfluenceMRHandler(merge_request_url=mr_url)
        content = await handler.get_confluence_content_async()
        return content
    except ValueError as e:
        print(f"Configuration error: {e}")
        return None
