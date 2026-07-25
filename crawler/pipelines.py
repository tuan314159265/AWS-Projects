import json
import os
import boto3

class SQSPipeline:
    def __init__(self):
        self.queue_url = os.getenv('SQS_QUEUE_URL')
        self.sqs = boto3.client('sqs', region_name=os.getenv('SQS_REGION', 'ap-southeast-2'))

    def process_item(self, item, spider):
        if not self.queue_url:
            spider.logger.warning("SQS_QUEUE_URL is not set!")
            return item
            
        message_body = json.dumps(dict(item), ensure_ascii=False)
        try:
            self.sqs.send_message(
                QueueUrl=self.queue_url,
                MessageBody=message_body
            )
        except Exception as e:
            spider.logger.error(f"Failed to send message to SQS: {e}")
        return item
