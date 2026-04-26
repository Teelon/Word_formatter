import os
import glob
from docx2pdf import convert

def main():
    # Define directories
    base_dir = os.path.dirname(os.path.abspath(__file__))
    output_docs_dir = os.path.join(base_dir, 'output_docs')
    pdf_dir = os.path.join(base_dir, 'pdf')

    # Create pdf directory if it doesn't exist
    if not os.path.exists(pdf_dir):
        os.makedirs(pdf_dir)
        print(f"Created directory: {pdf_dir}")

    # Find all docx files in output_docs
    docx_files = glob.glob(os.path.join(output_docs_dir, '*.docx'))

    if not docx_files:
        print(f"No .docx files found in {output_docs_dir}")
        return

    print(f"Found {len(docx_files)} .docx files to convert.")

    # Convert each file
    for docx_file in docx_files:
        filename = os.path.basename(docx_file)
        pdf_filename = os.path.splitext(filename)[0] + '.pdf'
        pdf_path = os.path.join(pdf_dir, pdf_filename)
        
        print(f"Converting {filename} to PDF...")
        try:
            # We can use the convert method from docx2pdf
            # convert(input_path, output_path)
            convert(docx_file, pdf_path)
            print(f"Successfully converted to {pdf_path}")
        except Exception as e:
            print(f"Error converting {filename}: {str(e)}")

    print("PDF conversion process completed.")

if __name__ == "__main__":
    main()
