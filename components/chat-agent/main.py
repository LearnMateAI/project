import json
from ingestion.pdf_loader import extract_pdf_text
from ingestion.text_preprocessor import TextPreprocessor


def main():

    pdf_path = input("Enter PDF path: ").strip()

    # Step 1: Extract page-wise text
    pages = extract_pdf_text(pdf_path)

    if not pages:
        print("No text extracted.")
        return

    # Step 2: Clean page-wise text
    preprocessor = TextPreprocessor()

    processed_pages = preprocessor.preprocess(
        pages,
        pdf_path
    )

    # Step 3: Filter keys and print structured JSON output
    # This ensures we only output the 3 specific fields you requested
    formatted_output = [
        {
            "page_index": page["page_index"],
            "page_number": page["page_number"],
            "page_content": page["page_content"]
        }
        for page in processed_pages
    ]

    # Print the resulting list as a nicely formatted JSON string
    print(json.dumps(formatted_output, indent=4, ensure_ascii=False))


if __name__ == "__main__":
    main()