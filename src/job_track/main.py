"""Main entry point for job-track.

This module provides the main CLI interface for launching the different
components of job-track.
"""

import argparse
import sys


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Job-Track: Local job tracking and application management"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # TUI command
    subparsers.add_parser("tui", help="Launch the TUI interface")

    # API server command
    api_parser = subparsers.add_parser("api", help="Start the API server")
    api_parser.add_argument(
        "--port", type=int, default=8787, help="Port to run the API server on"
    )

    # Scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Scrape job listings")
    scrape_parser.add_argument(
        "urls", nargs="+", help="URLs to scrape for job listings"
    )
    scrape_parser.add_argument(
        "--new-grad", action="store_true", help="Filter for new-grad positions only"
    )

    # Profile commands
    profile_parser = subparsers.add_parser("profile", help="Manage profiles")
    profile_subparsers = profile_parser.add_subparsers(dest="profile_command")
    profile_subparsers.add_parser("list", help="List all profiles")
    add_profile = profile_subparsers.add_parser("add", help="Add a new profile")
    add_profile.add_argument("--profile-name", required=True, help="Name for this profile (e.g., 'Tech Resume')")
    add_profile.add_argument("--first-name", required=True, help="First name")
    add_profile.add_argument("--last-name", required=True, help="Last name")
    add_profile.add_argument("--email", required=True, help="Email address")
    add_profile.add_argument("--phone", help="Phone number")

    args = parser.parse_args()

    if args.command == "tui" or args.command is None:
        from job_track.tui.app import main as tui_main
        tui_main()
    elif args.command == "api":
        from job_track.api.server import run
        run()
    elif args.command == "scrape":
        run_scrape(args.urls, args.new_grad)
    elif args.command == "profile":
        run_profile_command(args)
    else:
        parser.print_help()


def run_scrape(urls: list[str], filter_new_grad: bool):
    """Run the scraper and add jobs to database."""
    from job_track.db.models import Job, get_session, init_db
    from job_track.scraper.scraper import scrape_jobs_sync

    init_db()

    print(f"Scraping {len(urls)} URLs...")
    jobs = scrape_jobs_sync(urls, filter_new_grad=filter_new_grad)

    session = get_session()
    try:
        added = 0
        for scraped_job in jobs:
            # Check if job already exists (by apply_url)
            existing = session.query(Job).filter(
                Job.apply_url == scraped_job.apply_url
            ).first()
            if existing:
                print(f"  Skipped (exists): {scraped_job.title}")
                continue

            job = Job(
                id=scraped_job.generate_id(),
                title=scraped_job.title,
                company=scraped_job.company,
                location=scraped_job.location,
                description=scraped_job.description,
                apply_url=scraped_job.apply_url,
                source_url=scraped_job.source_url,
            )
            job.set_tags(scraped_job.tags)
            session.add(job)
            added += 1
            print(f"  Added: {scraped_job.title} at {scraped_job.company}")

        session.commit()
        print(f"\nAdded {added} new jobs to database.")
    finally:
        session.close()


def run_profile_command(args):
    """Handle profile subcommands."""
    from job_track.db.models import Profile, get_session, init_db

    init_db()
    session = get_session()

    try:
        if args.profile_command == "list":
            profiles = session.query(Profile).all()
            if not profiles:
                print("No profiles found. Add one with: job-track profile add --profile-name 'My Profile' --first-name 'John' --last-name 'Doe' --email 'email@example.com'")
            else:
                print(f"Found {len(profiles)} profile(s):\n")
                for p in profiles:
                    print(f"  ID: {p.id}")
                    print(f"  Profile Name: {p.profile_name}")
                    print(f"  Name: {p.get_full_name()}")
                    print(f"  Email: {p.email}")
                    if p.phone:
                        print(f"  Phone: {p.phone}")
                    versions = p.get_resume_versions()
                    print(f"  Resume versions: {len(versions)}")
                    print()
        elif args.profile_command == "add":
            profile = Profile(
                profile_name=args.profile_name,
                first_name=args.first_name,
                last_name=args.last_name,
                email=args.email,
                phone=args.phone,
            )
            session.add(profile)
            session.commit()
            print(f"Created profile: {profile.profile_name} (ID: {profile.id})")
    finally:
        session.close()


if __name__ == "__main__":
    main()
