from langchain.tools import BaseTool
from utils import extract_text_from_pdf, clean_up_files
from llm_config import llm
# Custom PDF Content Summarizer Tool
class PDFSummarizerTool(BaseTool):
    name: str = "pdf_summarizer"
    description: str = "Analyze and summarize the content of a PDF file, requires the PDF file path"
    return_direct: bool = True

    def _run(self, file_path: str) -> str:
        try:
            # Extract PDF text
            text = extract_text_from_pdf(file_path.strip())
            
            # Delete the original file after extracting content
            try:
                clean_up_files(file_path.strip())
            except Exception as e:
                print(f"Warning: Could not delete file {file_path}: {str(e)}")

            if text.startswith("Unable to read PDF file"):
                return text

            # Build summary prompt
            prompt = f"""Please analyze the following text content and generate a comprehensive summary. Include:
                1. Main topic and purpose of the document
                2. Key points and important information
                3. Main conclusions or recommendations (if any)

                Text content:
                {text}

                Please organize the summary in clear, concise language for easy understanding."""

            # Use LLM to generate summary
            response = llm.invoke(prompt)
            return response.content
            
        except Exception as e:
            return f"Error summarizing PDF content: {str(e)}"

    async def _arun(self, file_path: str) -> str:
        return self._run(file_path)

