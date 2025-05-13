from chefs.models import Chef, ChefRequest
from elasticsearch_dsl import Document, Date, Integer, Keyword, Text, Boolean, Nested, InnerDoc
from elasticsearch_dsl.connections import connections
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
load_dotenv()
import os

# Define a default Elasticsearch client
es = Elasticsearch(
  "https://124031df79d3475bb86ae821e6ae2412.westus2.azure.elastic-cloud.com:443",
  api_key= os.getenv("ELASTIC_API_KEY")
)

def extract_chefs():
    chefs = Chef.objects.all()
    chef_data = []

    for chef in chefs:
        chef_data.append({
            "id": chef.id,
            "user": chef.user.username,
            "experience": chef.experience,
            "bio": chef.bio,
            "profile_pic": chef.profile_pic.url if chef.profile_pic else None,
            "servicing_postalcodes": [postalcode.code for postalcode in chef.serving_postalcodes.all()],
            "review_summary": chef.review_summary,
            "featured_dishes": [dish.name for dish in chef.featured_dishes.all()],
            "reviews": [review.content for review in chef.reviews.all()]
        })
    return chef_data

chef_data = extract_chefs()

for chef in chef_data:
    es.index(index='chefs', doc_type='chef', id=chef['id'], body=chef)
