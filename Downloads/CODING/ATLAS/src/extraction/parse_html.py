"""
Module for parsing HTML content from SEC filings.
"""

import os
import json
import pandas as pd
from bs4 import BeautifulSoup


def parse_html(html_file_path="data/raw/msft_2024_10k.html"):
    """
    Parse HTML content from SEC filings and extract all tables.
    
    Loads HTML file, finds all <table> elements, extracts them into pandas DataFrames,
    and saves the cleaned data to JSON.
    
    Args:
        html_file_path: Path to the HTML file to parse (default: data/raw/msft_2024_10k.html)
        
    Returns:
        List of pandas DataFrames containing extracted tables
    """
    # Load HTML file
    with open(html_file_path, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Parse HTML with BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Find all <table> elements
    tables = soup.find_all('table')
    num_tables = len(tables)
    
    print(f"Found {num_tables} table(s) in HTML file")
    
    # Extract tables into DataFrames and convert to dictionaries
    dataframes = []
    tables_data = []
    
    for i, table in enumerate(tables):
        try:
            # Convert table HTML to string and parse with pandas
            table_html = str(table)
            df_list = pd.read_html(table_html, flavor='bs4')
            
            # pandas.read_html returns a list, get the first DataFrame
            if df_list:
                df = df_list[0]
                dataframes.append(df)
                
                # Convert DataFrame to dictionary
                table_dict = df.to_dict(orient="records")
                tables_data.append({
                    "rows": table_dict,
                    "index": i
                })
                
                print(f"Extracted table {i}")
        except Exception as e:
            print(f"Warning: Could not extract table {i}: {e}")
            # Still add placeholder to maintain index consistency
            tables_data.append({
                "rows": [],
                "index": i
            })
    
    # Create output structure
    output = {
        "num_tables": num_tables,
        "tables": tables_data
    }
    
    # Save to JSON
    save_dir = os.path.join("data", "extracted")
    os.makedirs(save_dir, exist_ok=True)
    save_path = os.path.join(save_dir, "msft_tables_raw.json")
    
    with open(save_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"✓ Tables saved to {save_path}")
    print(f"  Total tables extracted: {len(dataframes)}")
    
    return dataframes


if __name__ == "__main__":
    parse_html()

