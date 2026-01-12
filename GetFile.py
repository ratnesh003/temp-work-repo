
import warnings
import requests
from urllib3.exceptions import InsecureRequestWarning
import json

def main():
    url = "https://aiforce.hcltech.com/dms/files/8580"

    # Suppress the "InsecureRequestWarning" since we're setting verify=False
    warnings.simplefilter("ignore", InsecureRequestWarning)

    auth_token="eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3OTkyMzM0MTcsInVzZXJfaWQiOjExMTcsInVzZXJfbmFtZSI6InJhdG5lc2hwYXNpMDMiLCJlbWFpbF9pZCI6InBhc2lyYXRuZXNoLnRhcmFrYW50QGhjbHRlY2guY29tIiwib3JnX2lkIjoxLCJyb2xlIjoiQ29udHJpYnV0b3IiLCJyb2xlX2lkIjozLCJwcm9qZWN0X2lkIjoyNSwiaXNfc3VwZXJfYWRtaW4iOmZhbHNlLCJyb2xlX3R5cGVfaWQiOjMsInJvbGVfdHlwZSI6IkNvbnRyaWJ1dG9yIiwidXNlcl90eXBlIjoicGxhdGZvcm1fdXNlciIsImp0aWQiOiIxNDY1NDBkMDlkZTk0MjVjYmViNzZlZDQ2NTAxNzFhZSJ9.JGwqZffLfjGHWKgaPSLEul0-mxyhGwdQdfAZU0ionHwWM0GdvgPJj4em22ihQ11buzb7A_kRp6hWqRrmbGhr96I1YKzYVq7fVtgVZ3_oBTTk88PgBZxZgsBdoR9TgEaFI4M7XNUTBTRLfGxFZTIj9bC4MBCTozW-LJGcfHAvjZecTnfpXDIhyJgLJCGe-scOZ1-capuRPcyKKAc8sihCgw5ZYw1AGnZqco7A4v1ub23e1XUK2LJkmrvY5PgdotLN1rLS5MdJbNtf6ehgIhvuXVIzp-ljRG3QzDvBm5VVI88CE9eh2pWGODXyBZ5JOtzEX0P4aAhuGmlUhpU_oaPSpA"

    headers = {"Authorization": f"Bearer {auth_token}", "Accept": "application/json"}

    try:
        resp = requests.get(url, headers=headers, timeout=15, verify=False)
        resp.raise_for_status()
        # If response is JSON
        try:
            print("API Response (JSON):", json.dumps(resp.json().get("data"), indent=4))
        except ValueError:
            print("API Response (Text):", resp.text[:1000])  # show a preview if not JSON
    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error occurred: {http_err}")
        if http_err.response is not None:
            print("Response body:", http_err.response.text[:1000])
    except requests.exceptions.RequestException as err:
        print(f"Request failed: {err}")

if __name__ == "__main__":
    main()
