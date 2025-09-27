import os
import re
import base64
import requests
import urllib.parse
import asyncio
import sys
from pr_agent.log import get_logger

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
        url = f"{self.jira_base_url}/v2/testcases/{test_case_id}"
        try:
            response = requests.get(url, headers=self.auth_header , verify=False)
            if response.status_code == 200:
                data = response.json()
                return {
                    "id": data.get("id"),
                    "key": data.get("key"),
                    "name": data.get("name"),
                    "objective": data.get("objective"),
                    "status": data.get("status", {}).get("name", "N/A"),
                    # "priority": data.get("priority", {}).get("id", "N/A"),
                }
            else:
                print(f"Failed to fetch {test_case_id}: {response.status_code} - {response.text}")
                return {"id": test_case_id, "error": "Not found or unauthorized"}
        except Exception as e:
            print(f"Exception fetching test case {test_case_id}: {e}")
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
            steps = await asyncio.to_thread(self.fetch_test_case_steps, test_case_id)
            results.append({
                "test_case_id": test_case_id,
                "id": info.get("id"),
                "key": info.get("key", test_case_id),
                "name": info.get("name"),
                "objective": info.get("objective"),
                "status": info.get("status", "N/A"),
                "steps": steps,  # <-- add this line
            })
        # print(results)
        return results

    async def get_cases_markdown(self):
        """Returns a markdown string for human-readable output."""
        cases = await self.extract_and_fetch_test_cases()
        if not cases:
            return "No test cases found in MR source code."

        lines = []
        for case in cases:
            lines.append(
                f"- **{case.get('key', case.get('test_case_id'))}**: {case.get('name', 'No name')}\n"
                f"  - Objective: {case.get('objective', 'No objective')}\n"
                f"  - Status: {case.get('status', 'N/A')}\n"
                # f"  - Priority: {case.get('priority', 'N/A')}\n"
            )
            steps = case.get("steps", [])
            if steps:
                lines.append("  - Steps:")
                for idx, step in enumerate(steps, 1):
                    lines.append(f"    {idx}. Description: {step.get('description', '').strip() or 'N/A'}\n")
                    if step.get('testData'):
                        lines.append(f"       Test Data: {step.get('testData')}\n")
                    if step.get('expectedResult'):
                        lines.append(f"       Expected Result: {step.get('expectedResult')}\n")
            lines.append("")  # Add a blank line between cases
        return "\n".join(lines)

    async def handle(self, as_markdown=False):
        """Main entry point. Returns markdown if as_markdown=True, else list of dicts."""
        if as_markdown:
            return await self.get_cases_markdown()
        return await self.extract_and_fetch_test_cases()
