# Task-Oriented AI Assistant

This project is a web-based application that provides task-oriented AI assistance, including functionalities like merging PDF files, summarizing PDF content, and analyzing email chains. The application is built using Flask and integrates with Azure's OpenAI service for natural language processing.

## Features

- **Merge PDF Files**: Combine multiple PDF files into a single document.
- **Summarize PDF**: Generate a comprehensive summary of a PDF document.
- **Analyze Email**: Extract and analyze email information, providing insights into email threads.

## Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/yourrepository.git
   cd yourrepository
   ```

2. **Set up a virtual environment** (optional but recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\\Scripts\\activate`
   ```

3. **Install the dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**:
   - Ensure you have the necessary API keys and configurations for Azure OpenAI.

5. **Run the application**:
   ```bash
   python app.py
   ```

6. **Access the application**:
   - Open your web browser and go to `http://localhost:5000`.

## Usage

- **Upload Files**: Use the upload button to select PDF or EML files for processing.
- **Enter Commands**: Type commands like "merge PDF files" or "summarize this document" in the input box.
- **View Results**: The assistant will process your request and display the results in the chat interface.

## Configuration

- **Azure OpenAI**: The application uses Azure's OpenAI service. Ensure your API key and endpoint are correctly set in `llm_config.py`.

## Contributing

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/YourFeature`).
3. Commit your changes (`git commit -am 'Add some feature'`).
4. Push to the branch (`git push origin feature/YourFeature`).
5. Open a pull request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Thanks to the contributors and the open-source community for their support and resources.
- Special thanks to Azure OpenAI for providing the language model capabilities.
