import os
from app import EmailSummaryTool




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
        tool = EmailSummaryTool()
      
        # Process the email
        print(f"\nProcessing email file: {eml_file_path}")
        print("-" * 50)
        result = tool._run(eml_file_path)
        print("\nAnalysis Result:")
        print("-" * 50)
        print(result)
        
    except Exception as e:
        print(f"Error processing email: {str(e)}")

if __name__ == "__main__":
    # Replace this path with your local eml file path
    email_file = "C:/Users/AlexandraLiu/Downloads/Antw_ Re_ [PAYMENT REMINDER] Castorama - Gust Alberts - INV-13W250007312.eml"
    test_local_email(email_file) 