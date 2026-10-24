import pytest
import pytest_asyncio
import os
import fitz
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from backend.app.main import app
from backend.app.database import Base, get_db

TEST_DB_FILE = "./test_scholarlens.db"
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{TEST_DB_FILE}"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(bind=test_engine, class_=AsyncSession, expire_on_commit=False)

@pytest_asyncio.fixture(scope="session", autouse=True)
async def prepare_database():
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except OSError:
            pass

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()
    if os.path.exists(TEST_DB_FILE):
        try:
            os.remove(TEST_DB_FILE)
        except OSError:
            pass

@pytest_asyncio.fixture
async def db_session():
    async with TestingSessionLocal() as session:
        yield session

@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture
def sample_pdf_bytes():
    """Generates a valid 2-page test PDF with PyMuPDF."""
    doc = fitz.open()
    
    # Page 1
    page1 = doc.new_page(width=595, height=842)
    page1.insert_text((50, 72), "Adaptive Cognitive Protocols: Trial Report", fontsize=16)
    page1.insert_text((50, 120), "Primary Objective: Evaluate 12-week adherence to closed-loop cognitive intervention.", fontsize=11)
    page1.insert_text((50, 160), "Methodology: Multicenter double-blind randomized controlled trial with 480 participants.", fontsize=11)
    
    # Page 2
    page2 = doc.new_page(width=595, height=842)
    page2.insert_text((50, 72), "Findings & Results: 92.4% retention in adaptive vs 78.1% in static arm (p < 0.001).", fontsize=11)
    page2.insert_text((50, 120), "Limitations: Authors did not monitor adverse sensory complaints or long-term persistence.", fontsize=11)
    
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
