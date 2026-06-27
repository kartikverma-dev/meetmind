import pytest
import os
import re
import json
import uuid
import asyncio
from unittest.mock import MagicMock, patch
from httpx import AsyncClient

# Mock environment variables BEFORE any imports
os.environ["GEMINI_API_KEY"] = "fake_gemini_key"
os.environ["SUPABASE_URL"] = "https://fake-supabase-url.supabase.co"
os.environ["SUPABASE_SERVICE_KEY"] = "fake_supabase_service_key"
os.environ["MOCK_MODE"] = "False"

# Import app
from main import app
from routes.auth import get_settings

BASE_URL = "https://meetmind-backend-90u7.onrender.com"

TEST_USERS = {
    "normal": {
        "email": "test_normal@meetmind.test",
        "password": "Test@123456"
    },
    "attacker": {
        "email": "attacker@evil.test", 
        "password": "Attack@789"
    }
}

class MockActionItem:
    def __init__(self, task, owner, deadline):
        self.task = task
        self.owner = owner
        self.deadline = deadline

class MockMOM:
    def __init__(self, data):
        self.data = data
        self.action_items = [
            MockActionItem(item["task"], item["owner"], item.get("deadline"))
            for item in data.get("action_items", [])
        ]
    def model_dump(self):
        return self.data

# In-memory mock database store
class MockDbStore:
    def __init__(self):
        self.reset()

    def reset(self):
        self.profiles = []
        self.meetings = []
        self.action_items = []
        self.users = {}  # email -> user_id
        self.failed_logins = []
        self.security_logs = []

MOCK_DB = MockDbStore()

# Mock Supabase Auth classes
class MockUser:
    def __init__(self, user_id, email):
        self.id = user_id
        self.email = email

class MockSession:
    def __init__(self, access_token, refresh_token):
        self.access_token = access_token
        self.refresh_token = refresh_token

class MockAuthResponse:
    def __init__(self, user, session=None):
        self.user = user
        self.session = session

class MockSupabaseAuth:
    def sign_up(self, credentials_dict):
        email = credentials_dict.get("email")
        password = credentials_dict.get("password")
        
        if email in MOCK_DB.users:
            raise Exception("User already registered")
            
        user_id = str(uuid.uuid4())
        MOCK_DB.users[email] = {
            "id": user_id,
            "password": password
        }
        
        # Auto-create profile in Supabase mode
        MOCK_DB.profiles.append({
            "id": user_id,
            "email": email,
            "is_pro": False,
            "pro_until": None,
            "meetings_used": 0,
            "referral_code": "demo1234"
        })
        
        return MockAuthResponse(MockUser(user_id, email))

    def sign_in_with_password(self, credentials_dict):
        email = credentials_dict.get("email")
        password = credentials_dict.get("password")
        
        if email not in MOCK_DB.users or MOCK_DB.users[email]["password"] != password:
            raise Exception("Invalid credentials")
            
        user_id = MOCK_DB.users[email]["id"]
        # Generate a fake JWT (3 parts separated by dots)
        access_token = f"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.{user_id}.signature"
        refresh_token = "fake_refresh_token"
        return MockAuthResponse(MockUser(user_id, email), MockSession(access_token, refresh_token))

    def refresh_session(self, refresh_token):
        if refresh_token != "fake_refresh_token":
            raise Exception("Invalid refresh token")
        user_id = list(MOCK_DB.users.values())[0]["id"] if MOCK_DB.users else str(uuid.uuid4())
        new_access_token = f"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.{user_id}.new_signature"
        return MockAuthResponse(MockUser(user_id, "test@example.com"), MockSession(new_access_token, "fake_refresh_token"))

    def get_user(self, jwt_token):
        if not jwt_token or "." not in jwt_token:
            raise Exception("Invalid token format")
        parts = jwt_token.split(".")
        if len(parts) != 3:
            raise Exception("Invalid token structure")
        user_id = parts[1]
        
        email = next((e for e, u in MOCK_DB.users.items() if u["id"] == user_id), None)
        if not email:
            raise Exception("User not found or invalid session token")
            
        return MockAuthResponse(MockUser(user_id, email))

    def sign_out(self):
        return None

# Mock Supabase Query classes
class MockExecute:
    def __init__(self, result):
        self.data = result.data

class MockTableQuery:
    def __init__(self, table_name, filters=None, updates=None):
        self.table_name = table_name
        self.filters = filters or []
        self.updates = updates or {}
        self.order_by = None
        self.or_filter = None

    def select(self, *args, **kwargs):
        return self

    def insert(self, data):
        table = getattr(MOCK_DB, self.table_name)
        import datetime
        if isinstance(data, list):
            for row in data:
                if "id" not in row:
                    row["id"] = str(uuid.uuid4())
                if self.table_name == "failed_logins" and "attempted_at" not in row:
                    row["attempted_at"] = datetime.datetime.now().isoformat()
                table.append(row)
            ret_data = data
        else:
            if "id" not in data:
                data["id"] = str(uuid.uuid4())
            if self.table_name == "failed_logins" and "attempted_at" not in data:
                data["attempted_at"] = datetime.datetime.now().isoformat()
            table.append(data)
            ret_data = [data]
        self.inserted_data = ret_data
        return self

    def update(self, data):
        self.updates.update(data)
        return self

    def delete(self):
        self.is_delete = True
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def gte(self, column, value):
        self.filters.append((column, value, "gte"))
        return self

    def or_(self, query_string):
        self.or_filter = query_string
        return self

    def order(self, column, desc=False):
        self.order_by = (column, desc)
        return self

    def maybe_single(self):
        self.is_single = True
        return self

    def execute(self):
        if hasattr(self, "inserted_data"):
            class Result:
                def __init__(self, d):
                    self.data = d
            return Result(self.inserted_data)

        rows = getattr(MOCK_DB, self.table_name)
        matched_rows = []
        for row in rows:
            match = True
            for filter_item in self.filters:
                if len(filter_item) == 3:
                    col, val, op = filter_item
                    if op == "gte":
                        if col not in row or row[col] < val:
                            match = False
                            break
                else:
                    col, val = filter_item
                    if col not in row or str(row[col]) != str(val):
                        match = False
                        break
            if match:
                matched_rows.append(row)

        if hasattr(self, "is_delete") and self.is_delete:
            remaining = [r for r in rows if r not in matched_rows]
            setattr(MOCK_DB, self.table_name, remaining)
            
            # Cascade deletes from meetings to action_items
            if self.table_name == "meetings":
                for m in matched_rows:
                    m_id = str(m.get("id"))
                    MOCK_DB.action_items = [
                        ai for ai in MOCK_DB.action_items
                        if str(ai.get("meeting_id")) != m_id
                    ]
            
            class Result:
                def __init__(self, d):
                    self.data = d
            return Result(matched_rows)

        if self.updates:
            for row in matched_rows:
                row.update(self.updates)
            class Result:
                def __init__(self, d):
                    self.data = d
            return Result(matched_rows)

        if self.or_filter:
            parts = self.or_filter.split(",")
            search_query = ""
            for part in parts:
                if ".ilike.%" in part:
                    search_query = part.split(".ilike.%")[1].rstrip("%")
                    break
            
            final_rows = []
            for row in matched_rows:
                title_val = str(row.get("title", "")).lower()
                transcript_val = str(row.get("transcript", "")).lower()
                if search_query.lower() in title_val or search_query.lower() in transcript_val:
                    final_rows.append(row)
            matched_rows = final_rows

        if self.order_by:
            col, desc = self.order_by
            matched_rows.sort(key=lambda r: r.get(col, ""), reverse=desc)

        # Mock joins on meetings for action_items
        if self.table_name == "action_items":
            for row in matched_rows:
                m_id = row.get("meeting_id")
                meet = next((m for m in MOCK_DB.meetings if str(m.get("id")) == str(m_id)), None)
                row["meetings"] = {"title": meet.get("title", "Untitled") if meet else "Untitled"}

        class Result:
            def __init__(self, d):
                self.data = d

        if hasattr(self, "is_single") and self.is_single:
            ret = matched_rows[0] if matched_rows else None
            return Result(ret)

        return Result(matched_rows)

class MockSupabaseClient:
    def __init__(self):
        self.auth = MockSupabaseAuth()

    def table(self, table_name):
        return MockTableQuery(table_name)

def mock_get_supabase():
    return MockSupabaseClient()

# Global patches
@pytest.fixture(autouse=True)
def setup_global_mocks():
    MOCK_DB.reset()
    
    # Disable rate limits by default in all tests
    app.state.limiter.enabled = False
    
    # Supabase connection mocks
    patch_sb1 = patch("services.supabase_client.get_supabase", mock_get_supabase)
    patch_sb2 = patch("routes.auth.get_supabase", mock_get_supabase)
    patch_sb3 = patch("routes.meetings.get_supabase", mock_get_supabase)
    patch_sb4 = patch("routes.action_items.get_supabase", mock_get_supabase)
    patch_sb5 = patch("routes.share.get_supabase", mock_get_supabase)
    patch_sb6 = patch("routes.qa.get_supabase", mock_get_supabase)
    patch_sb7 = patch("routes.stats.get_supabase", mock_get_supabase)
    patch_sb8 = patch("middleware.security.get_supabase", mock_get_supabase)
    
    # Whisper and Gemini API mocks
    patch_transcribe = patch("routes.meetings.transcribe_audio", return_value="Mocked meeting transcript content.")
    patch_process = patch("routes.meetings.process_transcript", return_value=(
        MockMOM({
            "attendees": ["Alice", "Bob"],
            "date": "2026-06-27",
            "agenda": ["Sprint Planning", "Feature Review"],
            "decisions": ["Approved V2 designs", "Set launch date for Monday"],
            "action_items": [
                {"task": "Write test cases", "owner": "Bob", "deadline": "Jun 29, 2026", "status": "pending"},
                {"task": "Ship summary module", "owner": "Alice", "deadline": "Jun 30, 2026", "status": "pending"}
            ]
        }),
        "📌 Mocked executive summary bullet point.\n📌 Second meeting summary note."
    ))
    
    # Mock subprocess duration probe
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = '{"format": {"duration": "120.0"}}'
    patch_sub = patch("routes.meetings.subprocess.run", return_value=mock_proc)
    
    async def mock_answer_question(transcript, question):
        if "script" in question.lower():
            return f"Answer reflecting the script query: {question}"
        return "This is a mocked answer to your question about the meeting."
    patch_qa = patch("routes.qa.answer_question", side_effect=mock_answer_question)

    with patch_sb1, patch_sb2, patch_sb3, patch_sb4, patch_sb5, patch_sb6, patch_sb7, patch_sb8, \
         patch_transcribe, patch_process, patch_sub, patch_qa:
        yield

import httpx
import pytest_asyncio

@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=True)
    async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as c:
        original_request = c.request
        async def request_wrapper(method, url, *args, **kwargs):
            if method in ["POST", "PUT", "PATCH", "DELETE"]:
                headers = kwargs.get("headers")
                if headers is None:
                    headers = {}
                else:
                    headers = dict(headers)
                
                if "X-CSRF-Token" not in headers:
                    csrf_val = "test_csrf_token_123"
                    headers["X-CSRF-Token"] = csrf_val
                    cookies = kwargs.get("cookies")
                    if cookies is None:
                        cookies = {}
                    else:
                        cookies = dict(cookies)
                    cookies["csrf_token"] = csrf_val
                    kwargs["cookies"] = cookies
                kwargs["headers"] = headers
            return await original_request(method, url, *args, **kwargs)
        c.request = request_wrapper
        yield c
