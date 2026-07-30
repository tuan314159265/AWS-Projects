import json
import boto3
import os
from itemadapter import ItemAdapter

class SQSPipeline:
    def __init__(self):
        self.queue_url = os.environ.get('SQS_QUEUE_URL')
        # Sẽ tự động dùng quyền của AWS Fargate, không cần khai báo Access Key
        self.sqs_client = boto3.client('sqs', region_name=os.environ.get('AWS_REGION', 'us-east-1'))

    def process_item(self, item, spider):
        if not self.queue_url:
            spider.logger.warning("Bỏ qua item do không có URL SQS.")
            return item
        
        try:
            self.sqs_client.send_message(
                QueueUrl=self.queue_url,
                MessageBody=json.dumps(ItemAdapter(item).asdict(), ensure_ascii=False)
            )
            spider.logger.info(f"Đã gửi lên SQS: {item['url']}")
        except Exception as e:
            spider.logger.error(f"Lỗi SQS: {e}")
            
        return item