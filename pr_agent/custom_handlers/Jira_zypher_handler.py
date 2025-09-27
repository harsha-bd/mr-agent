import os
import re
import base64
import requests
import urllib.parse
import asyncio
import sys
from pr_agent.log import get_logger

try:
    from requests.auth import HTTPBasicAuth
except ImportError:
    # Fallback implementation if requests.auth is not available
    class HTTPBasicAuth:
        def __init__(self, username, password):
            self.username = username
            self.password = password
        
        def __call__(self, r):
            import base64
            credentials = f"{self.username}:{self.password}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            r.headers['Authorization'] = f'Basic {encoded_credentials}'
            return r

class GitLabMRHelper:
    def __init__(self, mr_url, token):
        self.mr_url = mr_url
        self.token = token
        self.project_path, self.mr_id = self.get_project_path_and_mr_id(mr_url)
        self.source_branch = self.get_source_branch()

    def get_project_path_and_mr_id(self, mr_url):
        # Remove protocol and domain, split by '/'
        url = mr_url.split('://', 1)[-1].split('/', 1)[-1]
        parts = url.strip('/').split('/')
        try:
            mr_index = parts.index('merge_requests')
            if parts[mr_index - 1] == '-':
                project_path = '/'.join(parts[:mr_index - 1])
            else:
                project_path = '/'.join(parts[:mr_index])
            mr_id = parts[mr_index + 1] 
            return urllib.parse.quote(project_path, safe=''), mr_id
        except (ValueError, IndexError):
            raise ValueError("Invalid MR URL format")
        
    def get_file_diffs(self):
        """Returns a dict: {file_path: [added_lines]}"""
        mr_data = self.get_mr_changes()
        diffs = {}
        for change in mr_data['changes']:
            diff = change.get('diff', '')
            added_lines = []
            for line in diff.split('\n'):
                if line.startswith('+') and not line.startswith('+++'):
                    added_lines.append(line[1:])
            diffs[change['new_path']] = added_lines
        return diffs
    
    def get_mr_changes(self):
        url = f"https://gitlab.tools.duckutil.net/api/v4/projects/{self.project_path}/merge_requests/{self.mr_id}/changes"
        headers = {"PRIVATE-TOKEN": self.token}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    def get_source_branch(self):
        mr_data = self.get_mr_changes()
        return mr_data['source_branch']

    def get_changed_files(self):
        mr_data = self.get_mr_changes()
        return [change['new_path'] for change in mr_data['changes']]

    def get_file_content(self, file_path):
        encoded_path = urllib.parse.quote_plus(file_path)
        url = f"https://gitlab.tools.duckutil.net/api/v4/projects/{self.project_path}/repository/files/{encoded_path}/raw?ref={self.source_branch}"
        headers = {"PRIVATE-TOKEN": self.token}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    
    def get_mr_details(self):
        url = f"https://gitlab.tools.duckutil.net/api/v4/projects/{self.project_path}/merge_requests/{self.mr_id}"
        headers = {"PRIVATE-TOKEN": self.token}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    def get_mr_description(self):
        mr_details = self.get_mr_details()
        return mr_details.get("description", "")


class JiraTestCaseHandler:
    def __init__(self, pr_url: str):
        self.jira_base_url = "https://api.zephyrscale.smartbear.com"
        self.jira_token = os.getenv("ZEPHYR_SCALE_TOKEN")  # Set your JWT token in env var
        self.auth_header = {
            "Authorization": f"Bearer {self.jira_token}",
            "Content-Type": "application/json"
        }
        self.pr_url = pr_url
        # self.git_provider = get_git_provider_with_context(pr_url)
        
        # JIRA credentials for issue fetching
        self.jira_domain = os.getenv("JIRA_DOMAIN")  # e.g., "blackduck"
        self.jira_email = os.getenv("JIRA_EMAIL")
        self.jira_api_token = os.getenv("JIRA_API_TOKEN")
    
    def fetch_jira_issue_info(self, issue_key):
        """Fetches JIRA issue information using Atlassian REST API."""
        if not all([self.jira_domain, self.jira_email, self.jira_api_token]):
            print("JIRA credentials not configured. Set JIRA_DOMAIN, JIRA_EMAIL, and JIRA_API_TOKEN environment variables.")
            return None
            
        base_url = f"https://{self.jira_domain}.atlassian.net"
        issue_url = f"{base_url}/rest/api/3/issue/{issue_key}"
        comment_url = f"{issue_url}/comment"

        auth = HTTPBasicAuth(self.jira_email, self.jira_api_token)
        headers = {
            "Accept": "application/json"
        }

        try:
            # Fetch issue details
            response = requests.get(issue_url, headers=headers, auth=auth, verify=False)
            if response.status_code != 200:
                print(f"Failed to fetch JIRA issue details for {issue_key}: {response.status_code} - {response.text}")
                return None

            issue_data = response.json()
            fields = issue_data.get("fields", {})

            summary = fields.get("summary", "")
            description_content = fields.get("description", {})
            description = ""
            if description_content and "content" in description_content:
                # Extract text from Atlassian Document Format
                description = self._extract_text_from_adf(description_content)
            
            status = fields.get("status", {}).get("name", "")
            labels = fields.get("labels", [])
            attachments = fields.get("attachment", [])

            # Fetch comments
            comments = []
            comments_response = requests.get(comment_url, headers=headers, auth=auth, verify=False)
            if comments_response.status_code == 200:
                comments_data = comments_response.json()
                for comment in comments_data.get("comments", []):
                    if "body" in comment:
                        comment_text = self._extract_text_from_adf(comment["body"])
                        if comment_text:
                            comments.append(comment_text)

            return {
                "id": issue_key,
                "key": issue_key,
                "name": summary,
                "objective": description,
                "status": status,
                "labels": labels,
                "comments": comments,
                "attachments": [{"filename": att.get("filename", ""), "content": att.get("content", "")} for att in attachments],
                "source": "jira"
            }

        except Exception as e:
            print(f"Exception fetching JIRA issue {issue_key}: {e}")
            return None
    
    def _extract_text_from_adf(self, adf_content):
        """Extract plain text from Atlassian Document Format."""
        if not adf_content or not isinstance(adf_content, dict):
            return ""
        
        text_parts = []
        
        def extract_text_recursive(node):
            if isinstance(node, dict):
                if node.get("type") == "text":
                    text_parts.append(node.get("text", ""))
                elif "content" in node:
                    for child in node["content"]:
                        extract_text_recursive(child)
            elif isinstance(node, list):
                for item in node:
                    extract_text_recursive(item)
        
        extract_text_recursive(adf_content)
        return " ".join(text_parts).strip()

    def fetch_test_case_steps(self, test_case_id):
        """Fetches all test steps for a given test case ID from Zephyr Scale."""
        url = f"{self.jira_base_url}/v2/testcases/{test_case_id}/teststeps"
        try:
            response = requests.get(url, headers=self.auth_header ,  verify=False)
            if response.status_code == 200:
                data = response.json()
                steps = []
                for value in data.get("values", []):
                    inline = value.get("inline", {})
                    steps.append({
                        "description": inline.get("description"),
                        "testData": inline.get("testData"),
                        "expectedResult": inline.get("expectedResult"),
                    })
                return steps
            else:
                print(f"Failed to fetch steps for {test_case_id}: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            print(f"Exception fetching steps for {test_case_id}: {e}")
            return []
    

    def fetch_test_case_info(self, test_case_id):
        """Tries to fetch from Zephyr Scale first, then from JIRA if not found."""
        # First try Zephyr Scale
        url = f"{self.jira_base_url}/v2/testcases/{test_case_id}"
        try:
            response = requests.get(url, headers=self.auth_header, verify=False)
            if response.status_code == 200:
                data = response.json()
                return {
                    "id": data.get("id"),
                    "key": data.get("key"),
                    "name": data.get("name"),
                    "objective": data.get("objective"),
                    "status": data.get("status", {}).get("name", "N/A"),
                    "source": "zephyr"
                }
            else:
                print(f"Failed to fetch from Zephyr Scale {test_case_id}: {response.status_code}")
                # If Zephyr fails, try JIRA
                jira_result = self.fetch_jira_issue_info(test_case_id)
                if jira_result:
                    return jira_result
                
                return {"id": test_case_id, "error": "Not found in Zephyr Scale or JIRA"}
        except Exception as e:
            print(f"Exception fetching from Zephyr Scale {test_case_id}: {e}")
            # If Zephyr fails with exception, try JIRA
            jira_result = self.fetch_jira_issue_info(test_case_id)
            if jira_result:
                return jira_result
            
            return {"id": test_case_id, "error": str(e)}
        


    async def extract_and_fetch_test_cases(self):
        '''Extracts all CNC-XXXX or CNCQA-XXXX patterns from MR source code and MR description, and fetches their JIRA info.'''
        # pattern = re.compile(r'\b(CNCQA-\w+|CNC-\w+)\b') 
        # -> export JIRA_TESTCASE_REGEX="\\b(CNCQA-\\w+|CNC-\\w+)\\b"
        regex_pattern = os.getenv("JIRA_TESTCASE_REGEX")
        if not regex_pattern:
            get_logger().error("No regex given in JIRA_TESTCASE_REGEX environment variable. Exiting JIRA test case extraction.")
            return []
        pattern = re.compile(regex_pattern)
        test_case_ids = set()
        results = []

        # Initialize GitLabMRHelper with MR URL and token
        gitlab_token = os.getenv("gitlab__personal_access_token")

        gitlab_helper = GitLabMRHelper(self.pr_url, gitlab_token)

        # try:
        #     changed_files = gitlab_helper.get_changed_files()
        #     for file_path in changed_files:
        #         try:
        #             content = gitlab_helper.get_file_content(file_path)
        #             matches = pattern.findall(content)
        #             test_case_ids.update(matches)
        #         except Exception as e:
        #             print(f"Error reading file {file_path}: {e}")
        # except Exception as e:
        #     print(f"Error fetching changed files: {e}")
        #     return []


        # Extract from MR description
        try:
            mr_description = gitlab_helper.get_mr_description()
            matches = pattern.findall(mr_description)
            test_case_ids.update(matches)
        except Exception as e:
            print(f"Error fetching MR description: {e}")

        # Extract from added lines in diffs
        try:
            file_diffs = gitlab_helper.get_file_diffs()
            for file_path, added_lines in file_diffs.items():
                content = '\n'.join(added_lines)
                matches = pattern.findall(content)
                test_case_ids.update(matches)
        except Exception as e:
            print(f"Error fetching changed files: {e}")
            return []
        

        for test_case_id in sorted(test_case_ids):
            info = await asyncio.to_thread(self.fetch_test_case_info, test_case_id)
            
            # Only fetch steps if it's from Zephyr Scale
            steps = []
            if info.get("source") == "zephyr":
                steps = await asyncio.to_thread(self.fetch_test_case_steps, test_case_id)
            
            result_item = {
                "test_case_id": test_case_id,
                "id": info.get("id"),
                "key": info.get("key", test_case_id),
                "name": info.get("name"),
                "objective": info.get("objective"),
                "status": info.get("status", "N/A"),
                "source": info.get("source", "unknown"),
            }
            
            # Add source-specific fields
            if info.get("source") == "zephyr":
                result_item["steps"] = steps
            elif info.get("source") == "jira":
                result_item["labels"] = info.get("labels", [])
                result_item["comments"] = info.get("comments", [])
                result_item["attachments"] = info.get("attachments", [])
            
            results.append(result_item)
        # print(results)
        return results

    async def get_cases_markdown(self):
        """Returns a markdown string for human-readable output."""
        cases = await self.extract_and_fetch_test_cases()
        if not cases:
            return "No test cases found in MR source code."

        lines = []
        for case in cases:
            source = case.get('source', 'unknown').title()
            lines.append(
                f"- **{case.get('key', case.get('test_case_id'))}** ({source}): {case.get('name', 'No name')}\n"
                f"  - Objective: {case.get('objective', 'No objective')}\n"
                f"  - Status: {case.get('status', 'N/A')}\n"
            )
            
            # Handle Zephyr Scale specific data
            if case.get('source') == 'zephyr':
                steps = case.get("steps", [])
                if steps:
                    lines.append("  - Steps:")
                    for idx, step in enumerate(steps, 1):
                        lines.append(f"    {idx}. Description: {step.get('description', '').strip() or 'N/A'}\n")
                        if step.get('testData'):
                            lines.append(f"       Test Data: {step.get('testData')}\n")
                        if step.get('expectedResult'):
                            lines.append(f"       Expected Result: {step.get('expectedResult')}\n")
            
            # Handle JIRA specific data
            elif case.get('source') == 'jira':
                labels = case.get("labels", [])
                if labels:
                    lines.append(f"  - Labels: {', '.join(labels)}\n")
                
                comments = case.get("comments", [])
                if comments:
                    lines.append("  - Comments:")
                    for comment in comments[:3]:  # Limit to first 3 comments
                        lines.append(f"    - {comment[:100]}{'...' if len(comment) > 100 else ''}\n")
                
                attachments = case.get("attachments", [])
                if attachments:
                    lines.append("  - Attachments:")
                    for att in attachments:
                        lines.append(f"    - {att.get('filename', 'Unknown file')}\n")
            
            lines.append("")  # Add a blank line between cases
        return "\n".join(lines)

    async def handle(self, as_markdown=False):
        """Main entry point. Returns markdown if as_markdown=True, else list of dicts."""
        if as_markdown:
            return await self.get_cases_markdown()
        return await self.extract_and_fetch_test_cases()