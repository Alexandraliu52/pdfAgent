from flask import Flask, request, jsonify, render_template, send_file, url_for
from langchain_openai import AzureChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
from langchain.agents.format_scratchpad import format_log_to_messages
from langchain.agents.output_parsers import ReActSingleInputOutputParser
from langchain_core.messages import HumanMessage, SystemMessage
from langchain.tools import BaseTool
import os
from langchain_core.exceptions import OutputParserException
from PyPDF2 import PdfReader, PdfMerger
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def clean_up_files(*file_paths):
    """Safely delete files"""
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"Error deleting file {file_path}: {str(e)}")

def extract_text_from_pdf(file_path):
    """Extract text from PDF file"""
    try:
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    except Exception as e:
        return f"Unable to read PDF file: {str(e)}"

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

# Azure OpenAI LLM Configuration
llm = AzureChatOpenAI(
    azure_endpoint="https://qsp-prod.openai.azure.com",
    api_version="2025-01-01-preview",
    deployment_name="gpt-4o",
    api_key="key"
)

tools = [PDFMergerTool(), PDFSummarizerTool()]

# Get tool names and descriptions
tool_names = [tool.name for tool in tools]
tool_descriptions = "\n".join([f"{tool.name}: {tool.description}" for tool in tools])

REACT_TEMPLATE = """Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought: {agent_scratchpad}"""

prompt = PromptTemplate.from_template(template=REACT_TEMPLATE)

# Create the agent
agent = create_react_agent(
    llm=llm,
    tools=tools,
    prompt=prompt
)

# Create the agent executor
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    handle_parsing_errors=True
)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limit upload file size to 16MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/download/<filename>')
def download_file(filename):
    try:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # Send file
        response = send_file(
            file_path,
            as_attachment=True,
            download_name=filename
        )
        
        # Set callback to delete file after sending
        @response.call_on_close
        def cleanup():
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Error cleaning up merged file: {str(e)}")
        
        return response
    except Exception as e:
        return jsonify({'error': f'Error downloading file: {str(e)}'}), 404

@app.route('/chat_with_files', methods=['POST'])
def chat_with_files():
    uploaded_files = []  # Track uploaded file paths
    try:
        if 'files[]' not in request.files:
            return jsonify({'reply': 'Please upload PDF files'}), 400
        
        files = request.files.getlist('files[]')
        message = request.form.get('message', '')
        
        if not files:
            return jsonify({'reply': 'Please select PDF files'}), 400
        
        # Check all files
        for file in files:
            if file.filename == '':
                return jsonify({'reply': 'There are unselected files'}), 400
            if not allowed_file(file.filename):
                return jsonify({'reply': 'Only PDF file format is supported'}), 400
        
        # Save all files
        filepaths = []
        for file in files:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            file.close()  # Ensure file is closed
            filepaths.append(filepath)
            uploaded_files.append(filepath)
        
        # Prepare input for agent
        if len(filepaths) > 1:
            input_text = f"merge these PDF files: {','.join(filepaths)}"
        else:
            input_text = f"summarize this PDF file: {filepaths[0]}"
            
        # Call agent executor to process request
        response = agent_executor.invoke({"input": input_text})
        return jsonify({'reply': response['output']})
        
    except Exception as e:
        # Clean up uploaded files if processing fails
        for filepath in uploaded_files:
            clean_up_files(filepath)
        return jsonify({'reply': f'Error processing files: {str(e)}'}), 500

@app.route('/chat', methods=['POST'])
def chat():
    try:
        user_input = request.json['message']
        response = agent_executor.invoke({"input": user_input})
        return jsonify({'reply': response['output']})
    except OutputParserException as e:
        error_msg = str(e)
        return jsonify({'reply': 'Sorry, I need more information to process your request. ' + error_msg})
    except Exception as e:
        return jsonify({'reply': f'Sorry, an error occurred while processing your request: {str(e)}'})

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True) 
