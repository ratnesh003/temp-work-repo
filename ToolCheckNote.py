import re
import json
import math
import requests
import warnings
import urllib.parse
from tqdm import tqdm
from bs4 import BeautifulSoup
from typing import List, Dict, Any
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

def check_single_file_note(
    html_content: str,
    source_file: str
) -> Dict[str, Any]:
    """
    Validate Note usage in a single HTML document.
    """

    soup = BeautifulSoup(html_content, "html.parser")

    note_divs = soup.find_all("div", class_=re.compile(r"Note"))

    found_note_in_note_div = False
    found_note_outside_note_div = False

    # Notes inside grey box
    for div in note_divs:
        if "Note:" in div.get_text():
            found_note_in_note_div = True

    # Notes anywhere else
    for element in soup.find_all(string=lambda t: t and "Note:" in t):
        parent = element.find_parent()
        if parent:
            if not parent.find_parent("div", class_=re.compile(r"Note")) \
               and parent.get("class") != ["Note"]:
                found_note_outside_note_div = True

    if found_note_outside_note_div:
        return {
            "file": source_file,
            "status": "Invalid",
            "error": "'Note:' found outside designated grey box",
            "details": {
                "note_inside_box": found_note_in_note_div,
                "note_outside_box": True,
            },
        }

    return {
        "file": source_file,
        "status": "Valid",
        "error": "",
        "details": {
            "note_inside_box": found_note_in_note_div,
            "note_outside_box": False,
        },
    }

def check_note(
    collection_id: int,
    auth_token: str
) -> List[Dict[str, Any]]:
    """
    Orchestrates note validation across a DMS collection.
    Returns only invalid results.
    """

    html_items = list_all_html_files_in_collection(
        collection_id=collection_id,
        auth_token=auth_token,
        search_query=".html",
        page_size=100,
    )

    results: List[Dict[str, Any]] = []

    for item in tqdm(html_items):
        content = get_file_content(
            file_id=item["id"],
            auth_token=auth_token,
        )

        file_result = check_single_file_note(
            html_content=content,
            source_file=item["file_name"],
        )

        if file_result["status"] == "Invalid":
            results.append(file_result)

    return results

if __name__ == "__main__":

    auth_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3OTkzMTYwNTIsInVzZXJfaWQiOjExMTcsInVzZXJfbmFtZSI6InJhdG5lc2hwYXNpMDMiLCJlbWFpbF9pZCI6InBhc2lyYXRuZXNoLnRhcmFrYW50QGhjbHRlY2guY29tIiwib3JnX2lkIjoxLCJyb2xlIjoiQ29udHJpYnV0b3IiLCJyb2xlX2lkIjozLCJwcm9qZWN0X2lkIjoyNSwiaXNfc3VwZXJfYWRtaW4iOmZhbHNlLCJyb2xlX3R5cGVfaWQiOjMsInJvbGVfdHlwZSI6IkNvbnRyaWJ1dG9yIiwidXNlcl90eXBlIjoicGxhdGZvcm1fdXNlciIsImp0aWQiOiI1ZjI3MjYzNTc5MTI0ZDFmOTMwMWNmZjU2ZDE3MmM4ZCJ9.gk5l1bwxBMl61Rjti67bXwKpr7IUv6EFyAr6YuJx8RxQ1uzCJy4ZefKNySVAF18HzOJcAKLovZsRm8_QYx7xoP3MNlYYy7kF5-bqoduLVTPVTbi2xoYs3WvuTsDIKTPixXXc-xXzOEDCHfzRVdELe9c8Lxnj7GdP-AXtJneJjPKqsYc8MFMPVvD9lblb7H4-ryfcIPC5RiSrEUah3T-euutzetwFWhBbgxM8tTZAk-_5_UcsDy5D-Kc0fQbkzM711EX47V_4npZz1dnXJWPkcipxV8DGCKQ86qVrvpyYGLDae0wCHkAaofQbUB1iZv5FpuOtmqnmqPYsxoBUGHqOew"

    data = check_note(collection_id=1152, auth_token=auth_token)

    file_path = "initial_files_invalid_notes.json"

    try:
        # Open the file in write mode ('w')
        with open(file_path, 'w') as json_file:
            # Use json.dump() to write the data to the file
            json.dump(data, json_file, indent=4)
        print(f"Successfully wrote data to {file_path}")
    except IOError as e:
        print(f"Error writing to file: {e}")

"""
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
  "check_single_file_note": {
    "html_content": "<html></html>",
    "source_file": "myfile.html"
  },
  "check_note_in_collection_by_id": {
    "collection_id": 1152,
    "auth_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3OTkzMTYwNTIsInVzZXJfaWQiOjExMTcsInVzZXJfbmFtZSI6InJhdG5lc2hwYXNpMDMiLCJlbWFpbF9pZCI6InBhc2lyYXRuZXNoLnRhcmFrYW50QGhjbHRlY2guY29tIiwib3JnX2lkIjoxLCJyb2xlIjoiQ29udHJpYnV0b3IiLCJyb2xlX2lkIjozLCJwcm9qZWN0X2lkIjoyNSwiaXNfc3VwZXJfYWRtaW4iOmZhbHNlLCJyb2xlX3R5cGVfaWQiOjMsInJvbGVfdHlwZSI6IkNvbnRyaWJ1dG9yIiwidXNlcl90eXBlIjoicGxhdGZvcm1fdXNlciIsImp0aWQiOiI1ZjI3MjYzNTc5MTI0ZDFmOTMwMWNmZjU2ZDE3MmM4ZCJ9.gk5l1bwxBMl61Rjti67bXwKpr7IUv6EFyAr6YuJx8RxQ1uzCJy4ZefKNySVAF18HzOJcAKLovZsRm8_QYx7xoP3MNlYYy7kF5-bqoduLVTPVTbi2xoYs3WvuTsDIKTPixXXc-xXzOEDCHfzRVdELe9c8Lxnj7GdP-AXtJneJjPKqsYc8MFMPVvD9lblb7H4-ryfcIPC5RiSrEUah3T-euutzetwFWhBbgxM8tTZAk-_5_UcsDy5D-Kc0fQbkzM711EX47V_4npZz1dnXJWPkcipxV8DGCKQ86qVrvpyYGLDae0wCHkAaofQbUB1iZv5FpuOtmqnmqPYsxoBUGHqOew"
  }
}
"""