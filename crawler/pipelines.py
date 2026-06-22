import json
from confluent_kafka import Producer
import os

class KafkaPipeline:
    def __init__(self):
        self.producer = Producer({
            'bootstrap.servers': os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9092')
        })

    def process_item(self, item, spider):
        line = json.dumps(dict(item), ensure_ascii=False).encode('utf-8')
        self.producer.produce(os.getenv('KAFKA_TOPIC_NEWS', 'news_raw'), value=line)
        self.producer.flush()
        return item
