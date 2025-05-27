from flask import Flask, request, jsonify, render_template, send_file
from langchain_openai import AzureChatOpenAI
from langchain.agents import AgentExecutor, create_react_agent
from langchain_core.prompts import PromptTemplate
import os
from langchain_core.exceptions import OutputParserException
from werkzeug.utils import secure_filename
from utils import clean_up_files
from pdf_merge_tool import PDFMergerTool
from pdf_summarizer_tool import PDFSummarizerTool
from email_summarizer_tool import EmailSummaryTool
from llm_config import llm

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf', 'eml'}

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)



tools = [PDFMergerTool(), PDFSummarizerTool(), EmailSummaryTool()]

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
            return jsonify({'reply': 'Please upload files'}), 400
        
        files = request.files.getlist('files[]')
        message = request.form.get('message', '')
        
        if not files:
            return jsonify({'reply': 'Please select files'}), 400
        
        # Check all files
        for file in files:
            if file.filename == '':
                return jsonify({'reply': 'There are unselected files'}), 400
            if not allowed_file(file.filename):
                return jsonify({'reply': 'Only PDF and EML file formats are supported'}), 400
        
        # Save all files
        filepaths = []
        for file in files:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            file.close()  # Ensure file is closed
            filepaths.append(filepath)
            uploaded_files.append(filepath)
        
        # Prepare input for agent based on file types
        if len(filepaths) > 1 and all(f.endswith('.pdf') for f in filepaths):
            input_text = f"merge these PDF files: {','.join(filepaths)}"
        elif len(filepaths) == 1 and filepaths[0].endswith('.pdf'):
            input_text = f"summarize this PDF file: {filepaths[0]}"
        elif len(filepaths) == 1 and filepaths[0].endswith('.eml'):
            input_text = f"analyze this email chain: {filepaths[0]}"
        else:
            return jsonify({'reply': 'Invalid combination of file types'}), 400
            
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