from django.test import TestCase, Client


class HealthzTests(TestCase):
    def test_healthz_ok(self):
        c = Client()
        resp = c.get('/healthz/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content.strip(), b'ok')

