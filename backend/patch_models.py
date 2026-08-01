"""
patch_models.py

Run this from your backend folder:
    python patch_models.py

It automatically adds:
    next_visit_date = models.DateField(null=True, blank=True)
to the FarmVisitReport class in crm_core/models.py — safely, with
a backup and clear before/after confirmation. No manual text editing
needed.
"""

import shutil
import sys

PATH = "crm_core/models.py"
MARKER = "farm_problem = models.TextField(blank=True, null=True)"
ADDITION = "\n\n    # Auto-inserted by patch_models.py\n    next_visit_date = models.DateField(null=True, blank=True)"

def main():
    try:
        with open(PATH, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"ERROR: Could not find {PATH}")
        print("Make sure you're running this command from the 'backend' folder")
        print("(the same folder that has manage.py in it).")
        sys.exit(1)

    if "next_visit_date" in content:
        print("Nothing to do — 'next_visit_date' is already present in models.py.")
        print("If makemigrations still says 'No changes detected', the field")
        print("may be misindented or outside the FarmVisitReport class — paste")
        print("the FarmVisitReport class here so it can be checked.")
        sys.exit(0)

    idx = content.find(MARKER)
    if idx == -1:
        print("ERROR: Could not find the expected line in models.py:")
        print(f"    {MARKER}")
        print()
        print("This means your FarmVisitReport class doesn't match what was")
        print("expected. Paste the full content of crm_core/models.py here")
        print("so the exact insertion point can be found manually.")
        sys.exit(1)

    # Backup first
    backup_path = PATH + ".bak"
    shutil.copyfile(PATH, backup_path)
    print(f"Backup saved to: {backup_path}")

    insert_at = idx + len(MARKER)
    new_content = content[:insert_at] + ADDITION + content[insert_at:]

    with open(PATH, "w", encoding="utf-8") as f:
        f.write(new_content)

    print("SUCCESS: next_visit_date field inserted into FarmVisitReport.")
    print()
    print("Next steps:")
    print("    python manage.py makemigrations")
    print("    python manage.py migrate")
    print("    (then restart your dev server)")

if __name__ == "__main__":
    main()