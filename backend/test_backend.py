"""Unit tests for MeetMind Core backend (Phase 1 & 2)."""

import os
import unittest
from unittest.mock import patch, MagicMock
import asyncio

# Configure dummy environment variables before loading app config
os.environ["GEMINI_API_KEY"] = "fake_gemini_key"
os.environ["SUPABASE_URL"] = "https://fake-supabase-url.supabase.co"
os.environ["SUPABASE_SERVICE_KEY"] = "fake_supabase_service_key"
os.environ["TEST_USER_ID"] = "00000000-0000-0000-0000-000000000000"
os.environ["MOCK_MODE"] = "False"

from fastapi.testclient import TestClient
from main import app
from models.schemas import MOM
from services.ai_processor import process_transcript
from services.qa_service import answer_question


class TestMeetMindCore(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        from middleware.rate_limit import limiter
        limiter.enabled = False
        
        # Intercept client requests to automatically prefix /api/v1 and inject CSRF tokens
        original_request = self.client.request
        def request_wrapper(method, url, *args, **kwargs):
            # Auto-prefix with /api/v1 if needed
            if not url.startswith("/api/v1") and url not in ["/", "/health", "/api/v1/health"]:
                url = f"/api/v1{url}"
            
            # Add CSRF token for state-changing requests
            if method in ["POST", "PUT", "DELETE"]:
                headers = kwargs.get("headers")
                if headers is None:
                    headers = {}
                elif not isinstance(headers, dict):
                    headers = dict(headers)
                cookies = kwargs.get("cookies")
                if cookies is None:
                    cookies = {}
                elif not isinstance(cookies, dict):
                    cookies = dict(cookies)
                    
                csrf_val = "test_csrf_token_123"
                headers["X-CSRF-Token"] = csrf_val
                cookies["csrf_token"] = csrf_val
                
                kwargs["headers"] = headers
                kwargs["cookies"] = cookies
                
            return original_request(method, url, *args, **kwargs)
            
        self.client.request = request_wrapper
        
        # Standard headers for authenticated endpoints
        self.auth_headers = {"Authorization": "Bearer valid_token"}
        from routes.auth import MOCK_PROFILES
        MOCK_PROFILES.clear()

    def test_root_endpoint(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "status": "MeetMind backend is live",
            "mode": "Beta Free Mode",
            "documentation": "/docs"
        })

    def test_health_endpoint(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("services.ai_processor.genai.GenerativeModel")
    def test_process_transcript(self, mock_gen_model_class):
        # Setup mock model responses
        mock_model = MagicMock()
        mock_gen_model_class.return_value = mock_model

        # Mock generate_content response for MOM
        mock_mom_response = MagicMock()
        mock_mom_response.text = """
        {
          "attendees": ["Alice", "Bob"],
          "date": "2026-06-25",
          "agenda": ["Project kick-off"],
          "decisions": ["Use FastAPI"],
          "action_items": [
            {
              "task": "Create models",
              "owner": "Alice",
              "deadline": "2026-06-30"
            }
          ]
        }
        """

        # Mock generate_content response for Summary
        mock_summary_response = MagicMock()
        mock_summary_response.text = """
        - Bullet point 1
        - Bullet point 2
        - Bullet point 3
        - Bullet point 4
        - Bullet point 5
        """

        # Set up side_effect to return mom response then summary response
        mock_model.generate_content.side_effect = [mock_mom_response, mock_summary_response]

        # Run process_transcript
        mom, summary = asyncio.run(process_transcript("Mock transcript text"))

        # Verify results
        self.assertIsInstance(mom, MOM)
        self.assertEqual(mom.attendees, ["Alice", "Bob"])
        self.assertEqual(mom.action_items[0].task, "Create models")
        self.assertIn("Bullet point 1", summary)
        self.assertEqual(mock_model.generate_content.call_count, 2)

    @patch("services.qa_service.genai.GenerativeModel")
    def test_qa_service(self, mock_gen_model_class):
        mock_model = MagicMock()
        mock_gen_model_class.return_value = mock_model

        mock_response = MagicMock()
        mock_response.text = "FastAPI was chosen."
        mock_model.generate_content.return_value = mock_response

        answer = asyncio.run(answer_question("Mock transcript", "What framework was chosen?"))
        self.assertEqual(answer, "FastAPI was chosen.")
        mock_model.generate_content.assert_called_once()

    # --- Phase 2: Auth Unit Tests ---

    @patch("routes.auth.get_supabase")
    def test_signup_success(self, mock_get_supabase):
        mock_db = MagicMock()
        mock_get_supabase.return_value = mock_db

        # Mock auth response
        mock_user = MagicMock()
        mock_user.id = "11111111-1111-1111-1111-111111111111"
        mock_user.email = "test@example.com"
        mock_auth_resp = MagicMock()
        mock_auth_resp.user = mock_user
        mock_db.auth.sign_up.return_value = mock_auth_resp

        response = self.client.post(
            "/auth/signup",
            json={"email": "test@example.com", "password": "SecureP@ss123"}
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("Signup successful", data["message"])
        self.assertEqual(data["user"]["email"], "test@example.com")



    @patch("routes.auth.get_supabase")
    def test_login_success(self, mock_get_supabase):
        mock_db = MagicMock()
        mock_get_supabase.return_value = mock_db

        # Mock auth login response
        mock_user = MagicMock()
        mock_user.id = "11111111-1111-1111-1111-111111111111"
        mock_user.email = "test@example.com"
        mock_session = MagicMock()
        mock_session.access_token = "fake_access_token"

        mock_auth_resp = MagicMock()
        mock_auth_resp.user = mock_user
        mock_auth_resp.session = mock_session
        mock_db.auth.sign_in_with_password.return_value = mock_auth_resp

        response = self.client.post(
            "/auth/login",
            json={"email": "test@example.com", "password": "SecureP@ss123"}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["access_token"], "fake_access_token")
        self.assertEqual(data["user"]["email"], "test@example.com")

    def test_protected_route_without_token(self):
        response = self.client.get("/meetings/00000000-0000-0000-0000-000000000000")
        self.assertEqual(response.status_code, 401)  # Missing Auth header

    @patch("routes.auth.get_supabase")
    def test_protected_route_invalid_token(self, mock_get_supabase):
        mock_db = MagicMock()
        mock_get_supabase.return_value = mock_db
        mock_db.auth.get_user.side_effect = Exception("Invalid token")

        response = self.client.get(
            "/meetings/00000000-0000-0000-0000-000000000000",
            headers={"Authorization": "Bearer invalid_token"}
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "Invalid or expired access token")

    @patch("routes.auth.get_supabase")
    @patch("routes.meetings.get_supabase")
    def test_get_meeting_not_found(self, mock_meetings_supabase, mock_auth_supabase):
        # Mock auth
        mock_auth_db = MagicMock()
        mock_auth_supabase.return_value = mock_auth_db
        mock_user = MagicMock()
        mock_user.id = "11111111-1111-1111-1111-111111111111"
        mock_auth_resp = MagicMock()
        mock_auth_resp.user = mock_user
        mock_auth_db.auth.get_user.return_value = mock_auth_resp

        # Mock meetings empty
        mock_meet_db = MagicMock()
        mock_meetings_supabase.return_value = mock_meet_db
        mock_meet_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None

        response = self.client.get(
            "/meetings/00000000-0000-0000-0000-000000000000",
            headers=self.auth_headers
        )
        self.assertEqual(response.status_code, 404)

    @patch("routes.auth.get_supabase")
    @patch("routes.meetings.get_supabase")
    def test_get_meeting_owner_check_failure(self, mock_meetings_supabase, mock_auth_supabase):
        # Mock auth (current user id: 11111111-...)
        mock_auth_db = MagicMock()
        mock_auth_supabase.return_value = mock_auth_db
        mock_user = MagicMock()
        mock_user.id = "11111111-1111-1111-1111-111111111111"
        mock_auth_resp = MagicMock()
        mock_auth_resp.user = mock_user
        mock_auth_db.auth.get_user.return_value = mock_auth_resp

        # Mock meeting owned by user 22222222-...
        mock_meet_db = MagicMock()
        mock_meetings_supabase.return_value = mock_meet_db
        mock_meet_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "id": "00000000-0000-0000-0000-000000000000",
            "user_id": "22222222-2222-2222-2222-222222222222",
            "title": "Stolen Meeting",
            "status": "done"
        }

        response = self.client.get(
            "/meetings/00000000-0000-0000-0000-000000000000",
            headers=self.auth_headers
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["detail"], "You do not have permission to access this meeting")

    @patch("routes.auth.get_supabase")
    @patch("routes.meetings.get_supabase")
    def test_get_meeting_success(self, mock_meetings_supabase, mock_auth_supabase):
        # Mock auth
        mock_auth_db = MagicMock()
        mock_auth_supabase.return_value = mock_auth_db
        mock_user = MagicMock()
        mock_user.id = "11111111-1111-1111-1111-111111111111"
        mock_auth_resp = MagicMock()
        mock_auth_resp.user = mock_user
        mock_auth_db.auth.get_user.return_value = mock_auth_resp

        # Mock meeting fetch success
        mock_meet_db = MagicMock()
        mock_meetings_supabase.return_value = mock_meet_db
        mock_meet_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "id": "00000000-0000-0000-0000-000000000000",
            "user_id": "11111111-1111-1111-1111-111111111111",
            "title": "My Meeting",
            "mom": {
                "attendees": ["Alice"],
                "date": "2026-06-25",
                "agenda": [],
                "decisions": [],
                "action_items": []
            },
            "status": "done",
            "created_at": "2026-06-25T09:00:00+00:00"
        }

        response = self.client.get(
            "/meetings/00000000-0000-0000-0000-000000000000",
            headers=self.auth_headers
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["title"], "My Meeting")
        self.assertEqual(data["mom"]["attendees"], ["Alice"])

    @patch("routes.auth.get_supabase")
    @patch("routes.meetings.get_supabase")
    @patch("routes.meetings.verify_file_type")
    @patch("routes.meetings.transcribe_audio")
    @patch("routes.meetings.process_transcript")
    @patch("routes.meetings.subprocess.run")
    def test_upload_meeting_success(self, mock_sub_run, mock_process, mock_transcribe, mock_verify, mock_meetings_supabase, mock_auth_supabase):
        mock_verify.return_value = True
        # Mock subprocess.run to return a successful process output containing mock duration format JSON
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = b'{"format": {"duration": "120.0"}}'
        mock_sub_run.return_value = mock_proc

        # Mock auth
        mock_auth_db = MagicMock()
        mock_auth_supabase.return_value = mock_auth_db
        mock_user = MagicMock()
        mock_user.id = "11111111-1111-1111-1111-111111111111"
        mock_auth_resp = MagicMock()
        mock_auth_resp.user = mock_user
        mock_auth_db.auth.get_user.return_value = mock_auth_resp

        # Mock db
        mock_meet_db = MagicMock()
        mock_meetings_supabase.return_value = mock_meet_db

        # Mock AI & Whisper
        mock_transcribe.return_value = "This is a transcribed meeting."
        mock_mom = MOM(
            attendees=["Alice"],
            date="2026-06-25",
            agenda=[],
            decisions=[],
            action_items=[]
        )
        mock_process.return_value = (mock_mom, "Summary points")

        from io import BytesIO
        file_io = BytesIO(b"fake audio data")

        response = self.client.post(
            "/meetings/upload",
            files={"file": ("test_meeting.mp3", file_io, "audio/mpeg")},
            data={"title": "Test Title"},
            headers=self.auth_headers
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "done")
        self.assertEqual(data["message"], "Meeting processed successfully")

    @patch("routes.auth.get_supabase")
    @patch("routes.qa.get_supabase")
    @patch("routes.qa.answer_question")
    def test_qa_endpoint_success(self, mock_answer_question, mock_qa_supabase, mock_auth_supabase):
        # Mock auth
        mock_auth_db = MagicMock()
        mock_auth_supabase.return_value = mock_auth_db
        mock_user = MagicMock()
        mock_user.id = "11111111-1111-1111-1111-111111111111"
        mock_auth_resp = MagicMock()
        mock_auth_resp.user = mock_user
        mock_auth_db.auth.get_user.return_value = mock_auth_resp

        # Mock qa db
        mock_qa_db = MagicMock()
        mock_qa_supabase.return_value = mock_qa_db
        mock_qa_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "user_id": "11111111-1111-1111-1111-111111111111",
            "transcript": "FastAPI is great."
        }

        # Mock QA service
        mock_answer_question.return_value = "This is the answer."

        response = self.client.get(
            "/qa/00000000-0000-0000-0000-000000000000?q=Is FastAPI great?",
            headers=self.auth_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"answer": "This is the answer."})

    @patch("routes.auth.get_supabase")
    @patch("routes.qa.get_supabase")
    def test_qa_endpoint_owner_failure(self, mock_qa_supabase, mock_auth_supabase):
        # Mock auth
        mock_auth_db = MagicMock()
        mock_auth_supabase.return_value = mock_auth_db
        mock_user = MagicMock()
        mock_user.id = "11111111-1111-1111-1111-111111111111"
        mock_auth_resp = MagicMock()
        mock_auth_resp.user = mock_user
        mock_auth_db.auth.get_user.return_value = mock_auth_resp

        # Mock qa db with different owner
        mock_qa_db = MagicMock()
        mock_qa_supabase.return_value = mock_qa_db
        mock_qa_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "user_id": "22222222-2222-2222-2222-222222222222",
            "transcript": "Secret data."
        }

        response = self.client.get(
            "/qa/00000000-0000-0000-0000-000000000000?q=What is secret?",
            headers=self.auth_headers
        )
        self.assertEqual(response.status_code, 403)

    @patch("routes.auth.get_supabase")
    @patch("routes.meetings.get_supabase")
    def test_list_meetings_success(self, mock_meetings_supabase, mock_auth_supabase):
        # Mock auth
        mock_auth_db = MagicMock()
        mock_auth_supabase.return_value = mock_auth_db
        mock_user = MagicMock()
        mock_user.id = "11111111-1111-1111-1111-111111111111"
        mock_auth_resp = MagicMock()
        mock_auth_resp.user = mock_user
        mock_auth_db.auth.get_user.return_value = mock_auth_resp

        # Mock meetings list
        mock_meet_db = MagicMock()
        mock_meetings_supabase.return_value = mock_meet_db
        mock_meet_db.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
            {
                "id": "00000000-0000-0000-0000-000000000000",
                "user_id": "11111111-1111-1111-1111-111111111111",
                "title": "Meeting 1",
                "mom": None,
                "status": "done",
                "created_at": "2026-06-25T09:00:00+00:00"
            }
        ]

        response = self.client.get("/meetings", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["title"], "Meeting 1")

    @patch("routes.auth.get_supabase")
    def test_get_profile_success(self, mock_auth_supabase):
        mock_auth_db = MagicMock()
        mock_auth_supabase.return_value = mock_auth_db
        mock_user = MagicMock()
        mock_user.id = "22222222-2222-2222-2222-222222222222"
        mock_user.email = "test@example.com"
        mock_auth_resp = MagicMock()
        mock_auth_resp.user = mock_user
        mock_auth_db.auth.get_user.return_value = mock_auth_resp

        # Mock profiles row
        mock_auth_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "id": "22222222-2222-2222-2222-222222222222",
            "is_pro": False,
            "meetings_used": 2,
            "razorpay_subscription_id": None
        }

        response = self.client.get("/auth/profile", headers=self.auth_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["email"], "test@example.com")
        self.assertEqual(data["is_pro"], False)
        self.assertEqual(data["meetings_used"], 2)

    @patch("routes.auth.get_supabase")
    @patch("routes.meetings.get_supabase")
    def test_limit_checking_allowed(self, mock_meetings_supabase, mock_auth_supabase):
        # Mock auth
        mock_auth_db = MagicMock()
        mock_auth_supabase.return_value = mock_auth_db
        mock_user = MagicMock()
        mock_user.id = "22222222-2222-2222-2222-222222222222"
        mock_user.email = "test@example.com"
        mock_auth_resp = MagicMock()
        mock_auth_resp.user = mock_user
        mock_auth_db.auth.get_user.return_value = mock_auth_resp

        # Mock profile: not is_pro and meetings_used = 3 (limit is 3 for free, but free beta allows it)
        mock_auth_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "id": "22222222-2222-2222-2222-222222222222",
            "is_pro": False,
            "meetings_used": 3,
            "razorpay_subscription_id": None
        }

        # Mock meetings DB
        mock_meet_db = MagicMock()
        mock_meetings_supabase.return_value = mock_meet_db

        # Upload an empty file - it should pass the limit check and get rejected with 400 bad request (empty file) instead of 403
        response = self.client.post(
            "/meetings/upload",
            files={"file": ("test_meeting.mp3", b"", "audio/mpeg")},
            data={"title": "Test Title"},
            headers=self.auth_headers
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("empty or corrupt", response.json()["detail"].lower())

    @patch("routes.auth.get_supabase")
    @patch("routes.meetings.get_supabase")
    def test_export_pdf_free_user_allowed(self, mock_meetings_supabase, mock_auth_supabase):
        # Mock auth
        mock_auth_db = MagicMock()
        mock_auth_supabase.return_value = mock_auth_db
        mock_user = MagicMock()
        mock_user.id = "22222222-2222-2222-2222-222222222222"
        mock_user.email = "test@example.com"
        mock_auth_resp = MagicMock()
        mock_auth_resp.user = mock_user
        mock_auth_db.auth.get_user.return_value = mock_auth_resp

        # Mock profile: not is_pro
        mock_auth_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "id": "22222222-2222-2222-2222-222222222222",
            "is_pro": False,
            "meetings_used": 1,
            "razorpay_subscription_id": None
        }

        # Mock meeting database record with MOM
        mock_meet_db = MagicMock()
        mock_meetings_supabase.return_value = mock_meet_db
        mock_meet_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "id": "00000000-0000-0000-0000-000000000000",
            "user_id": "22222222-2222-2222-2222-222222222222",
            "title": "Free User Meeting",
            "mom": {
                "attendees": ["Alice", "Bob"],
                "date": "2026-06-25",
                "agenda": ["Test"],
                "decisions": [],
                "action_items": []
            },
            "status": "done",
            "created_at": "2026-06-25T09:00:00+00:00"
        }

        response = self.client.get(
            "/meetings/00000000-0000-0000-0000-000000000000/export/pdf",
            headers=self.auth_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")

    @patch("routes.auth.get_supabase")
    @patch("routes.meetings.get_supabase")
    def test_export_pdf_pro_success(self, mock_meetings_supabase, mock_auth_supabase):
        # Mock auth
        mock_auth_db = MagicMock()
        mock_auth_supabase.return_value = mock_auth_db
        mock_user = MagicMock()
        mock_user.id = "22222222-2222-2222-2222-222222222222"
        mock_user.email = "test@example.com"
        mock_auth_resp = MagicMock()
        mock_auth_resp.user = mock_user
        mock_auth_db.auth.get_user.return_value = mock_auth_resp

        # Mock profile: is_pro
        mock_auth_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "id": "22222222-2222-2222-2222-222222222222",
            "is_pro": True,
            "meetings_used": 1,
            "razorpay_subscription_id": "sub_123"
        }

        # Mock meeting database record with MOM
        mock_meet_db = MagicMock()
        mock_meetings_supabase.return_value = mock_meet_db
        mock_meet_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "id": "00000000-0000-0000-0000-000000000000",
            "user_id": "22222222-2222-2222-2222-222222222222",
            "title": "Pro Meeting",
            "mom": {
                "attendees": ["Alice", "Bob"],
                "date": "2026-06-25",
                "agenda": ["Test"],
                "decisions": [],
                "action_items": []
            },
            "status": "done",
            "created_at": "2026-06-25T09:00:00+00:00"
        }

        response = self.client.get(
            "/meetings/00000000-0000-0000-0000-000000000000/export/pdf",
            headers=self.auth_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertTrue(len(response.content) > 0)

    @patch("routes.auth.get_supabase")
    def test_upload_empty_file(self, mock_auth_supabase):
        # Mock auth & profile
        mock_auth_db = MagicMock()
        mock_auth_supabase.return_value = mock_auth_db
        mock_user = MagicMock()
        mock_user.id = "22222222-2222-2222-2222-222222222222"
        mock_user.email = "test@example.com"
        mock_auth_resp = MagicMock()
        mock_auth_resp.user = mock_user
        mock_auth_db.auth.get_user.return_value = mock_auth_resp

        mock_auth_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "id": "22222222-2222-2222-2222-222222222222",
            "is_pro": False,
            "meetings_used": 1
        }

        # Send request with empty file
        response = self.client.post(
            "/meetings/upload",
            headers=self.auth_headers,
            files={"file": ("empty.mp3", b"", "audio/mpeg")},
            data={"title": "Empty Meeting"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("empty", response.json()["detail"].lower())

    @patch("routes.auth.get_supabase")
    def test_upload_too_large_file(self, mock_auth_supabase):
        # Mock auth & profile
        mock_auth_db = MagicMock()
        mock_auth_supabase.return_value = mock_auth_db
        mock_user = MagicMock()
        mock_user.id = "22222222-2222-2222-2222-222222222222"
        mock_user.email = "test@example.com"
        mock_auth_resp = MagicMock()
        mock_auth_resp.user = mock_user
        mock_auth_db.auth.get_user.return_value = mock_auth_resp

        mock_auth_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "id": "22222222-2222-2222-2222-222222222222",
            "is_pro": False,
            "meetings_used": 1
        }

        # Modify MAX_FILE_SIZE_PRO temporarily
        import routes.meetings
        old_size = routes.meetings.MAX_FILE_SIZE_PRO
        routes.meetings.MAX_FILE_SIZE_PRO = 100
        try:
            # Send request with > 100 bytes file
            large_content = b"x" * 105
            response = self.client.post(
                "/meetings/upload",
                headers=self.auth_headers,
                files={"file": ("large.mp3", large_content, "audio/mpeg")},
                data={"title": "Large Meeting"}
            )
            self.assertEqual(response.status_code, 413)
            self.assertIn("file too large", response.json()["detail"].lower())
        finally:
            routes.meetings.MAX_FILE_SIZE_PRO = old_size

    @patch("routes.cron.get_supabase")
    def test_cron_reset_monthly_success(self, mock_cron_supabase):
        mock_db = MagicMock()
        mock_cron_supabase.return_value = mock_db
        mock_db.table.return_value.update.return_value.eq.return_value.execute.return_value = MagicMock()

        # Set 32-character environment variable CRON_SECRET for test
        os.environ["CRON_SECRET"] = "supersecretcronkey_extra_long_32chars"

        response = self.client.post(
            "/cron/reset-monthly",
            headers={"X-Cron-Secret": "supersecretcronkey_extra_long_32chars"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "success")

    def test_cron_reset_monthly_unauthorized(self):
        # Set 32-character environment variable CRON_SECRET for test
        os.environ["CRON_SECRET"] = "supersecretcronkey_extra_long_32chars"
        # Mismatched/missing secret -> 401
        response = self.client.post(
            "/cron/reset-monthly",
            headers={"X-Cron-Secret": "wrongkey"}
        )
        self.assertEqual(response.status_code, 401)

    @patch("routes.auth.get_supabase")
    @patch("routes.meetings.get_supabase")
    def test_delete_meeting_success(self, mock_meetings_supabase, mock_auth_supabase):
        # Mock auth
        mock_auth_db = MagicMock()
        mock_auth_supabase.return_value = mock_auth_db
        mock_user = MagicMock()
        mock_user.id = "11111111-1111-1111-1111-111111111111"
        mock_auth_resp = MagicMock()
        mock_auth_resp.user = mock_user
        mock_auth_db.auth.get_user.return_value = mock_auth_resp

        # Mock profile select for decrement
        mock_auth_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "meetings_used": 2
        }

        # Mock meetings owner check row
        mock_meet_db = MagicMock()
        mock_meetings_supabase.return_value = mock_meet_db
        mock_meet_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "user_id": "11111111-1111-1111-1111-111111111111"
        }

        response = self.client.delete(
            "/meetings/00000000-0000-0000-0000-000000000000",
            headers=self.auth_headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "deleted"})

    @patch("routes.auth.get_supabase")
    @patch("routes.meetings.get_supabase")
    def test_delete_meeting_unauthorized(self, mock_meetings_supabase, mock_auth_supabase):
        # Mock auth
        mock_auth_db = MagicMock()
        mock_auth_supabase.return_value = mock_auth_db
        mock_user = MagicMock()
        mock_user.id = "11111111-1111-1111-1111-111111111111"
        mock_auth_resp = MagicMock()
        mock_auth_resp.user = mock_user
        mock_auth_db.auth.get_user.return_value = mock_auth_resp

        # Mock meetings owner check row (owned by someone else)
        mock_meet_db = MagicMock()
        mock_meetings_supabase.return_value = mock_meet_db
        mock_meet_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
            "user_id": "22222222-2222-2222-2222-222222222222"
        }

        response = self.client.delete(
            "/meetings/00000000-0000-0000-0000-000000000000",
            headers=self.auth_headers
        )
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
