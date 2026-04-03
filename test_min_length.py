from api.schemas.api_models import UserCreate
try:
    UserCreate(username="admin", password="password", is_admin=False)
    print("FAILED: Did not raise validation error on short username")
except Exception as e:
    print("SUCCESS: Caught error for short username")

try:
    UserCreate(username="admin_user_long", password="password", is_admin=False)
    print("SUCCESS: Passed validation for long username")
except Exception as e:
    print("FAILED: Raised error on valid username:", e)
