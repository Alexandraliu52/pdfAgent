import os
from email import policy
from email.parser import BytesParser
from typing import List, Dict, Any
from email_mime_analyzer import MIMEAnalyzer

# 假设有一个 LLM summarization 函数
# 这里用一个简单的 mock 函数代替
# 实际使用时可替换为调用 OpenAI、Azure、Qwen 等 LLM API
class EmailSummaryTool(BaseTool):
    name: str = "email_chain_analyzer"
    description: str = "Analyze and summarize .eml email chain."
    return_direct: bool = True
    
    def llm_summarize_email(email_info: Dict[str, Any]) -> str:
        """
        Mock LLM summarization function. Replace with actual LLM API call.
        """
        summary = f"From: {email_info['headers'].get('from', 'N/A')}\n"
        summary += f"To: {email_info['headers'].get('to', 'N/A')}\n"
        summary += f"Subject: {email_info['headers'].get('subject', 'N/A')}\n"
        summary += f"Date: {email_info['headers'].get('date', 'N/A')}\n"
        summary += f"Body (plain): {email_info['body'].get('plain', '')[:200]}...\n"
        summary += f"Attachments: {len(email_info.get('attachments', []))}\n"
        summary += f"Embedded Images: {len(email_info.get('embedded_content', []))}\n"
        return summary


    def analyze_eml_file(file_path: str) -> List[Dict[str, Any]]:
        """
        读取本地eml文件，分析邮件链路，返回每一层邮件的详细内容。
        """
        with open(file_path, 'rb') as f:
            raw_bytes = f.read()
        # 兼容 analyzer 的初始化
        try:
            mime_content = raw_bytes.decode('utf-8')
        except UnicodeDecodeError:
            mime_content = raw_bytes.decode('latin1')
        analyzer = MIMEAnalyzer(mime_content)
        chain = analyzer.extract_email_chain()
        # 补充每层的附件和嵌入内容
        for idx, email in enumerate(chain):
            # 解析为 EmailMessage 对象以便提取附件和嵌入内容
            try:
                msg = BytesParser(policy=policy.default).parsebytes(email['body'].get('plain', '').encode('utf-8'))
            except Exception:
                msg = None
            if msg:
                email['attachments'] = analyzer.get_attachments(msg)
                email['embedded_content'] = analyzer.get_embedded_content(msg)
            else:
                email['attachments'] = []
                email['embedded_content'] = []
        return chain


    def summarize_email_chain(chain: List[Dict[str, Any]]) -> List[str]:
        """
        对邮件链路的每一层调用 LLM 进行总结。
        """
        summaries = []
        for idx, email in enumerate(chain):
            summary = llm_summarize_email(email)
            summaries.append(f"--- Email Level {idx} ---\n{summary}")
        return summaries


    def main():
        import argparse
        parser = argparse.ArgumentParser(description='Analyze and summarize .eml email chain.')
        parser.add_argument('eml_file', type=str, help='Path to the .eml file')
        args = parser.parse_args()
        
        chain = analyze_eml_file(args.eml_file)
        summaries = summarize_email_chain(chain)
        print("\n===== Email Chain Summaries =====\n")
        for summary in summaries:
            print(summary)

if __name__ == "__main__":
    main() 