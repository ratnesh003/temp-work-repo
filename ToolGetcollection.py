
import warnings
import requests
from urllib3.exceptions import InsecureRequestWarning

def get_collections_id_by_name(search_query: str | None = None):
    """
    Fetch a simplified list of DMS collections (id and name), optionally filtered by `search_query`.

    Purpose:
        Calls the DMS `list_collections` API and returns only the minimal fields needed to
        identify collections: `id` and `collection_name`. Designed for agent workflows that
        need to map a human-readable collection name to its `id`.

    Args:
        search_query (str | None): Optional text to filter collections server-side.
            - If provided and non-empty, included as `search_query` query param.
            - If None or empty, the param is omitted (returns first page of collections).

    Returns:
        list[dict] | str:
            - On success (JSON payload): a list of dicts with shape:
                [
                    {"id": <string|int>, "collection_name": <string>},
                    ...
                ]
              Empty list if no items.
            - On failure or non-JSON response: a string with the raw response body or an
              error message (e.g., "Request failed: <details>").

    Network:
        - GET https://aiforce.hcltech.com/dms/list_collections
        - Query params: page_number=1, page_size=100, (optional) search_query=<str>
        - Headers: Authorization: Bearer <token>, Accept: application/json
        - TLS verification is disabled (verify=False) and warnings suppressed.

    Notes:
        - The bearer token is hardcoded for demonstration; use environment variables or a
          secret manager for production. Prefer verify=True and proper CA bundles.
        - Pagination is fixed; add pagination if collections > 100.
        - The function defensively handles missing keys and non-dict items.

    Example:
        items = get_collections_id_by_name("Policies")
        # items might be:
        # [{"id": 42, "collection_name": "HR Policies"}, {"id": 51, "collection_name": "Company Policies"}]
        target = next((i for i in items if i["collection_name"] == "HR Policies"), None)
        if target:
        print(target["id"])  # 42
    """

    url = "https://aiforce.hcltech.com/dms/list_collections"
    params = {
        "page_number": 1,
        "page_size": 100,
    }

    if search_query:
        params["search_query"] = search_query

    warnings.simplefilter("ignore", InsecureRequestWarning)

    auth_token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3OTkzMTYwNTIsInVzZXJfaWQiOjExMTcsInVzZXJfbmFtZSI6InJhdG5lc2hwYXNpMDMiLCJlbWFpbF9pZCI6InBhc2lyYXRuZXNoLnRhcmFrYW50QGhjbHRlY2guY29tIiwib3JnX2lkIjoxLCJyb2xlIjoiQ29udHJpYnV0b3IiLCJyb2xlX2lkIjozLCJwcm9qZWN0X2lkIjoyNSwiaXNfc3VwZXJfYWRtaW4iOmZhbHNlLCJyb2xlX3R5cGVfaWQiOjMsInJvbGVfdHlwZSI6IkNvbnRyaWJ1dG9yIiwidXNlcl90eXBlIjoicGxhdGZvcm1fdXNlciIsImp0aWQiOiI1ZjI3MjYzNTc5MTI0ZDFmOTMwMWNmZjU2ZDE3MmM4ZCJ9.gk5l1bwxBMl61Rjti67bXwKpr7IUv6EFyAr6YuJx8RxQ1uzCJy4ZefKNySVAF18HzOJcAKLovZsRm8_QYx7xoP3MNlYYy7kF5-bqoduLVTPVTbi2xoYs3WvuTsDIKTPixXXc-xXzOEDCHfzRVdELe9c8Lxnj7GdP-AXtJneJjPKqsYc8MFMPVvD9lblb7H4-ryfcIPC5RiSrEUah3T-euutzetwFWhBbgxM8tTZAk-_5_UcsDy5D-Kc0fQbkzM711EX47V_4npZz1dnXJWPkcipxV8DGCKQ86qVrvpyYGLDae0wCHkAaofQbUB1iZv5FpuOtmqnmqPYsxoBUGHqOew"

    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Accept": "application/json"
    }

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15, verify=False)
        resp.raise_for_status()

        try:
            payload = resp.json()
        except ValueError:
            return resp.text

        data_obj = payload.get("data", {})
        items = data_obj.get("items", [])

        slim_items = [
            {
                "id": item.get("id"),
                "collection_name": item.get("collection_name")
            }
            for item in items
            if isinstance(item, dict)  # guard against non-dict items
        ]

        return slim_items

    except requests.exceptions.HTTPError as http_err:
        # print(f"HTTP error occurred: {http_err}")
        if http_err.response is not None:
            return http_err.response.text
    except requests.exceptions.RequestException as err:
        return f"Request failed: {err}"

if __name__ == "__main__":
    print(type(get_collections_id_by_name()[0].get("id")))

"""
{
  "get_collections_id_by_name": {
    "search_query": "",
    "auth_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3OTkzMTYwNTIsInVzZXJfaWQiOjExMTcsInVzZXJfbmFtZSI6InJhdG5lc2hwYXNpMDMiLCJlbWFpbF9pZCI6InBhc2lyYXRuZXNoLnRhcmFrYW50QGhjbHRlY2guY29tIiwib3JnX2lkIjoxLCJyb2xlIjoiQ29udHJpYnV0b3IiLCJyb2xlX2lkIjozLCJwcm9qZWN0X2lkIjoyNSwiaXNfc3VwZXJfYWRtaW4iOmZhbHNlLCJyb2xlX3R5cGVfaWQiOjMsInJvbGVfdHlwZSI6IkNvbnRyaWJ1dG9yIiwidXNlcl90eXBlIjoicGxhdGZvcm1fdXNlciIsImp0aWQiOiI1ZjI3MjYzNTc5MTI0ZDFmOTMwMWNmZjU2ZDE3MmM4ZCJ9.gk5l1bwxBMl61Rjti67bXwKpr7IUv6EFyAr6YuJx8RxQ1uzCJy4ZefKNySVAF18HzOJcAKLovZsRm8_QYx7xoP3MNlYYy7kF5-bqoduLVTPVTbi2xoYs3WvuTsDIKTPixXXc-xXzOEDCHfzRVdELe9c8Lxnj7GdP-AXtJneJjPKqsYc8MFMPVvD9lblb7H4-ryfcIPC5RiSrEUah3T-euutzetwFWhBbgxM8tTZAk-_5_UcsDy5D-Kc0fQbkzM711EX47V_4npZz1dnXJWPkcipxV8DGCKQ86qVrvpyYGLDae0wCHkAaofQbUB1iZv5FpuOtmqnmqPYsxoBUGHqOew"
  }
}
"""