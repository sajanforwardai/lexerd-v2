"""Website discovery models - parallels address discovery"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()


class Website(Base):
    """Property website information"""
    __tablename__ = 'websites'

    id = Column(Integer, primary_key=True)
    loan_id = Column(Integer, ForeignKey('loans.id'), nullable=False, index=True)

    # Website info
    website_url = Column(String(500))
    website_type = Column(String(100))  # official, management, listing, apartments.com, zillow, etc.
    website_source = Column(String(100))  # google_search, apartments.com, zillow, manual_verification
    website_confidence = Column(Float, default=0.0)  # 0.0-1.0

    # Contact info from website
    phone_number = Column(String(20))
    email_address = Column(String(255))
    management_company = Column(String(255))

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Website(id={self.id}, loan_id={self.loan_id}, url={self.website_url}, type={self.website_type})>"


class WebsiteDiscovery(Base):
    """Website discovery audit log - tracks all discovery attempts"""
    __tablename__ = 'website_discoveries'

    id = Column(Integer, primary_key=True)
    loan_id = Column(Integer, ForeignKey('loans.id'), nullable=False, index=True)

    # Discovery info
    discovered_url = Column(String(500))
    discovery_source = Column(String(100))  # google_search, apartments.com, zillow, manual, etc.
    discovery_type = Column(String(100))  # official, management, listing
    confidence = Column(Float, default=0.0)

    # Contact info found
    phone_discovered = Column(String(20))
    email_discovered = Column(String(255))
    management_company_discovered = Column(String(255))

    # Acceptance
    accepted = Column(Boolean, default=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<WebsiteDiscovery(id={self.id}, loan_id={self.loan_id}, url={self.discovered_url})>"
