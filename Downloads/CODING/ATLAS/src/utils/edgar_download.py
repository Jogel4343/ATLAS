"""
Module for downloading SEC filings from EDGAR database.
"""

import os
import re
import time
import xml.etree.ElementTree as ET
import zipfile
import io

import requests

from src.storage.cache import ensure_raw_dir, raw_dir, raw_exists
from src.utils.cik_lookup import get_cik


def host_for(url):
    if "data.sec.gov" in url:
        return "data.sec.gov"
    return "www.sec.gov"


def _get_headers(host):
    """Get headers required by SEC EDGAR with specified host."""
    return {
        'User-Agent': 'Atlas Financial Analysis Tool (contact@example.com)',
        'Accept-Encoding': 'gzip, deflate',
        'Host': host
    }


def _safe_get(url, headers, retries=5, delay=1):
    """
    Make HTTP GET request with retry logic and exponential backoff.
    
    Args:
        url: URL to request
        headers: HTTP headers for the request
        retries: Number of retry attempts (default: 5)
        delay: Initial delay in seconds (default: 1), doubles with each retry
        
    Returns:
        Response object with status_code == 200
        
    Raises:
        Exception: If request fails after all retries
    """
    for attempt in range(retries):
        resp = requests.get(url, headers={
            "User-Agent": "AtlasScraper contact: jackvogel4343@gmail.com",
            "Accept-Encoding": "gzip, deflate",
            "Host": host_for(url)
        })
        if resp.status_code == 200:
            return resp
        print(f"Request failed ({resp.status_code}). Retrying in {delay} seconds...")
        time.sleep(delay)
        delay *= 2
    raise Exception(f"Failed to GET {url} after {retries} retries")


def _extract_main_html(index_content):
    """
    Extract the main HTML document filename from the filing index.
    """
    # Priority 1: Look for 10-K links
    pattern_10k = r'<a\s+href="([^"]*\.htm)"[^>]*>.*?10-K.*?</a>'
    matches_10k = re.findall(pattern_10k, index_content, re.IGNORECASE | re.DOTALL)
    if matches_10k:
        return matches_10k[0]
    
    # Priority 2: Look for any non-index .htm file
    pattern_htm = r'href="([^"]*\.htm)"'
    html_links = re.findall(pattern_htm, index_content)
    for link in html_links:
        if '-index.htm' not in link.lower() and link.endswith('.htm'):
            return link
    
    # Priority 3: Fallback filename
    return "msft-20240630.htm"


def _select_best_annual_filing(submissions, target_year, specific_form=None):
    """
    Returns the best annual filing for the target year.
    Priority:
        1. 10-K
        2. 20-F
        3. 40-F
    Exact user-specified type (e.g., '2023_20-F') always wins.
    """
    filings = submissions.get('filings', {}).get('recent', {})
    forms = filings.get('form', [])
    accession_numbers = filings.get('accessionNumber', [])
    primary_documents = filings.get('primaryDocument', [])
    report_dates = filings.get('reportDate', [])
    period_of_report = filings.get('periodOfReport', [])

    candidates = []
    for idx, form in enumerate(forms):
        # Filter by form
        if specific_form:
            if form.upper() != specific_form.upper():
                continue
        elif form not in ['10-K', '20-F', '40-F']:
            continue

        date_str = None
        if idx < len(report_dates) and report_dates[idx]:
            date_str = report_dates[idx]
        elif idx < len(period_of_report) and period_of_report[idx]:
            date_str = period_of_report[idx]
            
        if not date_str:
            continue
            
        try:
            year_val = int(date_str.split('-')[0])
        except Exception:
            continue
            
        distance = abs(year_val - target_year)
        
        # Form priority score (lower is better)
        form_priority = {'10-K': 1, '20-F': 2, '40-F': 3}.get(form, 99)
        
        candidates.append(
            {
                "index": idx,
                "form": form,
                "distance": distance,
                "priority": form_priority,
                "accession": accession_numbers[idx] if idx < len(accession_numbers) else None,
                "primary_doc": primary_documents[idx] if idx < len(primary_documents) else None,
                "report_date": date_str,
            }
        )

    if not candidates:
        msg = f"No filing found for {target_year}"
        if specific_form:
            msg += f" (Form: {specific_form})"
        else:
            msg += " (Forms: 10-K, 20-F, 40-F)"
        raise ValueError(msg)

    # Sort by distance (ASC), then priority (ASC)
    candidates.sort(key=lambda c: (c["distance"], c["priority"]))
    return candidates[0]


def download_primary_pdf(cik: str, accession: str, output_dir: str) -> str:
    """
    Download the primary PDF for a filing by scraping the index HTML.
    Returns path to saved PDF or None.
    """
    import re, requests, os
    try:
        index_url = (
            f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession}-index.html"
        )
        headers = {
            "User-Agent": "AtlasScraper contact: jackvogel4343@gmail.com",
            "Accept-Encoding": "gzip, deflate",
        }
        resp = requests.get(index_url, headers=headers)
        if resp.status_code != 200:
            return None

        match = re.search(r'href="([^"]+\.pdf)"', resp.text, re.IGNORECASE)
        if not match:
            return None

        rel = match.group(1)
        if rel.startswith("/"):
            pdf_url = f"https://www.sec.gov{rel}"
        else:
            acc = accession.replace("-", "")
            pdf_url = (
                f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/{rel}"
            )

        pdf_resp = requests.get(pdf_url, headers=headers)
        if pdf_resp.status_code != 200:
            return None

        out_path = os.path.join(output_dir, "primary.pdf")
        with open(out_path, "wb") as f:
            f.write(pdf_resp.content)

        return out_path
    except Exception:
        return None


def download_filing(ticker: str = "msft", period: str = "2025_10k"):
    """
    UNIVERSAL DOWNLOADER
    """
    ticker = ticker.lower()
    period = period.lower()
    cik = get_cik(ticker)
    
    # Parse period
    parts = period.split('_')
    target_year = int(parts[0])
    
    specific_form = None
    if len(parts) > 1:
        raw_form = parts[1].upper()
        # Normalize "10k" -> "10-K" for convenience, otherwise treat as explicit
        if raw_form == "10K":
            specific_form = "10-K"
        elif raw_form in ["10-K", "20-F", "40-F"]:
            specific_form = raw_form
        # else: treat as "10k" default or ignore?
        # If user passes "2023_20-F", specific_form="20-F".
        # If user passes "2023", specific_form=None.

    if raw_exists(ticker, period):
        filing_directory = raw_dir(ticker, period)
        print(f"✔ Raw filing already cached at {filing_directory}. Skipping download.")
        return {"xbrl_dir": os.path.join(filing_directory, "xbrl")}
    
    try:
        # Fetch submission index
        cik_padded = str(int(cik)).zfill(10)
        submissions_url = f"https://data.sec.gov/submissions/CIK{cik_padded}.json"
        resp = requests.get(submissions_url, headers={
            "User-Agent": "AtlasScraper contact: jackvogel4343@gmail.com",
            "Accept-Encoding": "gzip, deflate",
            "Host": host_for(submissions_url)
        })
        resp.raise_for_status()
        data = resp.json()
        
        # Select filing
        filing = _select_best_annual_filing(data, target_year, specific_form)
        accession = filing['accession']
        form_found = filing['form']
        
        print(f"Found {form_found} filing")
        print(f"  Accession number: {accession}")
        
        # Try full-submission.zip
        acc = accession.replace("-", "")
        base_dir = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/"
        zip_url = base_dir + "full-submission.zip"

        print(f"Trying full-submission.zip: {zip_url}")
        zresp = requests.get(zip_url, headers={
            "User-Agent": "AtlasScraper contact: jackvogel4343@gmail.com",
            "Accept-Encoding": "gzip, deflate",
            "Host": host_for(zip_url)
        })

        output_dir = ensure_raw_dir(ticker, period)
        xbrl_dir = os.path.join(output_dir, "xbrl")
        os.makedirs(xbrl_dir, exist_ok=True)

        # If ZIP exists, extract XML/XSD/PDF
        if zresp.status_code == 200:
            print("✔ Using full-submission.zip")
            pdf_found = False

            with zipfile.ZipFile(io.BytesIO(zresp.content)) as z:
                for name in z.namelist():
                    lower = name.lower()

                    if lower.endswith((".xml", ".xsd", ".pdf")):
                        with z.open(name) as src:

                            # PDFs go to filing root; XML/XSD go to XBRL subfolder
                            if lower.endswith(".pdf"):
                                pdf_found = True
                                out = os.path.join(output_dir, os.path.basename(name))
                            else:
                                out = os.path.join(xbrl_dir, os.path.basename(name))

                            with open(out, "wb") as f:
                                f.write(src.read())

            if not pdf_found:
                print("⚠ No PDF in ZIP. Downloading primary PDF...")
                download_primary_pdf(cik, accession, output_dir)

            return {"xbrl_dir": xbrl_dir}

        print("⚠ full-submission.zip unavailable. Falling back to legacy XBRL files.")
        # PDF fallback for filings with no ZIP package
        print("⚠ No ZIP available. Attempting primary PDF download…")
        try:
            download_primary_pdf(cik, accession, output_dir)
        except Exception:
            pass

        # Try FilingSummary.xml (best-effort)
        filing_summary_url = base_dir + "FilingSummary.xml"
        try:
            r = requests.get(filing_summary_url, headers={
                "User-Agent": "AtlasScraper contact: jackvogel4343@gmail.com",
                "Accept-Encoding": "gzip, deflate",
                "Host": host_for(filing_summary_url)
            })
            if r.status_code == 200:
                with open(os.path.join(output_dir, "FilingSummary.xml"), "wb") as f:
                    f.write(r.content)
        except:
            pass

        # Legacy index.json
        index_url = base_dir + "index.json"
        r = requests.get(index_url, headers={
            "User-Agent": "AtlasScraper contact: jackvogel4343@gmail.com",
            "Accept-Encoding": "gzip, deflate",
            "Host": host_for(index_url)
        })

        # If index.json is forbidden → perform HTML fallback
        if r.status_code == 403:
            print("⚠ index.json forbidden. Using robust HTML directory fallback.")

            try:
                html_resp = requests.get(base_dir, headers={
                    "User-Agent": "AtlasScraper contact: jackvogel4343@gmail.com",
                    "Accept-Encoding": "gzip, deflate",
                    "Host": host_for(base_dir)
                })
                if html_resp.status_code != 200:
                    print("❌ HTML directory listing unavailable.")
                    return {"xbrl_dir": xbrl_dir}

                html = html_resp.text

                # Extract ALL hrefs
                links = re.findall(r'href=[\'"]([^\'"]+)[\'"]', html)

                # Normalize and filter for .xml / .xsd
                cleaned = []
                for name in links:
                    lower = name.lower()

                    # Skip directories, parent links, or anchors
                    if lower.startswith("..") or lower.startswith("#") or "/" in lower:
                        # keep only relative file names, not nested paths
                        basename = name.split("/")[-1]
                        name = basename
                        lower = name.lower()

                    if lower.endswith(".xml") or lower.endswith(".xsd"):
                        cleaned.append(name)

                cleaned = list(set(cleaned))  # remove duplicates

                print(f"✔ Found {len(cleaned)} XML/XSD links via HTML fallback.")

                # Download each file
                for file in cleaned:
                    url = base_dir + file
                    try:
                        resp = requests.get(url, headers={
                            "User-Agent": "AtlasScraper contact: jackvogel4343@gmail.com",
                            "Accept-Encoding": "gzip, deflate",
                            "Host": host_for(url)
                        })
                        if resp.status_code == 200:
                            out_path = os.path.join(xbrl_dir, file)
                            with open(out_path, "wb") as f:
                                f.write(resp.content)
                    except Exception:
                        continue

                return {"xbrl_dir": xbrl_dir}

            except Exception as e:
                print(f"❌ HTML fallback error: {e}")
                return {"xbrl_dir": xbrl_dir}

        # Otherwise process index.json normally
        r.raise_for_status()
        index_data = r.json()

        # Download every XML/XSD in legacy presentation
        for file in index_data.get("directory", {}).get("item", []):
            name = file.get("name", "")
            lower = name.lower()
            if lower.endswith(".xml") or lower.endswith(".xsd"):
                url = base_dir + name
                try:
                    resp = requests.get(url, headers={
                        "User-Agent": "AtlasScraper contact: jackvogel4343@gmail.com",
                        "Accept-Encoding": "gzip, deflate",
                        "Host": host_for(url)
                    })
                    if resp.status_code == 200:
                        with open(os.path.join(xbrl_dir, name), "wb") as f:
                            f.write(resp.content)
                except:
                    pass

        return {"xbrl_dir": xbrl_dir}
        
    except requests.RequestException as e:
        print(f"Error downloading filing: {e}")
        raise
    except Exception as e:
        print(f"Unexpected error: {e}")
        raise


if __name__ == "__main__":
    download_filing()
