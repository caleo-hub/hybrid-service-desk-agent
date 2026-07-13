import json, os
from pathlib import Path
import boto3
table=boto3.resource('dynamodb',region_name=os.environ.get('AWS_REGION','us-east-1')).Table(os.environ['CATALOG_TABLE'])
for item in json.loads((Path(__file__).resolve().parents[1]/'data/seed/catalog.json').read_text()): table.put_item(Item=item)
print('Catálogo fictício carregado no DynamoDB.')
