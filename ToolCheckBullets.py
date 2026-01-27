import json
import math
import requests
import warnings
import urllib.parse
from tqdm import tqdm
from bs4 import BeautifulSoup
from typing import List, Dict, Any
from urllib3.exceptions import InsecureRequestWarning
import re

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
        error_msg = f"HTTP error occurred: {http_err}"
        if http_err.response is not None:
            error_msg += f" | Response body: {http_err.response.text}"
        return error_msg
    except requests.exceptions.RequestException as err:
        return f"Request failed: {err}"
    
import re
from bs4 import BeautifulSoup

def check_bullets_in_single_file(
    file_id: str,
    file_path: str,
    html_content: str
) -> dict | None:
    """
    Checks bullet alignment issues in a single HTML file.

    Returns:
        None if no issues found
        Dict with bullet alignment issues otherwise
    """

    soup = BeautifulSoup(html_content, "html.parser")

    bullet_elements = set(
        soup.find_all("div", class_=re.compile(r"List_\d+_-_\w+")) +
        soup.find_all("li")
    )

    if not bullet_elements:
        return None

    misaligned = []

    for element in bullet_elements:
        style = element.get("style", "")
        classes = element.get("class", []) or []

        # -------------------------------------------------
        # Rule 1: margin-left validation for List_* classes
        # -------------------------------------------------
        if any("List_" in cls for cls in classes):
            margin_match = re.search(
                r"margin-left:\s*(\d+(?:\.\d+)?)(pt|px)",
                style
            )

            if not margin_match:
                misaligned.append({
                    "element_id": element.get("id"),
                    "text": element.get_text(strip=True),
                    "reason": "Missing margin-left property"
                })
            elif margin_match.group(1) != "18" or margin_match.group(2) != "pt":
                misaligned.append({
                    "element_id": element.get("id"),
                    "text": element.get_text(strip=True),
                    "reason": f"Invalid margin-left: {margin_match.group(1)}{margin_match.group(2)}"
                })

        if invalid_props := re.findall(
            r"(padding|line-height):\s*[^;]+", style
        ):
            misaligned.append({
                "element_id": element.get("id"),
                "text": element.get_text(strip=True),
                "reason": f"Found problematic properties: {', '.join(invalid_props)}"
            })

    if not misaligned:
        return None

    return {
        "file_id": file_id,
        "file_path": file_path,
        "total_bullets": len(bullet_elements),
        "misaligned_count": len(misaligned),
        "issues": misaligned,
        "remarks": "Misaligned bullets detected"
    }

def check_bullets_in_collection_by_id(collection_id: str, auth_token: str) -> list[dict]:
    """
    Orchestrates bullet alignment validation across a collection.

    Returns:
        Array of result objects describing bullet alignment issues
    """

    results = []

    html_files = list_all_html_files_in_collection(collection_id=collection_id, auth_token=auth_token)

    for file_meta in tqdm(html_files):
        file_id = file_meta["id"]
        file_path = file_meta.get("file_name", "")

        try:
            html_content = get_file_content(file_id=file_id, auth_token=auth_token)

            if file_result := check_bullets_in_single_file(
                file_id=file_id, file_path=file_path, html_content=html_content
            ):
                results.append(file_result)

        except Exception as exc:
            results.append({
                "file_id": file_id,
                "file_path": file_path,
                "error": str(exc),
                "remarks": "Failed to process bullet alignment"
            })

    return results

if __name__ == "__main__":

    auth_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3OTkzMTYwNTIsInVzZXJfaWQiOjExMTcsInVzZXJfbmFtZSI6InJhdG5lc2hwYXNpMDMiLCJlbWFpbF9pZCI6InBhc2lyYXRuZXNoLnRhcmFrYW50QGhjbHRlY2guY29tIiwib3JnX2lkIjoxLCJyb2xlIjoiQ29udHJpYnV0b3IiLCJyb2xlX2lkIjozLCJwcm9qZWN0X2lkIjoyNSwiaXNfc3VwZXJfYWRtaW4iOmZhbHNlLCJyb2xlX3R5cGVfaWQiOjMsInJvbGVfdHlwZSI6IkNvbnRyaWJ1dG9yIiwidXNlcl90eXBlIjoicGxhdGZvcm1fdXNlciIsImp0aWQiOiI1ZjI3MjYzNTc5MTI0ZDFmOTMwMWNmZjU2ZDE3MmM4ZCJ9.gk5l1bwxBMl61Rjti67bXwKpr7IUv6EFyAr6YuJx8RxQ1uzCJy4ZefKNySVAF18HzOJcAKLovZsRm8_QYx7xoP3MNlYYy7kF5-bqoduLVTPVTbi2xoYs3WvuTsDIKTPixXXc-xXzOEDCHfzRVdELe9c8Lxnj7GdP-AXtJneJjPKqsYc8MFMPVvD9lblb7H4-ryfcIPC5RiSrEUah3T-euutzetwFWhBbgxM8tTZAk-_5_UcsDy5D-Kc0fQbkzM711EX47V_4npZz1dnXJWPkcipxV8DGCKQ86qVrvpyYGLDae0wCHkAaofQbUB1iZv5FpuOtmqnmqPYsxoBUGHqOew"

    data = check_bullets_in_collection_by_id(collection_id=1152, auth_token=auth_token)

    file_path = "initial_files_check_bullets.json"

    try:
        # Open the file in write mode ('w')
        with open(file_path, 'w') as json_file:
            # Use json.dump() to write the data to the file
            json.dump(data, json_file, indent=4)
        print(f"Successfully wrote data to {file_path}")
    except IOError as e:
        print(f"Error writing to file: {e}")