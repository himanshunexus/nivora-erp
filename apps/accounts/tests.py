from django.contrib.auth.hashers import make_password
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import OTPChallenge, User, WorkspaceMembership


class OTPAuthenticationTests(TestCase):
    def test_login_and_register_pages_render(self):
        client = Client()

        login_response = client.get(reverse("accounts:login"))
        register_response = client.get(reverse("accounts:register"))

        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(register_response.status_code, 200)
        self.assertContains(login_response, "Login")
        self.assertContains(register_response, "Register")

    def test_request_and_verify_otp_api_issues_workspace_and_jwt_cookies(self):
        client = Client()
        email = "newuser@nivora.test"

        response = client.post(
            reverse("api_request_otp"),
            {
                "email": email,
                "full_name": "New User",
                "workspace_name": "North Yard",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

        challenge = OTPChallenge.objects.get(email=email)
        challenge.code_hash = make_password("123456")
        challenge.save(update_fields=["code_hash"])

        verify_response = client.post(
            reverse("api_verify_otp"),
            {"email": email, "code": "123456"},
        )
        payload = verify_response.json()

        self.assertEqual(verify_response.status_code, 200)
        self.assertTrue(payload["ok"])
        self.assertIn("nivora_access_token", verify_response.cookies)
        self.assertIn("nivora_refresh_token", verify_response.cookies)

        user = User.objects.get(email=email)
        self.assertEqual(user.default_workspace.name, "North Yard")
        self.assertTrue(
            WorkspaceMembership.objects.filter(
                user=user,
                workspace=user.default_workspace,
                is_default=True,
            ).exists()
        )
