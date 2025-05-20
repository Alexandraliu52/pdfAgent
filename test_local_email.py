import os
from app import EmailSummaryTool
import email
from email import policy
from email.utils import parsedate_to_datetime
from model import EmailData


def _extract_email_info( msg) -> EmailData:
    sender = msg.get('From', 'Unknown Sender')
    recipient = msg.get('To', 'Unknown Recipient')
    subject = msg.get('Subject', 'No Subject')
    message_id = msg.get('Message-ID', 'Unknown Message-ID')
    reply_to = msg.get('Reply-To', 'Unknown Reply-To')
    forwarded = msg.get('X-Forwarded-For', 'Not Forwarded')
    
    date_str = msg.get('Date', None)
    try:
        date = parsedate_to_datetime(date_str).isoformat() if date_str else 'No Date'
    except Exception:
        date = 'Invalid Date'
    
    body_plain = None
    body_html = None
    attachments = []

    def _process_email_part(part):
        nonlocal body_plain, body_html, attachments

        content_type = part.get_content_type()
        disposition = str(part.get("Content-Disposition", ""))

        if content_type == "message/rfc822":
            forwarded_msg = email.message_from_bytes(part.get_payload(decode=True), policy=policy.default)
            # Recursively process forwarded message parts
            _extract_email_info(forwarded_msg)
        
        # Extract plain text body
        elif content_type == "text/plain" and "attachment" not in disposition:
            if body_plain is None:
                body_plain = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
        
        elif content_type == "text/html" and "attachment" not in disposition:
            if body_html is None:
                body_html = part.get_payload(decode=True).decode(part.get_content_charset() or 'utf-8')
        
        elif part.get_filename() or "attachment" in disposition or content_type.startswith('application/'):
            file_name = part.get_filename() or "unnamed_attachment"
            attachment_data = part.get_payload(decode=True)
            
            # attachment_key = upload_file_to_s3(email_id, file_name, attachment_data, content_type)
            
            attachments.append({
                'file_name': file_name,
                'content_type': content_type,
                # 'file_key': attachment_key,
                'content_id': part.get('Content-ID'),
            })

    if msg.is_multipart():
        for part in msg.walk():
            _process_email_part(part)
    else:
        _process_email_part(msg)

    if not body_plain:
        body_plain = "No plain text content found"

    email_data = {
        'sender': sender,
        'recipient': recipient,
        'subject': subject,
        'date': date,
        'body_plain': body_plain,
        'attachments': attachments,
        'message_id': message_id,
        'reply_to': reply_to,
        'forwarded_from': forwarded
    }
    

    return EmailData(**email_data)



def test_local_email(eml_file_path):
    """
    Test EmailSummaryTool with a local eml file
    
    Args:
        eml_file_path (str): Path to the local .eml file
    """
    try:
        # Check if file exists
        if not os.path.exists(eml_file_path):
            print(f"Error: File not found at {eml_file_path}")
            return
        
        # Check if file is .eml
        if not eml_file_path.lower().endswith('.eml'):
            print("Error: File must be an .eml file")
            return
        
        # Initialize the tool
        # tool = EmailSummaryTool()
        file_path = "C:/Users/AlexandraLiu/Downloads/Antw_ Re_ [PAYMENT REMINDER] Castorama - Gust Alberts - INV-13W250007312.eml"
        with open(file_path, 'rb') as f:
            raw_bytes = f.read()
        # 兼容 analyzer 的初始化
        try:
            mime_content = raw_bytes.decode('utf-8')
        except UnicodeDecodeError:
            mime_content = raw_bytes.decode('latin1')
        
        message = email.message_from_string(mime_content, policy=policy.default)
        emailData =  _extract_email_info(message);
        # Process the email
        # print(f"\nProcessing email file: {eml_file_path}")
        # print("-" * 50)
        # result = tool._run(eml_file_path)
        # print("\nAnalysis Result:")
        # print("-" * 50)
        print(emailData)
        
    except Exception as e:
        print(f"Error processing email: {str(e)}")

if __name__ == "__main__":
    # Replace this path with your local eml file path
    email_file = "C:/Users/AlexandraLiu/Downloads/Antw_ Re_ [PAYMENT REMINDER] Castorama - Gust Alberts - INV-13W250007312.eml"
    test_local_email(email_file) 