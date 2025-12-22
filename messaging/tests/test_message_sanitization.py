import pytest
from rest_framework.test import APIClient

from custom_auth.models import CustomUser
from chefs.models import Chef
from messaging.models import Conversation, Message
from messaging.serializers import MessageSerializer


@pytest.mark.django_db
class TestMessageSanitization:
    def setup_method(self):
        self.client = APIClient()
        self.customer = CustomUser.objects.create_user(
            username='cust1',
            email='cust1@example.com',
            password='testpass123'
        )
        self.chef_user = CustomUser.objects.create_user(
            username='chef1',
            email='chef1@example.com',
            password='testpass123'
        )
        self.chef = Chef.objects.create(user=self.chef_user)
        self.conversation = Conversation.objects.create(
            customer=self.customer,
            chef=self.chef
        )

    def test_send_message_strips_debug_timestamp_suffix(self):
        self.client.force_authenticate(user=self.chef_user)
        content = 'Chef hello 2025-12-21T13-09-24-658Z'

        response = self.client.post(
            f'/messaging/api/conversations/{self.conversation.id}/send/',
            {'content': content},
            format='json'
        )

        assert response.status_code == 201
        assert response.data['content'] == 'Chef hello'

        msg = Message.objects.get(id=response.data['id'])
        assert msg.content == 'Chef hello'

    def test_send_message_keeps_non_suffix_timestamp(self):
        self.client.force_authenticate(user=self.chef_user)
        content = 'Check 2025-12-21T13-09-24-658Z please'

        response = self.client.post(
            f'/messaging/api/conversations/{self.conversation.id}/send/',
            {'content': content},
            format='json'
        )

        assert response.status_code == 201
        assert response.data['content'] == content

    def test_serializer_strips_debug_suffix_for_existing_messages(self):
        raw_content = 'Customer hello 2025-12-22T06-40-54-167Z'
        msg = Message.objects.create(
            conversation=self.conversation,
            sender=self.customer,
            sender_type='customer',
            content=raw_content
        )

        data = MessageSerializer(msg).data
        assert data['content'] == 'Customer hello'
