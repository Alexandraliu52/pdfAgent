from langchain_openai import AzureChatOpenAI

llm = AzureChatOpenAI(
    azure_endpoint="https://qsp-prod.openai.azure.com",
    api_version="2025-01-01-preview",
    deployment_name="gpt-4o",
    api_key=""
)