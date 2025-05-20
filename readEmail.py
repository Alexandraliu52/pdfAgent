import re
import json
from email import policy
from email.parser import BytesParser
from bs4 import BeautifulSoup
import html2text
from typing import List, Dict, Any
import email.utils
from datetime import datetime

def extract_email_parts(msg):
    """提取邮件中正文和所有附件/非文本部分"""
    body_text = ""
    html_text = ""
    non_text_parts = []

    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disposition = part.get_content_disposition()
            filename = part.get_filename()

            if ctype == "text/plain" and disposition != "attachment":
                body_text += part.get_content()
            elif ctype == "text/html" and disposition != "attachment":
                html_text += part.get_content()
            elif disposition == "attachment" or filename:
                non_text_parts.append({
                    "filename": filename or "unnamed",
                    "content_type": ctype,
                    "is_inline": disposition == "inline"
                })
    else:
        ctype = msg.get_content_type()
        if ctype == "text/plain":
            body_text = msg.get_content()
        elif ctype == "text/html":
            html_text = msg.get_content()

    # fallback to html if no plain
    content = body_text.strip() if body_text.strip() else html2text.html2text(html_text)
    return content, non_text_parts

def extract_email_metadata(text: str) -> Dict[str, str]:
    """从邮件文本中提取元数据"""
    metadata = {
        "from": "",
        "to": "",
        "date": "",
        "subject": ""
    }
    
    # 匹配发件人
    from_patterns = [
        r"From:\s*([^\n]+)",
        r"发件人:\s*([^\n]+)"
    ]
    
    # 匹配收件人
    to_patterns = [
        r"To:\s*([^\n]+)",
        r"收件人:\s*([^\n]+)"
    ]
    
    # 匹配日期
    date_patterns = [
        r"Sent:\s*([^\n]+)",
        r"Date:\s*([^\n]+)",
        r"发送时间:\s*([^\n]+)",
        r"日期:\s*([^\n]+)"
    ]
    
    # 匹配主题
    subject_patterns = [
        r"Subject:\s*([^\n]+)",
        r"主题:\s*([^\n]+)"
    ]
    
    for pattern_list, key in [
        (from_patterns, "from"),
        (to_patterns, "to"),
        (date_patterns, "date"),
        (subject_patterns, "subject")
    ]:
        for pattern in pattern_list:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                metadata[key] = match.group(1).strip()
                break
                
    return metadata

def classify_block(text: str) -> str:
    """识别邮件块的类型"""
    text = text.strip()
    
    # 转发邮件的标识
    if any(marker in text for marker in [
        "Forwarded message",
        "---------- Forwarded message ----------",
        "转发的邮件"
    ]):
        return "FORWARD"
    
    # 回复邮件的标识
    if any(pattern.search(text) for pattern in [
        re.compile(r"On .* wrote:", re.IGNORECASE),
        re.compile(r"在.+写道："),
        re.compile(r"发件人:.+发送时间:", re.DOTALL),
        re.compile(r"From:.+Sent:", re.DOTALL)
    ]):
        return "REPLY"
    
    # 引用内容的标识
    if re.search(r"^\s*>", text, re.MULTILINE):
        return "QUOTED"
        
    # 自动回复等通知的标识
    if re.search(r"Auto-Reply|Out of Office|Delivery Status Notification", text, re.IGNORECASE):
        return "NOTICE"
        
    return "ORIGINAL"

def split_email_history(text: str) -> List[str]:
    """将邮件内容分割成多个历史部分"""
    # 定义分隔标记的模式
    patterns = [
        r"(?=\n?On .* wrote:)",
        r"(?=\n?>>> .* \d{2}\.\d{2}\.\d{4})",
        r"(?=\n?---------- Forwarded message ----------)",
        r"(?=\n?From: .*\nSent: .*\nTo: .*\nSubject:)",
        r"(?=\n?发件人: .*\n发送时间: .*\n收件人: .*\n主题:)",
        r"(?=\n?在.+写道：)",
    ]
    
    # 合并所有模式
    combined_pattern = '|'.join(patterns)
    
    # 分割文本
    parts = re.split(combined_pattern, text)
    
    # 清理和过滤分割后的部分
    cleaned_parts = []
    for part in parts:
        part = part.strip()
        if part and not part.isspace():
            # 移除多余的空行
            part = re.sub(r'\n\s*\n\s*\n+', '\n\n', part)
            cleaned_parts.append(part)
    
    return cleaned_parts

def parse_eml_to_json(file_path: str) -> List[Dict[str, Any]]:
    """解析.eml文件并返回结构化的邮件历史"""
    with open(file_path, 'rb') as f:
        msg = BytesParser(policy=policy.default).parse(f)

    # 提取主要内容和附件
    full_text, non_text_parts = extract_email_parts(msg)
    
    # 分割邮件历史
    blocks = split_email_history(full_text)
    
    # 构建结果
    result = []
    for i, block in enumerate(blocks):
        # 提取每个块的元数据
        metadata = extract_email_metadata(block)
        
        # 清理正文内容（移除元数据部分）
        content = block
        for key, value in metadata.items():
            if value:
                content = content.replace(f"{key}: {value}", "").strip()
        
        result.append({
            "index": i + 1,
            "action": classify_block(block),
            "metadata": metadata,
            "content": content,
            "non_text": non_text_parts if i == 0 else []
        })

    return result

if __name__ == "__main__":
    file_path = "C:/Users/AlexandraLiu/Downloads/Re_ R-Cloud-25075404 ACE Hardware - Toolsworks International Ltd.eml"  # 替换为实际的测试文件路径
    history_json = parse_eml_to_json(file_path)
    print(json.dumps(history_json, indent=2, ensure_ascii=False))
