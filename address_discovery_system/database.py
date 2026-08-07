"""Database initialization and management"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from pathlib import Path

from address_discovery_system.models import Base, Loan

# Database configuration
DB_DIR = Path(__file__).parent.parent / 'data'
DB_PATH = DB_DIR / 'loans.db'

# Ensure data directory exists
DB_DIR.mkdir(exist_ok=True)

# Create database engine
DATABASE_URL = f"sqlite:///{DB_PATH}"
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    echo=False  # Set to True for SQL logging
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize database - create all tables"""
    Base.metadata.create_all(bind=engine)
    print(f"✓ Database initialized at {DB_PATH}")


def get_session() -> Session:
    """Get a new database session"""
    return SessionLocal()


def load_loans_into_db(loans, state_filter=None):
    """Load loans from data source into database.

    Args:
        loans: List of loan objects from load_loans()
        state_filter: Optional set of states to filter by (e.g., {'TX', 'FL', 'GA'})

    Returns:
        Count of loans loaded
    """
    from address_discovery_system.dashboard_filter import DASHBOARD_STATES

    session = get_session()
    loaded = 0

    try:
        for loan in loans:
            # Skip portfolio properties (removed from database entirely)
            if 'portfolio' in (loan.property_name or "").lower():
                continue

            # Optional state filter
            if state_filter and loan.state not in state_filter:
                continue

            # Skip if already in database
            existing = session.query(Loan).filter(
                Loan.property_name == loan.property_name,
                Loan.city == loan.city,
                Loan.state == loan.state
            ).first()

            if existing:
                continue

            # Create new loan record
            db_loan = Loan(
                property_name=loan.property_name,
                city=loan.city,
                state=loan.state,
                county=getattr(loan, 'county', None),
                property_address=getattr(loan, 'property_address', None),
                units=getattr(loan, 'units', None),
                original_balance=getattr(loan, 'original_balance', None),
                current_balance=getattr(loan, 'current_balance', None),
                property_type=getattr(loan, 'property_type', None),
                program=getattr(loan, 'program', None),
                deal=getattr(loan, 'deal', None),
                loan_id=getattr(loan, 'loan_id', None),
                address_source='raw_data' if loan.property_address else None,
                address_confidence=1.0 if loan.property_address else None,
            )
            session.add(db_loan)
            loaded += 1

        session.commit()
        print(f"✓ Loaded {loaded} loans into database")
        return loaded

    except Exception as e:
        session.rollback()
        print(f"✗ Error loading loans: {e}")
        raise
    finally:
        session.close()


def get_loan_count(session: Session, state_filter=None) -> int:
    """Get total loan count, optionally filtered by state"""
    query = session.query(Loan)
    if state_filter:
        query = query.filter(Loan.state.in_(state_filter))
    return query.count()


def get_loans_without_addresses(session: Session, state_filter=None) -> list:
    """Get all loans without addresses"""
    query = session.query(Loan).filter(Loan.property_address.is_(None))
    if state_filter:
        query = query.filter(Loan.state.in_(state_filter))
    return query.all()


def get_address_coverage(session: Session, state_filter=None) -> dict:
    """Get address coverage statistics"""
    total_query = session.query(Loan)
    with_address_query = session.query(Loan).filter(Loan.property_address.isnot(None))

    if state_filter:
        total_query = total_query.filter(Loan.state.in_(state_filter))
        with_address_query = with_address_query.filter(Loan.state.in_(state_filter))

    total = total_query.count()
    with_address = with_address_query.count()
    without_address = total - with_address

    return {
        'total': total,
        'with_address': with_address,
        'without_address': without_address,
        'coverage_pct': (with_address / total * 100) if total > 0 else 0,
    }


def update_loan_address(session: Session, loan_id: int, address: str, source: str, confidence: float = 0.85):
    """Update loan address from discovery

    Args:
        session: Database session
        loan_id: Loan database ID
        address: Discovered address
        source: Where address came from ('google_maps', 'county_assessor', etc.)
        confidence: Confidence score (0.0 - 1.0)
    """
    from datetime import datetime

    loan = session.query(Loan).filter(Loan.id == loan_id).first()
    if not loan:
        return False

    loan.property_address = address
    loan.address_source = source
    loan.address_confidence = confidence
    loan.address_last_updated = datetime.utcnow()

    session.commit()
    return True


def get_loans_by_state(session: Session, state: str) -> list:
    """Get all loans for a specific state"""
    return session.query(Loan).filter(Loan.state == state).all()


def search_loans(session: Session, property_name: str = None, city: str = None, state: str = None) -> list:
    """Search for loans by criteria"""
    query = session.query(Loan)

    if property_name:
        query = query.filter(Loan.property_name.ilike(f"%{property_name}%"))
    if city:
        query = query.filter(Loan.city.ilike(f"%{city}%"))
    if state:
        query = query.filter(Loan.state == state)

    return query.all()
