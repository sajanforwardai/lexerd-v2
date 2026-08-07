#!/usr/bin/env python3
"""Add navigation tabs to all state lookup tools"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

STATES = ['AL', 'FL', 'GA', 'KS', 'KY', 'LA', 'NC', 'TX']

def add_navigation_to_state_html(state: str):
    """Add navigation tabs to a state's HTML file"""

    html_file = Path(f"{state.lower()}_property_lookup.html")

    if not html_file.exists():
        print(f"  ✗ {html_file} not found")
        return

    with open(html_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Create navigation HTML
    nav_html = f'''        <!-- Navigation tabs -->
        <div class="nav-tabs">
            <a href="about.html">📖 Guide</a>
'''

    # Add state buttons (highlight current state)
    for s in STATES:
        if s == state:
            nav_html += f'            <span class="active">{s}</span>\n'
        else:
            nav_html += f'            <a href="{s.lower()}_property_lookup.html">{s}</a>\n'

    nav_html += '        </div>\n'

    # Add nav-tabs styles if not present
    if '.nav-tabs' not in content:
        style_injection = '''        .nav-tabs { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
        .nav-tabs a, .nav-tabs span {
            display: inline-block;
            padding: 10px 16px;
            background: white;
            border-radius: 6px 6px 0 0;
            text-decoration: none;
            color: #666;
            font-size: 13px;
            font-weight: 500;
            border: 1px solid #ddd;
            border-bottom: none;
            transition: all 0.2s;
        }
        .nav-tabs a:hover { color: #2563eb; background: #f9fafb; }
        .nav-tabs .active { background: #2563eb; color: white; border-color: #2563eb; }
        '''

        # Inject styles after the instruction-box style
        content = content.replace(
            '.footer { margin-top: 30px;',
            style_injection + '        .footer { margin-top: 30px;'
        )

    # Inject navigation after the opening container div
    content = content.replace(
        '<div class="container">',
        f'<div class="container">\n{nav_html}'
    )

    with open(html_file, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"  ✓ {html_file} updated")


def main():
    """Add navigation to all state tools"""

    print("════════════════════════════════════════════════════════════════════")
    print("ADD NAVIGATION TABS TO ALL STATE LOOKUP TOOLS")
    print("════════════════════════════════════════════════════════════════════\n")

    print("Updating state HTML files with navigation...\n")

    for state in STATES:
        add_navigation_to_state_html(state)

    print("\n" + "════════════════════════════════════════════════════════════════════")
    print("✅ NAVIGATION ADDED TO ALL TOOLS")
    print("════════════════════════════════════════════════════════════════════\n")

    print("Changes made:")
    print("  ✓ Added navigation tabs to all 8 state lookup pages")
    print("  ✓ Each state now has: Guide link + links to all 7 other states")
    print("  ✓ Current state is highlighted in navigation")
    print("  ✓ Start at about.html to see the guide and overview\n")

    print("Navigation structure:")
    print("  about.html → Guide + Overview + Quick access to all states")
    print("  al_property_lookup.html → AL properties + links to other states")
    print("  fl_property_lookup.html → FL properties + links to other states")
    print("  ... (same for GA, KS, KY, LA, NC, TX)\n")


if __name__ == "__main__":
    main()
