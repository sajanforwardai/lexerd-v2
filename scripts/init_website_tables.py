#!/usr/bin/env python3
"""Initialize website tables in database"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

from address_discovery_system.website_database import init_website_tables


def main():
    """Initialize tables"""
    print("════════════════════════════════════════════════════════════════════")
    print("INITIALIZE WEBSITE TABLES")
    print("════════════════════════════════════════════════════════════════════\n")

    print("Creating website tables...")
    init_website_tables()
    print("✅ Tables created successfully!\n")

    print("Tables initialized:")
    print("  • websites (website information)")
    print("  • website_discoveries (discovery audit log)\n")


if __name__ == "__main__":
    main()
