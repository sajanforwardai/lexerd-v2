"""Database operations for website discovery"""

import sys
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path.cwd()))

from address_discovery_system.website_model import Base, Website, WebsiteDiscovery
from address_discovery_system.models import Loan


DATABASE_URL = "sqlite:///data/loans.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_website_tables():
    """Initialize website tables"""
    Base.metadata.create_all(bind=engine)


def get_website_session():
    """Get database session"""
    return SessionLocal()


def update_loan_website(
    session,
    loan_id: int,
    website_url: str,
    website_type: str = "official",
    source: str = "manual_verification",
    confidence: float = 1.0,
    phone: str = None,
    email: str = None,
    management_company: str = None
):
    """Update loan with discovered website"""

    loan = session.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        raise ValueError(f"Loan {loan_id} not found")

    # Check if website already exists
    existing = session.query(Website).filter(
        Website.loan_id == loan_id,
        Website.website_url == website_url
    ).first()

    if existing:
        existing.website_type = website_type
        existing.website_source = source
        existing.website_confidence = confidence
        existing.phone_number = phone
        existing.email_address = email
        existing.management_company = management_company
    else:
        website = Website(
            loan_id=loan_id,
            website_url=website_url,
            website_type=website_type,
            website_source=source,
            website_confidence=confidence,
            phone_number=phone,
            email_address=email,
            management_company=management_company
        )
        session.add(website)

    session.commit()


def search_loans_for_websites(session, property_name: str = None, city: str = None, state: str = None):
    """Find loans without websites"""

    query = session.query(Loan)

    if property_name:
        query = query.filter(Loan.property_name.ilike(f"%{property_name}%"))
    if city:
        query = query.filter(Loan.city.ilike(f"%{city}%"))
    if state:
        query = query.filter(Loan.state == state)

    return query.all()


def get_loans_without_websites(session, state: str = None) -> list:
    """Get all loans without websites"""

    query = session.query(Loan).outerjoin(Website).filter(Website.id.is_(None))

    if state:
        query = query.filter(Loan.state == state)

    return query.all()


def log_website_discovery(
    session,
    loan_id: int,
    discovered_url: str,
    discovery_source: str,
    discovery_type: str = "official",
    confidence: float = 0.8,
    phone: str = None,
    email: str = None,
    management_company: str = None,
    accepted: bool = False
):
    """Log website discovery attempt"""

    discovery = WebsiteDiscovery(
        loan_id=loan_id,
        discovered_url=discovered_url,
        discovery_source=discovery_source,
        discovery_type=discovery_type,
        confidence=confidence,
        phone_discovered=phone,
        email_discovered=email,
        management_company_discovered=management_company,
        accepted=accepted
    )
    session.add(discovery)
    session.commit()

    return discovery
