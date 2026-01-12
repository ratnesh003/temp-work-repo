import os
import re
import json
import math
import requests
import warnings
import urllib.parse
from tqdm import tqdm
from bs4 import BeautifulSoup
import base64
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor
from urllib3.exceptions import InsecureRequestWarning
from pypdf import PdfReader
import html

def list_all_html_files_in_collection(
    collection_id: int,
    auth_token: str,
    search_query: str = ".pdf",
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


def extract_text_from_pdf(text):
    unescaped = html.unescape(text)

    pdf_bytes = unescaped.encode("latin-1", errors="strict")

    with open("output.pdf", "wb") as f:
        f.write(pdf_bytes)

    with open("output.pdf", "rb") as f:
        print(f.read(5))  # b'%PDF-'

    return pdf_bytes


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

        out_path = "output.pdf"
        
        with open(out_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            # Sanity check
        with open(out_path, "rb") as f:
            print(f.read(5))  # should be b'%PDF-'

    except requests.exceptions.HTTPError as http_err:
        return f"HTTP error occurred: {http_err}"
        if http_err.response is not None:
            return f"Response body: {http_err.response.text}"
    except requests.exceptions.RequestException as err:
        return f"Request failed: {err}"

if __name__ == "__main__":
    auth_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3OTkzMTYwNTIsInVzZXJfaWQiOjExMTcsInVzZXJfbmFtZSI6InJhdG5lc2hwYXNpMDMiLCJlbWFpbF9pZCI6InBhc2lyYXRuZXNoLnRhcmFrYW50QGhjbHRlY2guY29tIiwib3JnX2lkIjoxLCJyb2xlIjoiQ29udHJpYnV0b3IiLCJyb2xlX2lkIjozLCJwcm9qZWN0X2lkIjoyNSwiaXNfc3VwZXJfYWRtaW4iOmZhbHNlLCJyb2xlX3R5cGVfaWQiOjMsInJvbGVfdHlwZSI6IkNvbnRyaWJ1dG9yIiwidXNlcl90eXBlIjoicGxhdGZvcm1fdXNlciIsImp0aWQiOiI1ZjI3MjYzNTc5MTI0ZDFmOTMwMWNmZjU2ZDE3MmM4ZCJ9.gk5l1bwxBMl61Rjti67bXwKpr7IUv6EFyAr6YuJx8RxQ1uzCJy4ZefKNySVAF18HzOJcAKLovZsRm8_QYx7xoP3MNlYYy7kF5-bqoduLVTPVTbi2xoYs3WvuTsDIKTPixXXc-xXzOEDCHfzRVdELe9c8Lxnj7GdP-AXtJneJjPKqsYc8MFMPVvD9lblb7H4-ryfcIPC5RiSrEUah3T-euutzetwFWhBbgxM8tTZAk-_5_UcsDy5D-Kc0fQbkzM711EX47V_4npZz1dnXJWPkcipxV8DGCKQ86qVrvpyYGLDae0wCHkAaofQbUB1iZv5FpuOtmqnmqPYsxoBUGHqOew"
    data=get_file_content(file_id=9884, auth_token=auth_token)
    # data = extract_text_from_pdf(text=text)
    print(data)