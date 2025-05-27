from flask import url_for
from langchain.tools import BaseTool
from PyPDF2 import PdfMerger
import os
from utils import clean_up_files

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'eml'}

# Custom PDF Merger Tool
class PDFMergerTool(BaseTool):
    name: str = "pdf_merger"
    description: str = "Merge multiple PDF files, requires a comma-separated list of PDF file paths"
    return_direct: bool = True

    def _run(self, file_paths: str) -> str:
        merger = None
        try:
            files = [f.strip() for f in file_paths.split(',')]
            if len(files) < 2:
                return "At least two PDF files are required for merging"
                
            merger = PdfMerger()
            
            # Add all PDF files in order
            for file in files:
                with open(file, 'rb') as pdf_file:
                    merger.append(pdf_file)
            
            # Create output filename
            output_filename = f"merged_{os.path.basename(files[0])}"
            output_path = os.path.join(UPLOAD_FOLDER, output_filename)
            
            # Save merged file
            with open(output_path, 'wb') as output_file:
                merger.write(output_file)
            
            # Close merger
            if merger:
                merger.close()
            
            # Clean up original files
            clean_up_files(*files)
            
            # Generate download link
            download_link = url_for('download_file', filename=output_filename, _external=True)
            return f"Successfully merged {len(files)} PDF files! Original files have been cleaned up. <download>{download_link}</download>"
            
        except Exception as e:
            if merger:
                merger.close()

            return f"Error merging PDF files: {str(e)}"

    async def _arun(self, file_paths: str) -> str:
        return self._run(file_paths)