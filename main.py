#!/usr/bin/env python3
"""
Workana Job Scraping Bot
Detects new job postings from Workana and displays them in the console
"""

import requests
from bs4 import BeautifulSoup
import time
import json
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
from colorama import init, Fore, Style
import re
from html import unescape
from discord_webhook import DiscordWebhook, DiscordEmbed

# Initialize colorama for colored console output
init()

class WorkanaScraper:
    def __init__(self):
        self.seen_jobs_file = "seen_jobs.dat"
        self.seen_jobs = self.load_seen_jobs()
        
        # Discord webhook URLs per category, loaded from the environment so secrets
        # never live in source. Set DISCORD_WEBHOOK_IT_PROGRAMMING in .env.
        self.webhook_urls = {
            'it-programming': os.environ.get("DISCORD_WEBHOOK_IT_PROGRAMMING", "").strip(),
        }
        # User ID to mention in Discord (set JUPITER_DISCORD_ID in .env for ping); use numeric Discord ID
        self.mention_user_id = os.environ.get("JUPITER_DISCORD_ID", "").strip()
        
    def load_seen_jobs(self):
        """Load previously seen job data from file"""
        if os.path.exists(self.seen_jobs_file):
            try:
                with open(self.seen_jobs_file, 'r', encoding='utf-8') as f:
                    data = [str(line.strip()) for line in f]
                    return data
            except OSError:
                return []
        return []
    
    SEEN_JOBS_MAX = 50

    def save_seen_jobs(self, new_urls):
        """Merge new job URLs into seen list, keep only the 50 most recent, and persist."""
        combined = [u for u in self.seen_jobs if u] + [u for u in new_urls if u]
        seen_ordered = []
        seen_set = set()
        for u in reversed(combined):
            if u not in seen_set:
                seen_set.add(u)
                seen_ordered.append(u)
        seen_ordered.reverse()
        self.seen_jobs = seen_ordered[-self.SEEN_JOBS_MAX:]
        with open(self.seen_jobs_file, "w", encoding="utf-8") as f:
            f.write("\n".join(self.seen_jobs))

    def _text_from_html(self, html_str):
        """Strip HTML tags and decode entities from a string."""
        if not html_str:
            return ""
        # Decode JSON Unicode escapes then strip tags
        text = unescape(html_str)
        text = re.sub(r"<[^>]+>", " ", text)
        return " ".join(text.split()).strip()

    def _posted_date_to_exact(self, posted_date_str):
        """
        Convert Spanish relative postedDate (e.g. 'Hace 8 horas') to exact datetime.
        Returns formatted string like '2025-03-15 14:30' or original string if unparseable.
        """
        if not posted_date_str or not posted_date_str.strip():
            return posted_date_str or ""
        now = datetime.now()
        s = posted_date_str.strip().lower()
        try:
            if "instantes" in s:
                dt = now - timedelta(minutes=0)
            elif "casi una hora" in s:
                dt = now - timedelta(minutes=50)
            elif "minutos" in s:
                m = re.search(r"hace\s+(\d+)\s*minutos?", s, re.I)
                dt = now - timedelta(minutes=int(m.group(1))) if m else now - timedelta(minutes=5)
            elif "hora" in s and "horas" not in s:
                # "Hace una hora", "Hace 1 hora"
                dt = now - timedelta(hours=1)
            elif "horas" in s:
                m = re.search(r"hace\s+(\d+)\s*horas?", s, re.I)
                dt = now - timedelta(hours=int(m.group(1))) if m else now - timedelta(hours=1)
            elif "ayer" in s:
                dt = now - timedelta(days=1)
            elif "días" in s or "dias" in s:
                m = re.search(r"hace\s+(\d+)\s*d[ií]as?", s, re.I)
                dt = now - timedelta(days=int(m.group(1))) if m else now - timedelta(days=1)
            else:
                return posted_date_str
            return dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return posted_date_str

    def get_project_list_from_soup(self, soup):
        """
        Extract project list from the search component's :results-initials JSON.
        Returns list of dicts with: slug, title, description, budget, postedDate,
        authorName, skills, totalBids, job_url, etc.
        """
        projects = []
        # Find <search> or any element with :results-initials
        for tag in soup.find_all(True):
            raw = None
            for attr_name, attr_value in tag.attrs.items():
                if "results-initials" in attr_name and isinstance(attr_value, str):
                    raw = attr_value
                    break
            if raw is None:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            results = data.get("results") or []
            base_job_url = "https://www.workana.com/job"
            for r in results:
                slug = r.get("slug") or ""
                job_url = f"{base_job_url}/{slug}" if slug else ""
                title_html = r.get("title") or ""
                desc_html = r.get("description") or ""
                skills_list = r.get("skills") or []
                skill_names = [s.get("anchorText") or s.get("title", "") for s in skills_list if isinstance(s, dict)]
                projects.append({
                    "slug": slug,
                    "title": self._text_from_html(title_html),
                    "title_html": title_html,
                    "description": self._text_from_html(desc_html),
                    "description_html": desc_html,
                    "budget": r.get("budget") or "",
                    "postedDate": r.get("postedDate") or "",
                    "publishedDate": r.get("publishedDate") or "",
                    "authorName": r.get("authorName") or "",
                    "totalBids": r.get("totalBids") or "",
                    "country": self._text_from_html(r.get("country") or ""),
                    "isHourly": r.get("isHourly") or False,
                    "skills": skill_names,
                    "job_url": job_url,
                })
            break
        return projects

    def _parse_bid_count(self, total_bids_str):
        """Extract numeric bid count from e.g. 'Propuestas: 14' -> 14."""
        if not total_bids_str:
            return 0
        m = re.search(r"(\d+)", total_bids_str)
        return int(m.group(1)) if m else 0

    def _posted_within_one_hour(self, posted_date_str):
        """True if postedDate indicates 1 hour or less (Spanish labels)."""
        if not posted_date_str:
            return False
        s = posted_date_str.strip().lower()
        # "Hace instantes", "Hace X minutos", "Hace casi una hora", "Hace una hora", "Hace 1 hora"
        if "instantes" in s or "casi una hora" in s or "una hora" in s:
            return True
        if "hace" in s and "minutos" in s:
            m = re.search(r"hace\s+(\d+)\s*minutos?", s, re.I)
            if m:
                return int(m.group(1)) <= 60
            return True  # "Hace unos minutos" etc.
        if "hace" in s and "hora" in s and "horas" not in s:
            return True  # "Hace 1 hora" (singular)
        if re.match(r"hace\s+1\s*hora", s):
            return True
        return False

    def filter_fresh_low_competition(self, projects, max_bids=10):
        """Keep only projects posted ≤1 hour ago and with ≤ max_bids bids."""
        return [
            p for p in projects
            if self._posted_within_one_hour(p.get("postedDate") or "")
            and self._parse_bid_count(p.get("totalBids") or "") <= max_bids
        ]
    
    def send_discord_notification(self, job):
        """Send job posting to Discord channel based on category"""
        try:
            category = job.get("category", "it-programming")
            webhook_url = self.webhook_urls.get(category)
            if not webhook_url:
                print(f"{Fore.YELLOW}[!] No webhook URL for category: {category}{Style.RESET_ALL}")
                return False

            title = (job.get("title") or "")[:256]
            # desc = (job.get("description") or "")[:100]
            # if len(job.get("description") or "") > 100:
                # desc += "..."

            embed = DiscordEmbed(
                title=title or "Workana Job",
                # description=desc,
                color=0x00ff00,
                url=job.get("job_url", ""),
            )
            embed.add_embed_field(name="Author", value=(job.get("authorName") or "")[:1024], inline=True)
            embed.add_embed_field(name="Budget", value=(job.get("budget") or "")[:1024], inline=True)
            embed.add_embed_field(name="Posted", value=(job.get("postedDate") or "")[:1024], inline=True)
            embed.add_embed_field(name="Bids", value=(job.get("totalBids") or "")[:1024], inline=True)
            embed.add_embed_field(name="Country", value=(job.get("country") or "-")[:1024], inline=True)
            skills = ", ".join((job.get("skills") or [])[:10])
            embed.add_embed_field(name="Skills", value=skills[:1024] or "-", inline=False)
            embed.set_footer(text="Workana Job Bot")

            webhook = DiscordWebhook(url=webhook_url, username="Workana Bot")
            if self.mention_user_id:
                webhook.content = f"<@{self.mention_user_id}>"
            webhook.add_embed(embed)
            response = webhook.execute()

            if response.status_code in (200, 204):
                print(f"{Fore.GREEN}[OK] Posted to Discord: {job.get('job_url', '')}{Style.RESET_ALL}")
                return True
            print(f"{Fore.RED}[X] Discord failed: {response.status_code}{Style.RESET_ALL}")
            return False
        except Exception as e:
            print(f"{Fore.RED}[X] Discord error: {e}{Style.RESET_ALL}")
            return False

    def scrape_jobs(self):
        """Scrape job postings from Workana across all configured categories."""
        try:
            base_urls = [
                { 'category': "it-programming", 'url': "https://www.workana.com/jobs?sort=new&category=it-programming&language=xx" }
            ]
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            })

            seen_set = set(self.seen_jobs)
            all_jobs = []

            for base_url in base_urls:
                print(f"{Fore.CYAN}Target URL: {base_url['url']}{Style.RESET_ALL}")

                response = session.get(base_url['url'], timeout=15)
                response.raise_for_status()

                soup = BeautifulSoup(response.content, 'html.parser')
                # Optional: save HTML for debugging
                # with open("temp.html", "w", encoding="utf-8") as f:
                #     f.write(soup.prettify())
                jobs = self.get_project_list_from_soup(soup)
                if jobs:
                    print(f"{Fore.GREEN}Found {len(jobs)} projects on page{Style.RESET_ALL}")
                jobs = self.filter_fresh_low_competition(jobs, max_bids=10)
                if jobs:
                    print(f"{Fore.GREEN}  -> {len(jobs)} posted <=1h ago with <=10 bids{Style.RESET_ALL}")
                jobs = [j for j in jobs if (j.get("job_url") or "") not in seen_set]
                for j in jobs:
                    j["category"] = base_url.get("category", "it-programming")
                    j["postedDate"] = self._posted_date_to_exact(j.get("postedDate") or "")
                all_jobs.extend(jobs)

            all_jobs.sort(key=lambda p: p.get("postedDate") or "")
            return all_jobs

        except requests.RequestException as e:
            print(f"{Fore.RED}❌ Network error: {e}{Style.RESET_ALL}")
            return []
        except Exception as e:
            print(f"{Fore.RED}❌ Scraping error: {e}{Style.RESET_ALL}")
            return []

    def display_jobs(self, jobs, discord_mode=False):
        """Display jobs in console, optionally send each to Discord."""
        if not jobs:
            print(f"{Fore.YELLOW}No new job postings found.{Style.RESET_ALL}")
            return
        new_jobs = []
        for i, p in enumerate(jobs, 1):
            print(f"{Fore.CYAN}[{i}] {p.get('title', '')[:70]}{'...' if len(p.get('title','')) > 70 else ''}{Style.RESET_ALL}")
            print(f"    {p.get('budget','')} | {p.get('postedDate','')} | {p.get('totalBids','')}")
            print(f"    {p.get('job_url','')}")
            if p.get("skills"):
                print(f"    Skills: {', '.join(p['skills'][:8])}")
            print()
            new_jobs.append(p.get("job_url", ""))
            if discord_mode:
                self.send_discord_notification(p)
        self.save_seen_jobs(new_jobs)
        print(f"{Fore.GREEN}Found {len(new_jobs)} job(s).{' Sent to Discord.' if discord_mode else ''}{Style.RESET_ALL}\n")

    def run(self, continuous=False, interval=2, discord_mode=False):
        """Run the scraper"""
        print(f"{Fore.CYAN}Workana Job Scraping Bot Started{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Continuous mode: {'ON' if continuous else 'OFF'}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}Discord mode: {'ON' if discord_mode else 'OFF'}{Style.RESET_ALL}")
        
        if continuous:
            print(f"{Fore.CYAN}Checking every {interval} seconds...{Style.RESET_ALL}")
            if discord_mode:
                print(f"{Fore.GREEN}New jobs will be posted to Discord channels by category{Style.RESET_ALL}")
            print(f"{Fore.YELLOW}Press Ctrl+C to stop{Style.RESET_ALL}\n")
        try:
            while True:
                jobs = self.scrape_jobs()
                self.display_jobs(jobs, discord_mode=discord_mode)
                
                if not continuous:
                    break
                
                print(f"\n{Fore.CYAN}Waiting {interval} seconds before next check...{Style.RESET_ALL}")
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print(f"\n{Fore.YELLOW}👋 Bot stopped by user{Style.RESET_ALL}")
        except Exception as e:
            print(f"\n{Fore.RED}❌ Bot error: {e}{Style.RESET_ALL}")
            return False

def main():
    """Main function"""
    scraper = WorkanaScraper()
    # Parse command line arguments
    import sys
    continuous = '--continuous' in sys.argv or '-c' in sys.argv
    discord_mode = '--discord' in sys.argv or '-d' in sys.argv
    interval = 60 if discord_mode else 300  # 60s for Discord mode, 5 minutes default
    
    if continuous:
        # Check for custom interval
        for arg in sys.argv:
            if arg.startswith('--interval='):
                try:
                    interval = int(arg.split('=')[1])
                except ValueError:
                    print(f"{Fore.RED}Invalid interval format. Using default interval.{Style.RESET_ALL}")
    scraper.run(continuous=continuous, interval=interval, discord_mode=discord_mode)

if __name__ == "__main__":
    main()