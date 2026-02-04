import re
import json
import math
import requests
import warnings
import urllib.parse
from tqdm import tqdm
from html import unescape
from typing import List, Dict, Any
from bs4 import BeautifulSoup, NavigableString
from concurrent.futures import ThreadPoolExecutor
from urllib3.exceptions import InsecureRequestWarning

def list_all_html_files_in_collection(
    collection_id: int,
    auth_token: str,
    search_query: str = ".html",
    page_size: int = 100,
    timeout: int = 15,
) -> List[Dict[str, Any]]:
    """
    Returns ALL .html files from a collection using total_count for pagination.
    """

    warnings.simplefilter("ignore", InsecureRequestWarning)

    url = f"https://aiforce.hcltech.com/dms/collection/{collection_id}"
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Accept": "application/json",
    }

    def fetch_page(page_number: int) -> Dict[str, Any]:
        params = {
            "page_number": page_number,
            "page_size": page_size,
            "search_query": search_query,
        }
        resp = requests.get(url, headers=headers, params=params, timeout=timeout, verify=False)
        resp.raise_for_status()
        return resp.json()["data"]

    # ✅ First call – get total_count
    first_page = fetch_page(1)
    total_count = first_page.get("total_count", 0)
    items = first_page.get("items", [])

    if total_count == 0:
        return []

    # ✅ Calculate number of pages
    total_pages = math.ceil(total_count / page_size)

    # ✅ Fetch remaining pages
    for page in range(2, total_pages + 1):
        data = fetch_page(page)
        items.extend(data.get("items", []))

    result = [
            {
                "id": item.get("id"),
                "file_name": item.get("file_name")
            }
            for item in items
            if isinstance(item, dict)  # guard against non-dict items
        ]

    return result

def get_file_content(file_id: int, auth_token: str):
    url = "https://aiforce.hcltech.com/dms/file_download"

    params = {
        "file_id": file_id
    }

    warnings.simplefilter("ignore", InsecureRequestWarning)

    headers = {"Authorization": f"Bearer {auth_token}", "Accept": "application/json"}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15, verify=False)
        resp.raise_for_status()
        return resp.text
    except requests.exceptions.HTTPError as http_err:
        return f"HTTP error occurred: {http_err}"
        if http_err.response is not None:
            return f"Response body: {http_err.response.text}"
    except requests.exceptions.RequestException as err:
        return f"Request failed: {err}"
 
def invalid_navigation_paths_single_file(html: str) -> List[Dict[str, Any]]:
    """
    Parse HTML (string), extract navigation paths from <div class="Step_1">,
    validate them, and return detailed information about invalid paths.
 
    Invalid criteria:
      1) Incorrect spacing around '&amp;gt;' (must be ' &amp;gt; ' with one space on both sides)
      2) Contains CamelCase-like words (sub-words with >= 2 uppercase letters AND at least one lowercase)
 
    Returns:
      List[Dict[str, Any]]: List of dictionaries containing:
        - navigation_path: The full navigation path
        - issues: List of issue types ("incorrect_spacing", "camel_case")
        - camel_case_words: List of words that have camel case (if applicable)
    """
 
    # Regex: camel-like (≥2 uppercase and ≥1 lowercase) anywhere in the sub-word
    CAMEL_LIKE_RE = re.compile(r'(?=.*[A-Z].*[A-Z])(?=.*[a-z])')
 
    soup = BeautifulSoup(html, "html.parser")
    nav_paths = []
 
    # --- Extract navigation paths ---
    for div in soup.find_all("div", class_="Step_1"):
        parts = []
 
        for elem in div.children:
            if isinstance(elem, NavigableString):
                txt = str(elem)
                if txt.strip():
                    # Normalize any variant of &gt; into a canonical token
                    # Replace raw '>' or decoded variants to ' &amp;gt; '
                    # We handle multiple forms: '>', '&gt;', '&amp;gt;', '&amp;amp;gt;'
                    txt_unesc = unescape(txt)
                    # Replace any '>' (possibly with surrounding spaces) into ' &amp;gt; '
                    txt_unesc = re.sub(r'\s*&gt;\s*|\s*>\s*', ' &amp;gt; ', txt_unesc)
                    parts.append(txt_unesc)
            else:
                classes = elem.get("class") or []
                text = elem.get_text(" ", strip=True)
                if "Command_002c_menucascade_002c_uicontrol" in classes:
                    parts.append(text)
                else:
                    # If other inline elements contribute to the visible path, include them
                    # (comment this out if you truly want to restrict to that specific class)
                    parts.append(text)
 
        if parts:
            # Join and normalize spacing:
            combined = " ".join(parts)
            # Collapse multiple spaces
            combined = re.sub(r'\s+', ' ', combined).strip()
 
            # Final normalization: ensure all '>' are '&amp;gt;' with single spaces
            combined = unescape(combined)
            combined = re.sub(r'\s*&gt;\s*|\s*>\s*', ' &amp;gt; ', combined)
            combined = re.sub(r'\s+', ' ', combined).strip()
 
            nav_paths.append(combined)
 
    invalid_paths = []
 
    # --- Validate each path ---
    for nav_path in nav_paths:
        issues = []
        camel_case_words = []
        incorrect_spacing = False
        has_camel_case = False
 
        # Spacing check: if '&amp;gt;' appears, every occurrence must be " &amp;gt; "
        if "&amp;gt;" in nav_path:
            # Replace valid occurrences with a placeholder and see if any raw '&amp;gt;' remain
            placeholder = nav_path.replace(" &amp;gt; ", " [ARROW] ")
            if "&amp;gt;" in placeholder:
                incorrect_spacing = True
                issues.append("incorrect_spacing")
 
        # CamelCase-like check: split around properly spaced arrows, then split into sub-words
        parts = re.split(r'\s*&amp;gt;\s*', nav_path)
        for part in parts:
            for word in part.split():
                for sub_word in re.split(r"[\/\\\-_'\(\)]", word):
                    if not sub_word:
                        continue
                    # Detect camel-like (≥2 uppercase AND ≥1 lowercase)
                    if CAMEL_LIKE_RE.search(sub_word):
                        has_camel_case = True
                        if sub_word not in camel_case_words:
                            camel_case_words.append(sub_word)
 
        if has_camel_case:
            issues.append("camel_case")
 
        if issues:
            invalid_path_obj = {
                "navigation_path": nav_path,
                "issues": issues,
            }
            
            if camel_case_words:
                invalid_path_obj["camel_case_words"] = camel_case_words
            
            invalid_paths.append(invalid_path_obj)
 
    return invalid_paths

def invalid_navigation_paths_in_collection(
    collection_id: int,
    auth_token: str,
    search_query: str = ".html",
    use_multithreading: bool = True,
    max_workers: int = 5,
) -> List[Dict[str, Any]]:
    """
    Fetch all HTML files from a collection, validate navigation paths in each file,
    and return a curated list of files with invalid navigation paths.
    
    Args:
        collection_id: The ID of the collection to search
        auth_token: Authentication token for API requests
        search_query: Search query to filter files (default: ".html")
        use_multithreading: Whether to use multithreading for file downloads (default: True)
        max_workers: Maximum number of concurrent workers for multithreading (default: 5)
    
    Returns:
        List[Dict[str, Any]]: List of dictionaries containing:
            - file_id: The file ID
            - file_name: The file name
            - invalid_count: Number of invalid navigation paths in the file
            - invalid_paths: List of invalid navigation path objects (from invalid_navigation_paths_single_file)
    """
    
    print(f"📁 Fetching HTML files from collection {collection_id}...")
    
    # Get all HTML files in the collection
    html_files = list_all_html_files_in_collection(
        collection_id=collection_id,
        auth_token=auth_token,
        search_query=search_query
    )
    
    if not html_files:
        return []
        
    results = []
    
    def process_file(file_info: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single file and return results if invalid paths found."""
        file_id = file_info["id"]
        file_name = file_info["file_name"]
        
        # Get file content
        html_content = get_file_content(file_id, auth_token)
        
        # Check if download was successful
        if isinstance(html_content, str) and html_content.startswith(("HTTP error", "Request failed")):
            return {
                "file_id": file_id,
                "file_name": file_name,
                "error": html_content,
                "invalid_count": 0,
                "invalid_paths": []
            }
        
        # Validate navigation paths
        invalid_paths = invalid_navigation_paths_single_file(html_content)
        
        if invalid_paths:
            return {
                "file_id": file_id,
                "file_name": file_name,
                "invalid_count": len(invalid_paths),
                "invalid_paths": invalid_paths
            }
        
        return None
    
    # Process files with or without multithreading
    if use_multithreading:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_file, file_info) for file_info in html_files]
            
            for future in tqdm(futures, desc="Validating files", total=len(html_files)):
                result = future.result()
                if result:
                    results.append(result)
    else:
        for file_info in tqdm(html_files, desc="Validating files"):
            result = process_file(file_info)
            if result:
                results.append(result)
    
    return results


if __name__ == "__main__":

    auth_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3OTkzMTYwNTIsInVzZXJfaWQiOjExMTcsInVzZXJfbmFtZSI6InJhdG5lc2hwYXNpMDMiLCJlbWFpbF9pZCI6InBhc2lyYXRuZXNoLnRhcmFrYW50QGhjbHRlY2guY29tIiwib3JnX2lkIjoxLCJyb2xlIjoiQ29udHJpYnV0b3IiLCJyb2xlX2lkIjozLCJwcm9qZWN0X2lkIjoyNSwiaXNfc3VwZXJfYWRtaW4iOmZhbHNlLCJyb2xlX3R5cGVfaWQiOjMsInJvbGVfdHlwZSI6IkNvbnRyaWJ1dG9yIiwidXNlcl90eXBlIjoicGxhdGZvcm1fdXNlciIsImp0aWQiOiI1ZjI3MjYzNTc5MTI0ZDFmOTMwMWNmZjU2ZDE3MmM4ZCJ9.gk5l1bwxBMl61Rjti67bXwKpr7IUv6EFyAr6YuJx8RxQ1uzCJy4ZefKNySVAF18HzOJcAKLovZsRm8_QYx7xoP3MNlYYy7kF5-bqoduLVTPVTbi2xoYs3WvuTsDIKTPixXXc-xXzOEDCHfzRVdELe9c8Lxnj7GdP-AXtJneJjPKqsYc8MFMPVvD9lblb7H4-ryfcIPC5RiSrEUah3T-euutzetwFWhBbgxM8tTZAk-_5_UcsDy5D-Kc0fQbkzM711EX47V_4npZz1dnXJWPkcipxV8DGCKQ86qVrvpyYGLDae0wCHkAaofQbUB1iZv5FpuOtmqnmqPYsxoBUGHqOew"

    data = invalid_navigation_paths_in_collection(collection_id=1152, auth_token=auth_token)

    file_path = "initial_files_invalid_navigation_path.json"

    try:
        # Open the file in write mode ('w')
        with open(file_path, 'w') as json_file:
            # Use json.dump() to write the data to the file
            json.dump(data, json_file, indent=4)
        print(f"Successfully wrote data to {file_path}")
    except IOError as e:
        print(f"Error writing to file: {e}")


""""
{
  "list_all_html_files_in_collection": {
    "collection_id": 1152,
    "auth_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3OTkzMTYwNTIsInVzZXJfaWQiOjExMTcsInVzZXJfbmFtZSI6InJhdG5lc2hwYXNpMDMiLCJlbWFpbF9pZCI6InBhc2lyYXRuZXNoLnRhcmFrYW50QGhjbHRlY2guY29tIiwib3JnX2lkIjoxLCJyb2xlIjoiQ29udHJpYnV0b3IiLCJyb2xlX2lkIjozLCJwcm9qZWN0X2lkIjoyNSwiaXNfc3VwZXJfYWRtaW4iOmZhbHNlLCJyb2xlX3R5cGVfaWQiOjMsInJvbGVfdHlwZSI6IkNvbnRyaWJ1dG9yIiwidXNlcl90eXBlIjoicGxhdGZvcm1fdXNlciIsImp0aWQiOiI1ZjI3MjYzNTc5MTI0ZDFmOTMwMWNmZjU2ZDE3MmM4ZCJ9.gk5l1bwxBMl61Rjti67bXwKpr7IUv6EFyAr6YuJx8RxQ1uzCJy4ZefKNySVAF18HzOJcAKLovZsRm8_QYx7xoP3MNlYYy7kF5-bqoduLVTPVTbi2xoYs3WvuTsDIKTPixXXc-xXzOEDCHfzRVdELe9c8Lxnj7GdP-AXtJneJjPKqsYc8MFMPVvD9lblb7H4-ryfcIPC5RiSrEUah3T-euutzetwFWhBbgxM8tTZAk-_5_UcsDy5D-Kc0fQbkzM711EX47V_4npZz1dnXJWPkcipxV8DGCKQ86qVrvpyYGLDae0wCHkAaofQbUB1iZv5FpuOtmqnmqPYsxoBUGHqOew",
    "search_query": ".html",
    "page_size": 10,
    "timeout": 5
  },
  "get_file_content": {
    "file_id": 8356,
    "auth_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3OTkzMTYwNTIsInVzZXJfaWQiOjExMTcsInVzZXJfbmFtZSI6InJhdG5lc2hwYXNpMDMiLCJlbWFpbF9pZCI6InBhc2lyYXRuZXNoLnRhcmFrYW50QGhjbHRlY2guY29tIiwib3JnX2lkIjoxLCJyb2xlIjoiQ29udHJpYnV0b3IiLCJyb2xlX2lkIjozLCJwcm9qZWN0X2lkIjoyNSwiaXNfc3VwZXJfYWRtaW4iOmZhbHNlLCJyb2xlX3R5cGVfaWQiOjMsInJvbGVfdHlwZSI6IkNvbnRyaWJ1dG9yIiwidXNlcl90eXBlIjoicGxhdGZvcm1fdXNlciIsImp0aWQiOiI1ZjI3MjYzNTc5MTI0ZDFmOTMwMWNmZjU2ZDE3MmM4ZCJ9.gk5l1bwxBMl61Rjti67bXwKpr7IUv6EFyAr6YuJx8RxQ1uzCJy4ZefKNySVAF18HzOJcAKLovZsRm8_QYx7xoP3MNlYYy7kF5-bqoduLVTPVTbi2xoYs3WvuTsDIKTPixXXc-xXzOEDCHfzRVdELe9c8Lxnj7GdP-AXtJneJjPKqsYc8MFMPVvD9lblb7H4-ryfcIPC5RiSrEUah3T-euutzetwFWhBbgxM8tTZAk-_5_UcsDy5D-Kc0fQbkzM711EX47V_4npZz1dnXJWPkcipxV8DGCKQ86qVrvpyYGLDae0wCHkAaofQbUB1iZv5FpuOtmqnmqPYsxoBUGHqOew"
  },
  "invalid_navigation_paths_single_file": {
    "html": "<html></html>"
  },
  "invalid_navigation_paths_in_collection": {
    "collection_id": 1152,
    "auth_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3OTkzMTYwNTIsInVzZXJfaWQiOjExMTcsInVzZXJfbmFtZSI6InJhdG5lc2hwYXNpMDMiLCJlbWFpbF9pZCI6InBhc2lyYXRuZXNoLnRhcmFrYW50QGhjbHRlY2guY29tIiwib3JnX2lkIjoxLCJyb2xlIjoiQ29udHJpYnV0b3IiLCJyb2xlX2lkIjozLCJwcm9qZWN0X2lkIjoyNSwiaXNfc3VwZXJfYWRtaW4iOmZhbHNlLCJyb2xlX3R5cGVfaWQiOjMsInJvbGVfdHlwZSI6IkNvbnRyaWJ1dG9yIiwidXNlcl90eXBlIjoicGxhdGZvcm1fdXNlciIsImp0aWQiOiI1ZjI3MjYzNTc5MTI0ZDFmOTMwMWNmZjU2ZDE3MmM4ZCJ9.gk5l1bwxBMl61Rjti67bXwKpr7IUv6EFyAr6YuJx8RxQ1uzCJy4ZefKNySVAF18HzOJcAKLovZsRm8_QYx7xoP3MNlYYy7kF5-bqoduLVTPVTbi2xoYs3WvuTsDIKTPixXXc-xXzOEDCHfzRVdELe9c8Lxnj7GdP-AXtJneJjPKqsYc8MFMPVvD9lblb7H4-ryfcIPC5RiSrEUah3T-euutzetwFWhBbgxM8tTZAk-_5_UcsDy5D-Kc0fQbkzM711EX47V_4npZz1dnXJWPkcipxV8DGCKQ86qVrvpyYGLDae0wCHkAaofQbUB1iZv5FpuOtmqnmqPYsxoBUGHqOew"
  }
}
"""