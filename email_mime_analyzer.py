import email
from email import policy
from email.parser import Parser
from email.message import EmailMessage
from typing import Dict, List, Optional, Tuple
import base64
import os
from datetime import datetime
import re
from bs4 import BeautifulSoup
import asyncio


class MIMEAnalyzer:
    def __init__(self, mime_content: str):
        """Initialize the MIME analyzer with raw MIME content"""
        self.mime_content = mime_content
        self.email_message = email.message_from_string(mime_content, policy=policy.default)
        
    def get_basic_headers(self, message=None) -> Dict[str, str]:
        """Extract basic email headers"""
        if message is None:
            message = self.email_message
            
        return {
            "subject": message.get("subject", ""),
            "from": message.get("from", ""),
            "to": message.get("to", ""),
            "cc": message.get("cc", ""),
            "date": message.get("date", ""),
            "message_id": message.get("message-id", ""),
            "in_reply_to": message.get("in-reply-to", ""),
            "references": message.get("references", ""),
            "thread_index": message.get("thread-index", "")
        }
    
    def get_email_body(self, message=None) -> Dict[str, str]:
        """Extract email body in both HTML and plain text formats"""
        if message is None:
            message = self.email_message
            
        body = {"text": "", "html": ""}
        
        if message.is_multipart():
            for part in message.walk():
                if part.get_content_maintype() == "text":
                    content_type = part.get_content_subtype()
                    if content_type == "plain":
                        body["text"] = part.get_content()
                    elif content_type == "html":
                        body["html"] = part.get_content()
        else:
            content_type = message.get_content_maintype()
            if content_type == "text":
                subtype = message.get_content_subtype()
                content = message.get_content()
                if subtype == "plain":
                    body["text"] = content
                elif subtype == "html":
                    body["html"] = content
                    
        return body
    
    def get_attachments(self, message=None) -> List[Dict[str, any]]:
        """Extract attachments from the email"""
        if message is None:
            message = self.email_message
            
        attachments = []
        
        for part in message.walk():
            if part.get_content_maintype() == 'multipart':
                continue
                
            content_disposition = part.get("Content-Disposition", "")
            if not content_disposition:
                continue
                
            if "attachment" not in content_disposition.lower():
                continue
                
            filename = part.get_filename()
            if filename:
                attachment = {
                    "filename": filename,
                    "content_type": part.get_content_type(),
                    "size": len(part.get_payload()),
                    "content_id": part.get("Content-ID", ""),
                    "content_disposition": content_disposition,
                    "payload": part.get_payload(decode=True)
                }
                attachments.append(attachment)
                
        return attachments
    
    def get_embedded_content(self, message=None) -> List[Dict[str, any]]:
        """Extract all embedded content (images, files) from the email"""
        if message is None:
            message = self.email_message
            
        embedded = []
        
        for part in message.walk():
            if part.get_content_maintype() == 'multipart':
                continue
                
            content_disposition = part.get("Content-Disposition", "")
            content_id = part.get("Content-ID", "")
            
            # Skip regular attachments
            if content_disposition and "attachment" in content_disposition.lower():
                continue
                
            # Look for embedded content
            if content_id or (content_disposition and "inline" in content_disposition.lower()):
                content = {
                    "content_type": part.get_content_type(),
                    "content_id": content_id.strip("<>") if content_id else "",
                    "filename": part.get_filename(),
                    "size": len(part.get_payload()),
                    "content_disposition": content_disposition,
                    "payload": part.get_payload(decode=True)
                }
                embedded.append(content)
                
        return embedded
    
    def extract_email_chain(self) -> List[Dict[str, any]]:
        """Extract and analyze the complete email chain"""
        chain = []
        
        # First, analyze the current email
        current_email = {
            "headers": self.get_basic_headers(),
            "body": self.get_email_body(),
            "attachments": self.get_attachments(),
            "embedded_content": self.get_embedded_content(),
            "level": 0  # Top level email
        }
        chain.append(current_email)
        
        # Extract quoted messages from both plain text and HTML
        body = current_email["body"]
        
        # Analyze HTML content for email chain
        if body["html"]:
            soup = BeautifulSoup(body["html"], 'html.parser')
            
            # Look for common email client quote patterns
            quote_patterns = [
                'blockquote',  # Standard HTML quote
                'div[class*="quote"]',  # Various email clients
                'div[class*="gmail_quote"]',  # Gmail
                'div[class*="outlook-quote"]',  # Outlook
                'div[style*="border-left"]',  # Common quote style
            ]
            
            level = 1
            for pattern in quote_patterns:
                quotes = soup.select(pattern)
                for quote in quotes:
                    quoted_email = {
                        "headers": {},
                        "body": {"html": str(quote), "text": quote.get_text()},
                        "attachments": [],
                        "embedded_content": [],
                        "level": level
                    }
                    
                    # Try to extract headers from the quote
                    header_text = quote.get_text()[:500]  # Look in first 500 chars
                    self._extract_headers_from_text(header_text, quoted_email["headers"])
                    
                    if quoted_email["headers"]:
                        chain.append(quoted_email)
                        level += 1
        
        # Analyze plain text content for email chain
        if body["text"]:
            text_parts = re.split(r'\n(?:[-_]{2,}|(?:Original Message|Forwarded Message)[-_]*)\n', body["text"])
            
            level = max([email["level"] for email in chain]) + 1
            for part in text_parts[1:]:  # Skip the first part (current email)
                quoted_email = {
                    "headers": {},
                    "body": {"text": part.strip(), "html": ""},
                    "attachments": [],
                    "embedded_content": [],
                    "level": level
                }
                
                # Try to extract headers from the text
                self._extract_headers_from_text(part[:500], quoted_email["headers"])
                
                if quoted_email["headers"]:
                    chain.append(quoted_email)
                    level += 1
        
        return chain
    
    def _extract_headers_from_text(self, text: str, headers: Dict[str, str]):
        """Helper method to extract email headers from text"""
        header_patterns = {
            "from": r"From:\s*([^\n]+)",
            "to": r"To:\s*([^\n]+)",
            "date": r"(?:Sent|Date):\s*([^\n]+)",
            "subject": r"Subject:\s*([^\n]+)"
        }
        
        for key, pattern in header_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                headers[key] = match.group(1).strip()
    
#     def analyze_full_email(self) -> Dict[str, any]:
#         """Perform a complete analysis of the email including the entire chain"""
#         chain = self.extract_email_chain()
        
#         # Additional analysis of the entire thread
#         thread_analysis = {
#             "total_emails": len(chain),
#             "thread_subject": self.get_basic_headers()["subject"],
#             "participants": set(),
#             "date_range": {"earliest": None, "latest": None},
#             "total_attachments": 0,
#             "total_embedded": 0,
#             "content_types": set()
#         }
        
#         for email in chain:
#             # Add participants
#             if "from" in email["headers"]:
#                 thread_analysis["participants"].add(email["headers"]["from"])
#             if "to" in email["headers"]:
#                 thread_analysis["participants"].update(email["headers"]["to"].split(","))
                
#             # Update date range
#             if "date" in email["headers"]:
#                 try:
#                     date = email["headers"]["date"]
#                     if thread_analysis["date_range"]["earliest"] is None:
#                         thread_analysis["date_range"]["earliest"] = date
#                     if thread_analysis["date_range"]["latest"] is None:
#                         thread_analysis["date_range"]["latest"] = date
#                     thread_analysis["date_range"]["earliest"] = min(thread_analysis["date_range"]["earliest"], date)
#                     thread_analysis["date_range"]["latest"] = max(thread_analysis["date_range"]["latest"], date)
#                 except:
#                     pass
            
#             # Count attachments and embedded content
#             thread_analysis["total_attachments"] += len(email.get("attachments", []))
#             thread_analysis["total_embedded"] += len(email.get("embedded_content", []))
            
#             # Track content types
#             for attachment in email.get("attachments", []):
#                 thread_analysis["content_types"].add(attachment["content_type"])
#             for embedded in email.get("embedded_content", []):
#                 thread_analysis["content_types"].add(embedded["content_type"])
        
#         thread_analysis["participants"] = list(thread_analysis["participants"])
#         thread_analysis["content_types"] = list(thread_analysis["content_types"])
        
#         return {
#             "thread_analysis": thread_analysis,
#             "email_chain": chain
#         }

# def analyze_email_mime(mime_content: str) -> Dict[str, any]:
#     """
#     Analyze email MIME content and return a structured representation including the full email chain
    
#     Args:
#         mime_content (str): Raw MIME content of the email
        
#     Returns:
#         Dict containing:
#         - thread_analysis: Overall analysis of the email thread
#         - email_chain: List of all emails in the chain with their details
#     """
#     analyzer = MIMEAnalyzer(mime_content)
#     return analyzer.analyze_full_email()



# async def main():

#     # Example MIME content
#      # Initialize the Graph client
#     client =  await initialize_graph_client()
#     sample_mime = await get_email_mime_content(client,
#                              "AQMkADNmYzI2MmE0LWE1OTItNGE1My1hNzQ3LTM0Njc2NzI4MmFlZABGAAADFGr-D2DXAUyc8tng0Nc-8wcAKCZ2oVgOhU6_Ac1Wpjx0XgAAAgEMAAAAKCZ2oVgOhU6_Ac1Wpjx0XgABtiQONgAAAA=="
#     )

#     # Analyze the email
#     result = analyze_email_mime(sample_mime)
    
#     # Print thread analysis
#     print("Thread Analysis:")
#     print(f"Total emails in chain: {result['thread_analysis']['total_emails']}")
#     print(f"Participants: {', '.join(result['thread_analysis']['participants'])}")
#     print(f"Date range: {result['thread_analysis']['date_range']}")
#     print(f"Total attachments: {result['thread_analysis']['total_attachments']}")
#     print(f"Content types: {', '.join(result['thread_analysis']['content_types'])}")
    
#     # Print each email in the chain
#     print("\nEmail Chain:")
#     for email in result['email_chain']:
#         print(f"\nLevel {email['level']}:")
#         print(f"From: {email['headers'].get('from', 'N/A')}")
#         print(f"Subject: {email['headers'].get('subject', 'N/A')}")
#         if email['attachments']:
#             print(f"Attachments: {len(email['attachments'])}")
#         if email['embedded_content']:
#             print(f"Embedded content: {len(email['embedded_content'])}") 



# Example usage:
# if __name__ == "__main__":
#     asyncio.run(main())