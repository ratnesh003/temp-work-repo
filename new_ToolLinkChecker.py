import os
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

def build_html_document_index(
    collection_id: int,
    auth_token: str
) -> Dict[str, List[int]]:
    """
    Maps logical HTML document names (e.g. 0001485246.html)
    to DMS file IDs, even when filenames are prefixed.
    """

    items = list_all_html_files_in_collection(
        collection_id=collection_id,
        auth_token=auth_token,
        search_query=".html",
        page_size=100,
    )

    index: Dict[str, List[int]] = {}

    for item in items:
        name = item.get("file_name", "")
        fid = item.get("id")

        if not name or not fid:
            continue

        base = os.path.basename(name).lower()

        # Extract logical html identifier
        # e.g. Xerox_en-US_0001485246.html → 0001485246.html
        if base.endswith(".html"):
            logical = base.split("_")[-1]

            index.setdefault(logical, []).append(fid)

    return index

def link_checker_single_html(
    html_content: str,
    source_file: str,
    html_document_index: Dict[str, List[int]],
    timeout: int = 5,
    threads: int = 10
) -> List[Dict[str, Any]]:
    """
    Validate links found in a single HTML content string (no base_dir / filesystem).
    Returns only invalid/broken entries, preserving original link_checker behavior
    for extraction, filtering, and HTTP checks.

    Args:
        html_content: Full HTML text of one file.
        source_file: Logical name/path of the HTML file (used for reporting).
        timeout: Requests timeout (seconds) for external URL checks.
        threads: Max workers for parallel link checks.

    Returns:
        List of dicts for invalid links:
        {
            "file": <source_file>,
            "href": <original href/src>,
            "text": <link text or short description>,
            "resolved_url": <absolute URL, fragment, or raw local path>,
            "status": <int or str>,
            "error": <string>
        }
    """

    soup = BeautifulSoup(html_content, "html.parser")

    # Consistent with original: skip typical static resources
    excluded_exts = (".html", ".css", ".js", ".svg", ".png", ".jpg", ".jpeg", ".gif", ".ico")

    links: List[Dict[str, Any]] = []

    # ... links
    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if not href or href.startswith("javascript:") or href.startswith("mailto:") or href == "#":
            continue
        if href.lower().endswith(excluded_exts):
            continue
        links.append({
            "source_file": source_file,
            "href": href,
            "text": a.get_text(strip=True)[:50] or "Link",
        })

    # ... resources
    for link_tag in soup.find_all("link", href=True):
        href = link_tag.get("href", "")
        if not href or href.lower().endswith(excluded_exts):
            continue
        links.append({
            "source_file": source_file,
            "href": href,
            "text": "CSS/Resource link",
        })
    
    # ... images (optional as in original)
    for img in soup.find_all("img", src=True):
        src = img.get("src", "")
        if not src or src.lower().endswith(excluded_exts):
            continue
        links.append({
            "source_file": source_file,
            "href": src,
            "text": img.get("alt", "Image")[:50] or "Image",
        })
    
    # De-duplicate by original href/src to reduce repeated checks
    unique_links = []
    seen = set()
    for link in links:
        if link["href"] not in seen:
            seen.add(link["href"])
            unique_links.append(link)
            
    def normalize_html_href(href: str) -> str:
        parsed = urllib.parse.urlparse(href)
        return parsed.path.split("/")[-1].lower()

            
    def resolve_local_html(href: str) -> Dict[str, Any]:
        logical_name = normalize_html_href(href)

        matches = html_document_index.get(logical_name, [])

        if len(matches) == 1:
            return {
                "status": 200,
                "is_broken": False,
                "error": "",
            }

        if len(matches) > 1:
            return {
                "status": "Ambiguous",
                "is_broken": True,
                "error": f"Multiple documents resolve to '{logical_name}'",
            }

        return {
            "status": 404,
            "is_broken": True,
            "error": f"Logical HTML '{logical_name}' not found in collection",
        }

    
    def resolve_url(href: str) -> str:
        """
        Resolve for reporting:
        - http/https: return as-is
        - fragment-only (#...): source_file + fragment
        - local/relative: return raw href (no filesystem resolution without base_dir)
        """
        if href.startswith(("http://", "https://")):
            return href
        if href.startswith("#"):
            return f"{source_file}{href}"
        # No base_dir: keep the raw href for transparency
        return urllib.parse.unquote(href).replace("\\", "/")

    def check_link(link_info: Dict[str, Any]) -> Dict[str, Any]:
        href = link_info["href"]
        result: Dict[str, Any] = {
            "file": source_file,
            "href": href,
            "text": link_info["text"],
            "resolved_url": resolve_url(href),
            "status": None,
            "error": "",
            "is_broken": False,
        }
        try:
            if href.startswith(("http://", "https://")):
                # External URL: try HEAD, fallback to GET if >=400
                try:
                    resp = requests.head(href, allow_redirects=True, timeout=timeout)
                    code = resp.status_code
                    if code >= 400:
                        resp = requests.get(href, timeout=timeout)
                        code = resp.status_code
                    result["status"] = code
                    result["is_broken"] = code >= 400
                    if result["is_broken"]:
                        result["error"] = f"HTTP {code}"
                except requests.exceptions.Timeout:
                    result["status"] = "Timeout"
                    result["is_broken"] = True
                    result["error"] = "Request timed out"
                except requests.exceptions.ConnectionError:
                    result["status"] = "Connection Error"
                    result["is_broken"] = True
                    result["error"] = "Failed to establish connection"
                except requests.exceptions.RequestException as e:
                    result["status"] = "Request Error"
                    result["is_broken"] = True
                    result["error"] = str(e)
            else:
                # Fragment-only (same file)
                if href.startswith("#"):
                    result["status"] = 200
                    result["is_broken"] = False
                    return result

                # Local HTML (with or without fragment)
                if ".html" in href.lower():
                    local = resolve_local_html(href)
                    result["status"] = local["status"]
                    result["is_broken"] = local["is_broken"]
                    result["error"] = local["error"]
                    return result

                # Other local assets
                result["status"] = "Not Validated"
                result["is_broken"] = True
                result["error"] = "Local path cannot be verified without base URL"

        except Exception as e:
            result["status"] = "Error"
            result["is_broken"] = True
            result["error"] = str(e)

        return result

    # Parallel checks (preserve original threading)
    with ThreadPoolExecutor(max_workers=threads) as executor:
        results = list(executor.map(check_link, unique_links))

    # Return only broken/invalid (including Not Validated)
    invalid = [r for r in results if r.get("is_broken")]
    # Shape output to the fields you asked for
    return [
        {
            "file": r["file"],
            "href": r["href"],
            "resolved_url": r["resolved_url"],
            "status": r["status"],
            "error": r.get("error", ""),
            "text": r.get("text", ""),
        }
        for r in invalid
    ]

def html_link_validation_in_collection_by_id(collection_id: int, auth_token: str):
    """
    Run link validation across all HTML files in a DMS collection and return a consolidated list
    of invalid (or not-validated) links with diagnostic details.

    Purpose:
        Enumerates every `.html` file in the specified collection (using `total_count` pagination
        with page_size=100), downloads each file’s HTML content, and checks all links within:
        - ... anchors (excluding javascript:, mailto:, and pure fragments "#")
        - ... resource references
        - ... image sources

        External URLs (http/https) are probed via HEAD with GET fallback and marked invalid when
        HTTP status >= 400 or on request errors (timeout, connection error). Local/relative paths
        are returned as "Not Validated" because the function does not resolve filesystem paths.

    Args:
        collection_id (int): The numeric ID of the DMS collection whose HTML files should be
            validated. The function automatically paginates using `total_count` and fetches
            up to 100 items per page.

    Returns:
        list[dict]:
            A flat list of invalid or not-validated links. Each entry has:
            {
                "file": <html file_name>,
                "href": <original href/src>,
                "resolved_url": <absolute URL, fragment, or raw local path>,
                "status": <int | str>,   # e.g., 404, "Timeout", "Connection Error", "Not Validated"
                "error": <str>,          # diagnostic message, e.g., "HTTP 404" or details of the request error
                "text": <str>            # link text or short description
            }
            Notes:
              - Valid links are omitted.
              - Duplicate hrefs within a file are checked once.

    Network:
        - List HTML files:
            GET https://aiforce.hcltech.com/dms/collection/<collection_id>
            Query params: page_number=<int>, page_size=100, search_query=".html"
            Headers: Authorization: Bearer <token>, Accept: application/json
            TLS: verification disabled in sample (verify=False), warnings suppressed.
        - Download HTML content:
            GET https://aiforce.hcltech.com/dms/file_download
            Query params: file_id=<int>
            Headers: Authorization: Bearer <token>, Accept: application/json
        - Validate external links:
            HEAD <http(s) URL> with allow_redirects=True, fallback GET on >=400

    Notes:
        - The bearer token is hardcoded in the sample implementation; use environment variables
          or a secret manager in production. Prefer TLS verification (verify=True) with proper CA bundles.
        - Pagination leverages the API’s `total_count` to compute total pages deterministically.
        - Local/relative links are returned as "Not Validated" (no base directory resolution by design).
        - Link checks are run in parallel per file using a thread pool to speed up HTTP validation.
        - The function defensively handles non-JSON responses and request exceptions.

    Example:
        # Validate all links in collection 1152
        results = html_link_validation_in_collection_by_id(1152)

        # Summarize by status code/type
        from collections import Counter
        counter = Counter(r["status"] for r in results)
        print(counter)
        # e.g., Counter({404: 12, 'Not Validated': 7, 'Timeout': 2})

        # Show top 5 broken links
        for r in results[:5]:
            print(f"{r['file']} -> {r['href']} [{r['status']}] {r['error']}")
    """
    
    html_items = list_all_html_files_in_collection(
        collection_id=collection_id,
        auth_token=auth_token,
        page_size=100,
        search_query=".html",
    )

    # ✅ Build index ONCE (agent-safe, deterministic)
    html_file_index = build_html_document_index(
        collection_id=collection_id,
        auth_token=auth_token,
    )

    results = []

    for item in tqdm(html_items):
        content = get_file_content(
            file_id=item.get("id"),
            auth_token=auth_token
        )

        file_results = link_checker_single_html(
            html_content=content,
            source_file=item.get("file_name"),
            html_document_index=html_file_index,
        )

        results.extend(file_results)

    return results

# if __name__ == "__main__":

#     auth_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3OTkzMTYwNTIsInVzZXJfaWQiOjExMTcsInVzZXJfbmFtZSI6InJhdG5lc2hwYXNpMDMiLCJlbWFpbF9pZCI6InBhc2lyYXRuZXNoLnRhcmFrYW50QGhjbHRlY2guY29tIiwib3JnX2lkIjoxLCJyb2xlIjoiQ29udHJpYnV0b3IiLCJyb2xlX2lkIjozLCJwcm9qZWN0X2lkIjoyNSwiaXNfc3VwZXJfYWRtaW4iOmZhbHNlLCJyb2xlX3R5cGVfaWQiOjMsInJvbGVfdHlwZSI6IkNvbnRyaWJ1dG9yIiwidXNlcl90eXBlIjoicGxhdGZvcm1fdXNlciIsImp0aWQiOiI1ZjI3MjYzNTc5MTI0ZDFmOTMwMWNmZjU2ZDE3MmM4ZCJ9.gk5l1bwxBMl61Rjti67bXwKpr7IUv6EFyAr6YuJx8RxQ1uzCJy4ZefKNySVAF18HzOJcAKLovZsRm8_QYx7xoP3MNlYYy7kF5-bqoduLVTPVTbi2xoYs3WvuTsDIKTPixXXc-xXzOEDCHfzRVdELe9c8Lxnj7GdP-AXtJneJjPKqsYc8MFMPVvD9lblb7H4-ryfcIPC5RiSrEUah3T-euutzetwFWhBbgxM8tTZAk-_5_UcsDy5D-Kc0fQbkzM711EX47V_4npZz1dnXJWPkcipxV8DGCKQ86qVrvpyYGLDae0wCHkAaofQbUB1iZv5FpuOtmqnmqPYsxoBUGHqOew"

#     content = get_file_content(file_id=8356, auth_token=auth_token)
#     results = link_checker_single_html(html_content=content, source_file="0001485366.html")
#     print(json.dumps(results, indent=4))
#     print(content)

#------------------------------------------------------------------------------------------------

if __name__ == "__main__":

    auth_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3OTkzMTYwNTIsInVzZXJfaWQiOjExMTcsInVzZXJfbmFtZSI6InJhdG5lc2hwYXNpMDMiLCJlbWFpbF9pZCI6InBhc2lyYXRuZXNoLnRhcmFrYW50QGhjbHRlY2guY29tIiwib3JnX2lkIjoxLCJyb2xlIjoiQ29udHJpYnV0b3IiLCJyb2xlX2lkIjozLCJwcm9qZWN0X2lkIjoyNSwiaXNfc3VwZXJfYWRtaW4iOmZhbHNlLCJyb2xlX3R5cGVfaWQiOjMsInJvbGVfdHlwZSI6IkNvbnRyaWJ1dG9yIiwidXNlcl90eXBlIjoicGxhdGZvcm1fdXNlciIsImp0aWQiOiI1ZjI3MjYzNTc5MTI0ZDFmOTMwMWNmZjU2ZDE3MmM4ZCJ9.gk5l1bwxBMl61Rjti67bXwKpr7IUv6EFyAr6YuJx8RxQ1uzCJy4ZefKNySVAF18HzOJcAKLovZsRm8_QYx7xoP3MNlYYy7kF5-bqoduLVTPVTbi2xoYs3WvuTsDIKTPixXXc-xXzOEDCHfzRVdELe9c8Lxnj7GdP-AXtJneJjPKqsYc8MFMPVvD9lblb7H4-ryfcIPC5RiSrEUah3T-euutzetwFWhBbgxM8tTZAk-_5_UcsDy5D-Kc0fQbkzM711EX47V_4npZz1dnXJWPkcipxV8DGCKQ86qVrvpyYGLDae0wCHkAaofQbUB1iZv5FpuOtmqnmqPYsxoBUGHqOew"

    data = html_link_validation_in_collection_by_id(collection_id=1152, auth_token=auth_token)

    file_path = "new_initial_files_invalid_links.json"

    try:
        # Open the file in write mode ('w')
        with open(file_path, 'w') as json_file:
            # Use json.dump() to write the data to the file
            json.dump(data, json_file, indent=4)
        print(f"Successfully wrote data to {file_path}")
    except IOError as e:
        print(f"Error writing to file: {e}")