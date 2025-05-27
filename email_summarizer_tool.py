
from langchain.tools import BaseTool
from email import policy
from email.parser import BytesParser
import re
import json
from bs4 import BeautifulSoup
import html2text
import uuid
from utils import clean_up_files
from llm_config import llm

class EmailSummaryTool(BaseTool):
    name: str = "email_chain_analyzer"
    description: str = "Analyze and summarize .eml email chain. Input should be the path to the .eml file."
    return_direct: bool = True

    def extract_preferred_content_from_eml(self, msg):
        """Preferably extract text/plain; if not available, then extract text/html."""
        plain = None
        html = None

        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == 'text/plain' and not plain:
                    plain = part.get_content()
                elif ctype == 'text/html' and not html:
                    html = part.get_content()
        else:
            ctype = msg.get_content_type()
            if ctype == 'text/plain':
                plain = msg.get_content()
            elif ctype == 'text/html':
                html = msg.get_content()

        return plain, html

    def parse_email_html_blockquotes(self,html):
        soup = BeautifulSoup(html, "html.parser")

        result = []

        def recurse(block, level=0):
            # Extract current layer text
            for bq in block.find_all('blockquote'):
                recurse(bq, level + 1)
                bq.decompose()  # Remove parsed blockquote

            text = block.get_text(separator="\n", strip=True)
            if text:
                result.append({
                    "id": str(uuid.uuid4()),
                    "level": level,
                    "sender": None,  # Optional to add sender/date extraction
                    "date": None,
                    "content": text
                })

        recurse(soup)
        result = list(reversed(result))  # The outermost layer is the first
        return result

    def parse_email_layers_grouped(self,text):
        # Main separator: the start of each email
        boundary_pattern = re.compile(
            r"(?:^|\n)(-+Original Message-+|On .*?wrote[:：]|From: .*|发件人[:：].*)",
            re.IGNORECASE
        )

        matches = list(boundary_pattern.finditer(text))
        blocks = []

        if not matches:
            return [{
                "id": str(uuid.uuid4()),
                "level": 0,
                "sender": None,
                "date": None,
                "content": text.strip()
            }]

        # The first segment may be the current email body
        if matches[0].start() > 0:
            blocks.append({
                "id": str(uuid.uuid4()),
                "level": 0,
                "sender": None,
                "date": None,
                "content": text[:matches[0].start()].strip()
            })

        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            segment = text[start:end].strip()

            # Extract complete email header (可能多行)
            header_lines = []
            body_lines = []
            in_header = True
            for line in segment.splitlines():
                if in_header and (
                    re.match(r"(From|发件人|Date|日期|Subject|主题|To|收件人|Cc|抄送)[:：]", line.strip(), re.IGNORECASE)
                    or re.match(r"On .* wrote[:：]", line.strip(), re.IGNORECASE)
                    or re.match(r"-+Original Message-+", line.strip(), re.IGNORECASE)
                ):
                    header_lines.append(line)
                else:
                    in_header = False
                    body_lines.append(line)

            header_text = "\n".join(header_lines)
            body_text = "\n".join(body_lines).strip()

            # Extract sender and date
            sender_match = re.search(r"(From|发件人)[:：]\s*(.*)", header_text, re.IGNORECASE)
            date_match = re.search(r"(Date|日期)[:：]\s*(.*)", header_text, re.IGNORECASE)

            blocks.append({
                "id": str(uuid.uuid4()),
                "level": i + 1,
                "sender": sender_match.group(2).strip() if sender_match else None,
                "date": date_match.group(2).strip() if date_match else None,
                "content": (header_text + "\n" + body_text).strip()
            })

        return blocks

    def parse_eml_file_smart(self, msg):
        """Intelligently parse the EML file, prioritizing text/plain content. Use the basic information available through the email library."""
        # Get basic email information
        basic_info = {
            "sender": msg.get("from", ""),
            "recipient": msg.get("to", ""),
            "subject": msg.get("subject", ""),
            "date": msg.get("date", ""),
            "cc": msg.get("cc", ""),
            "bcc": msg.get("bcc", ""),
            "message_id": msg.get("message-id", ""),
            "in_reply_to": msg.get("in-reply-to", ""),
            "references": msg.get("references", "")
        }

        # Extract email content
        plain, html = self.extract_preferred_content_from_eml(msg)

        if plain:
            print("[INFO] Parsing using text/plain...")
            layers = self.parse_email_layers_grouped(plain)
        elif html:
            print("[INFO] text/plain not found, parsing using HTML blockquote...")
            layers = self.parse_email_html_blockquotes(html2text.html2text(html))
        else:
            raise ValueError("No supported email content format found")

        # If layers are parsed, fill in the basic information to the first layer
        if layers and len(layers) > 0:
            # Keep the original level and content
            first_layer = layers[0]
            first_layer.update({
                "sender": first_layer.get("sender") or basic_info["sender"],
                "recipient": basic_info["recipient"],
                "subject": basic_info["subject"],
                "date": first_layer.get("date") or basic_info["date"],
                "cc": basic_info["cc"],
                "bcc": basic_info["bcc"],
                "message_id": basic_info["message_id"],
                "in_reply_to": basic_info["in_reply_to"],
                "references": basic_info["references"]
            })

        return layers


    def summarize_email_content(self,email_content):
        system_prompt = """You are an AI assistant specializing in email analysis and communication strategy. Your task is to analyze email threads and provide comprehensive insights and recommendations.

            ANALYSIS GUIDELINES:
            1. Identify each email in the chain (from newest to oldest)
            2. For each email, extract and analyze:
            - Sender and recipients,cc,bcc
            - Date and time
            - Subject
            - Main content and key points
            - Any action items or important information

            3. Thread Analysis:
            - Identify the main topic and overall context
            - Track the progression of discussion
            - Note key decisions and agreements
            - Highlight unresolved points
            - Map stakeholder involvement

            4. Response Recommendations:
            - Provide three distinct response options:
                a) Direct Response: Immediate action-focused reply
                b) Strategic Response: Relationship and long-term focused
                c) Clarifying Response: Information gathering approach

            FORMAT REQUIREMENTS:
            - Use clear headings and sections
            - Present information chronologically (newest to oldest)
            - Please output the email with as many layers as it contains, without merging or combining any two or more layers.
            - Use bullet points for clarity
            - Highlight action items and deadlines
            - Keep summaries concise and actionable"""

        # Prepare formatted email content for final analysis
        final_email_json = json.dumps(email_content, ensure_ascii=False, indent=2)
            
        # Create messages with system prompt and formatted content
        analysis_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Please analyze the following formatted email thread:\n\n{final_email_json}"}
        ]
            
        # Get LLM response for final analysis
        response = llm.invoke(analysis_messages)
        return response

    def _run(self, file_path: str) -> str:
        """Analyze and summarize an email chain from an .eml file."""
        try:
            with open(file_path, 'rb') as f:
                msg = BytesParser(policy=policy.default).parse(f)
            # Step 1: Parse email to extract raw data
            email_content = self.parse_eml_file_smart(msg)
            
            # Step 2: Analyze the formatted content
            response = self.summarize_email_content(email_content)

            # Clean up the EML file after processing
            try:
                clean_up_files(file_path.strip())
            except Exception as e:
                print(f"Warning: Could not delete file {file_path}: {str(e)}")
            
            return response.content
            
        except Exception as e:
            return f"Error analyzing email: {str(e)}"

    async def _arun(self, file_path: str) -> str:
        return self._run(file_path)