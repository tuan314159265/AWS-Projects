"""
Lambda handler cho ETL + Vectorize pipeline.
Được trigger bởi EventBridge Scheduler (02:00 UTC hàng ngày).
"""
import json
from etl.etl_warehouse import run_etl_warehouse
from vectorize.vectorize import run_vectorization

def handler(event, context):
    """Lambda entry point."""
    try:
        # Bước 1: ETL - Clean + Chunk + Insert warehouse
        etl_count = run_etl_warehouse(limit=50)
        
        # Bước 2: Vectorize - Embed + Insert pgvector
        vec_count = run_vectorization(batch_size=500)
        
        result = {
            "statusCode": 200,
            "body": json.dumps({
                "etl_processed": etl_count,
                "vectors_created": vec_count
            })
        }
        print(f"[OK] ETL: {etl_count} articles, Vectorize: {vec_count} vectors")
        return result
        
    except Exception as e:
        print(f"[ERROR] Pipeline failed: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
