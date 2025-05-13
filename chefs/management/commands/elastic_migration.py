from chefs.models import Chef, ChefRequest
from elasticsearch_dsl import Document, Date, Integer, Keyword, Text, Boolean, Nested, InnerDoc
from elasticsearch_dsl.connections import connections
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from django.conf import settings
load_dotenv()
import os
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Indexes chef requests in Elasticsearch'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('Starting to index chef requests...'))
        es = Elasticsearch(
            "https://124031df79d3475bb86ae821e6ae2412.westus2.azure.elastic-cloud.com:443",
            api_key=os.getenv("ELASTIC_API_KEY")
        )

        chef_request_data = self.extract_chef_requests()

        for chef_request in chef_request_data:
            es.index(index='chef_requests', id=chef_request['id'], body=chef_request)
            self.stdout.write(self.style.SUCCESS(f'Indexed chef request {chef_request["id"]}'))

        self.stdout.write(self.style.SUCCESS('Finished indexing chef requests'))

    def extract_chef_requests(self):
        chef_requests = ChefRequest.objects.all()
        chef_request_data = []

        for chef_request in chef_requests:
            chef_request_data.append({
                "id": chef_request.id,
                "user": chef_request.user.username,
                "experience": chef_request.experience,
                "bio": chef_request.bio,
                "requested_postalcodes": [postalcode.code for postalcode in chef_request.requested_postalcodes.all()],
                "profile_pic": chef_request.profile_pic.url if chef_request.profile_pic else None,
                "is_approved": chef_request.is_approved
            })
        return chef_request_data
