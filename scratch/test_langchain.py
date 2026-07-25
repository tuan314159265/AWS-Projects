import boto3
import os
from dotenv import load_dotenv
from langchain_aws import BedrockEmbeddings

load_dotenv()

client = boto3.client(
    "bedrock-runtime",
    region_name=os.getenv("BEDROCK_REGION", "ap-southeast-1"),
    aws_access_key_id=os.getenv("2_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("2_SECRET_ACCESS_KEY")
)

try:
    embedder = BedrockEmbeddings(
        model_id="cohere.embed-multilingual-v3",
        client=client,
        region_name=os.getenv("BEDROCK_REGION", "ap-southeast-1")
    )
    res = embedder.embed_documents(["Hello world"])
    print(f"Langchain Bedrock success. Embeddings length: {len(res[0])}")
except Exception as e:
    print(f"Langchain Bedrock error: {e}")
