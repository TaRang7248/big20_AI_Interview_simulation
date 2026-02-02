import asyncio
import logging
from datetime import timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from IMH.common.time import utc_now
from IMH.core.exceptions import AuthenticationError, IMHError
from IMH.core.logging_config import setup_logging
from IMH.core.request_id import RequestIdMiddleware, _request_id_ctx_var
from IMH.db.session import AsyncSessionLocal
from IMH.models.user import User

logger = logging.getLogger("IMH.test")

async def test_datetime():
    print("--- Testing Datetime ---")
    now = utc_now()
    print(f"utc_now(): {now} (tzinfo: {now.tzinfo})")
    assert now.tzinfo is not None
    assert now.tzinfo == timezone.utc
    print("✅ Datetime test passed")

async def test_exceptions():
    print("\n--- Testing Exceptions ---")
    try:
        raise AuthenticationError(message="Test Auth Error")
    except IMHError as e:
        print(f"Caught IMHError: {e.code} - {e.message} (Status: {e.status_code})")
        assert e.code == "AUTH_INVALID_CREDENTIALS"
        assert e.status_code == 401
    print("✅ Exceptions test passed")

async def test_logging_and_request_id():
    print("\n--- Testing Logging and Request ID ---")
    setup_logging()
    
    # Simulate middleware setting request_id
    token = _request_id_ctx_var.set("TEST-REQUEST-ID-123")
    try:
        logger.info("This is a test log message with request_id")
        print("Check terminal output for '[TEST-REQUEST-ID-123]' in the log line.")
    finally:
        _request_id_ctx_var.reset(token)
    print("✅ Logging test complete (manual verification of output recommended)")

async def main():
    await test_datetime()
    await test_exceptions()
    await test_logging_and_request_id()

if __name__ == "__main__":
    asyncio.run(main())
