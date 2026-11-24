from rest_framework import status

from .base import BaseAPITestCase


class RegisterTests(BaseAPITestCase):
    def test_register_contract(self):
        resp = self.client.post("/api/register/", {
            "username": "newuser", "email": "n@example.com", "password": "abc12345",
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("token", resp.data)
        self.assertEqual(resp.data["user"]["username"], "newuser")

    def test_register_duplicate_username(self):
        resp = self.client.post("/api/register/", {
            "username": "tester", "email": "", "password": "abc12345",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("username", resp.data)

    def test_register_weak_password(self):
        resp = self.client.post("/api/register/", {
            "username": "weakpw", "email": "", "password": "123456",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", resp.data)


class LoginTests(BaseAPITestCase):
    def test_login_contract(self):
        resp = self.client.post("/api/login/", {"username": "tester", "password": "password123"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("token", resp.data)
        self.assertEqual(set(resp.data["user"].keys()), {"id", "username", "email"})

    def test_login_invalid(self):
        resp = self.client.post("/api/login/", {"username": "tester", "password": "wrong"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["detail"], "Invalid credentials")
