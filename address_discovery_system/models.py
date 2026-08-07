"""SQLAlchemy ORM Models for Loans and Addresses"""

from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Loan(Base):
    """Loan model - stores all loan data with addresses"""

    __tablename__ = 'loans'

    # Primary key
    id = Column(Integer, primary_key=True)

    # Core loan identifiers
    property_name = Column(String(255), nullable=False, index=True)
    city = Column(String(100), nullable=True)
    state = Column(String(2), nullable=False, index=True)
    county = Column(String(100), nullable=True)

    # Address (dynamic - updated by discovery)
    property_address = Column(String(500), nullable=True, index=True)
    zip_code = Column(String(10), nullable=True)

    # Property details
    units = Column(Integer, nullable=True)
    original_balance = Column(Float, nullable=True)
    current_balance = Column(Float, nullable=True)

    # Loan details
    property_type = Column(String(50), nullable=True)
    program = Column(String(100), nullable=True)
    deal = Column(String(100), nullable=True)
    loan_id = Column(String(50), nullable=True, unique=True)

    # Address discovery tracking
    address_source = Column(String(100), nullable=True)  # 'raw', 'google_maps', 'county_assessor', etc.
    address_confidence = Column(Float, nullable=True)  # 0.0 - 1.0
    address_last_updated = Column(DateTime, nullable=True)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    discoveries = relationship('Discovery', back_populates='loan')

    # Indexes for common queries
    __table_args__ = (
        Index('ix_loan_state_has_address', 'state', 'property_address'),
        Index('ix_loan_property_city_state', 'property_name', 'city', 'state'),
    )

    def has_address(self):
        """Check if loan has an address"""
        return bool(self.property_address and self.property_address.strip())

    def __repr__(self):
        return f"<Loan {self.property_name} ({self.city}, {self.state})>"


class Discovery(Base):
    """Address Discovery History - tracks all discovery attempts"""

    __tablename__ = 'discoveries'

    id = Column(Integer, primary_key=True)
    loan_id = Column(Integer, ForeignKey('loans.id'), nullable=False, index=True)

    # Discovery details
    discovered_address = Column(String(500), nullable=True)
    source = Column(String(100), nullable=False)  # 'google_maps', 'county_assessor', etc.
    confidence = Column(Float, nullable=True)  # 0.0 - 1.0

    # Metadata
    discovered_at = Column(DateTime, default=datetime.utcnow)
    accepted = Column(Integer, default=0)  # 1 if this discovery was accepted, 0 otherwise

    # Relationship
    loan = relationship('Loan', back_populates='discoveries')

    def __repr__(self):
        return f"<Discovery {self.source}: {self.discovered_address}>"
