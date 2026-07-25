from ingestion.pdf_loader import extract_pdf_text

def main():
    pdf_path = input("Enter PDF path: ")

    pages = extract_pdf_text(pdf_path)

    for page in pages:
        print(f"Page {page['page_number']}")
        print(page["text"])

if __name__ == "__main__":
    main()