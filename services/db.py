from __future__ import annotations

import hashlib
import os
import sqlite3
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any


def _db_path() -> str:
    raw = os.getenv("DATABASE_URL", "sqlite:///job_agent.db")
    if not raw.startswith("sqlite:///"):
        raise ValueError("Only sqlite DATABASE_URL is supported in this MVP.")
    return raw.replace("sqlite:///", "", 1)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT NOT NULL,
                title TEXT NOT NULL,
                location TEXT,
                url TEXT UNIQUE NOT NULL,
                jd_text TEXT,
                source TEXT,
                match_score REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS jobs_fts USING fts5(
                company,
                title,
                location,
                jd_text,
                content='jobs',
                content_rowid='id'
            );
            CREATE TABLE IF NOT EXISTS recruiters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER REFERENCES jobs(id),
                name TEXT,
                email TEXT,
                UNIQUE(job_id, email)
            );
            CREATE TABLE IF NOT EXISTS emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER REFERENCES jobs(id),
                recruiter_email TEXT NOT NULL,
                subject TEXT,
                body TEXT,
                status TEXT CHECK (status IN ('sent','skipped','failed')),
                sent_at TEXT,
                dedupe_key TEXT UNIQUE NOT NULL,
                gmail_message_id TEXT,
                gmail_thread_id TEXT
            );
            CREATE TABLE IF NOT EXISTS replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email_id INTEGER REFERENCES emails(id),
                raw_text TEXT,
                category TEXT,
                confidence REAL,
                received_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS run_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_started TEXT,
                run_finished TEXT,
                jobs_processed INTEGER,
                emails_sent INTEGER,
                errors TEXT
            );
            CREATE TABLE IF NOT EXISTS inbox_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gmail_message_id TEXT,
                gmail_thread_id TEXT,
                sender_email TEXT,
                subject TEXT,
                body TEXT NOT NULL,
                received_at TEXT DEFAULT CURRENT_TIMESTAMP,
                processed INTEGER DEFAULT 0,
                category TEXT,
                confidence REAL,
                email_id INTEGER REFERENCES emails(id),
                error TEXT
            );
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
            CREATE TABLE IF NOT EXISTS resumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                latex_content TEXT NOT NULL,
                is_active INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                subject_template TEXT NOT NULL,
                body_template TEXT NOT NULL,
                is_active INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS ats_companies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                ats_type TEXT NOT NULL,
                token TEXT NOT NULL UNIQUE,
                last_scraped TEXT
            );
            CREATE TABLE IF NOT EXISTS ats_crawler_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_id INTEGER REFERENCES ats_companies(id),
                title TEXT NOT NULL,
                location TEXT NOT NULL,
                url TEXT UNIQUE NOT NULL,
                jd_text TEXT,
                source TEXT NOT NULL,
                last_seen TEXT DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS companies_custom (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                domain TEXT UNIQUE NOT NULL,
                career_url TEXT,
                ats_detected TEXT,
                last_checked TEXT,
                status TEXT DEFAULT 'pending'
            );
            """
        )
        # FTS5 virtual table for blazing-fast full-text search
        try:
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS ats_crawler_jobs_fts USING fts5(
                    title, location, jd_text,
                    content='ats_crawler_jobs',
                    content_rowid='id'
                )
            """)
        except sqlite3.OperationalError:
            pass  # FTS5 may not be available on all SQLite builds
        # Indexes
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_crawler_jobs_title ON ats_crawler_jobs(title COLLATE NOCASE)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_crawler_jobs_location ON ats_crawler_jobs(location COLLATE NOCASE)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_crawler_jobs_source ON ats_crawler_jobs(source)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_crawler_jobs_last_seen ON ats_crawler_jobs(last_seen)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ats_companies_ats_type ON ats_companies(ats_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_ats_companies_last_scraped ON ats_companies(last_scraped)")
        except sqlite3.OperationalError:
            pass
        # Attempt to add new columns to jobs table if they don't exist
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN status TEXT DEFAULT 'discovered'")
        except sqlite3.OperationalError:
            pass
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN apply_error TEXT")
        except sqlite3.OperationalError:
            pass
        columns = conn.execute("PRAGMA table_info(inbox_entries)").fetchall()
        names = {str(col["name"]) for col in columns}
        if "gmail_message_id" not in names:
            conn.execute("ALTER TABLE inbox_entries ADD COLUMN gmail_message_id TEXT")
        if "gmail_thread_id" not in names:
            conn.execute("ALTER TABLE inbox_entries ADD COLUMN gmail_thread_id TEXT")
        email_columns = conn.execute("PRAGMA table_info(emails)").fetchall()
        email_names = {str(col["name"]) for col in email_columns}
        if "gmail_message_id" not in email_names:
            conn.execute("ALTER TABLE emails ADD COLUMN gmail_message_id TEXT")
        if "gmail_thread_id" not in email_names:
            conn.execute("ALTER TABLE emails ADD COLUMN gmail_thread_id TEXT")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_inbox_entries_gmail_message_id ON inbox_entries(gmail_message_id)"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_emails_gmail_thread_id ON emails(gmail_thread_id)")


def make_dedupe_key(company: str, recruiter_email: str, title: str) -> str:
    raw = f"{company.lower()}|{recruiter_email.lower()}|{title.lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def upsert_job(job: Mapping[str, Any], match_score: float | None) -> int:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO jobs (company, title, location, url, jd_text, source, match_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(url) DO UPDATE SET
                company=excluded.company,
                title=excluded.title,
                location=excluded.location,
                jd_text=excluded.jd_text,
                source=excluded.source,
                match_score=excluded.match_score
            """,
            (
                job.get("company", ""),
                job.get("title", ""),
                job.get("location"),
                job.get("url", ""),
                job.get("jd_text"),
                job.get("source"),
                match_score,
                _utc_now(),
            ),
        )
        row = conn.execute("SELECT id FROM jobs WHERE url = ?", (job.get("url", ""),)).fetchone()
        if row is None:
            raise RuntimeError("Failed to persist job row.")
        return int(row["id"])


def already_sent(dedupe_key: str) -> bool:
    with get_conn() as conn:
        row = conn.execute("SELECT 1 FROM emails WHERE dedupe_key = ?", (dedupe_key,)).fetchone()
        return row is not None


def store_email_result(
    job_id: int,
    recruiter_email: str,
    subject: str | None,
    body: str | None,
    status: str,
    dedupe_key: str,
    gmail_message_id: str | None = None,
    gmail_thread_id: str | None = None,
) -> None:
    sent_at = _utc_now() if status == "sent" else None
    with get_conn() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO emails
            (id, job_id, recruiter_email, subject, body, status, sent_at, dedupe_key, gmail_message_id, gmail_thread_id)
            VALUES (
                (SELECT id FROM emails WHERE dedupe_key = ?),
                ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                dedupe_key,
                job_id,
                recruiter_email,
                subject,
                body,
                status,
                sent_at,
                dedupe_key,
                gmail_message_id,
                gmail_thread_id,
            ),
        )


def store_run_log(run_started: str, run_finished: str, jobs_processed: int, emails_sent: int, errors: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO run_log (run_started, run_finished, jobs_processed, emails_sent, errors)
            VALUES (?, ?, ?, ?, ?)
            """,
            (run_started, run_finished, jobs_processed, emails_sent, errors),
        )


def count_sent_today() -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS c FROM emails WHERE status='sent' AND date(sent_at)=date('now')"
        ).fetchone()
        return int(row["c"]) if row else 0


def count_replies() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM replies").fetchone()
        return int(row["c"]) if row else 0


def count_by_category(category: str) -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM replies WHERE category = ?", (category,)).fetchone()
        return int(row["c"]) if row else 0


def emails_sent_total() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS c FROM emails WHERE status='sent'").fetchone()
        return int(row["c"]) if row else 0


def success_rate() -> float:
    sent = emails_sent_total()
    if sent == 0:
        return 0.0
    return round((count_by_category("INTERVIEW") / sent) * 100.0, 2)


NON_TECH_TITLE_EXCLUSIONS = [
    "sales", "support", "customer", "tele-sales", "recruiter", "hr ", "designer",
    "product designer", "marketing", "accountant", "legal", "content", "writer",
    "agent", "representative", "operations", "business analyst", "inside sales",
    "product manager", "project manager", "talent", "people", "brand", "finance",
    "f&b", "deal desk", "guest service", "video editor", "social media", "insights associate",
    "account coordinator", "client service", "customer success", "sales associate", "retail associate"
]

# Indian location keywords for SQL pre-filtering
INDIAN_LOCATION_KEYWORDS = [
    "bengaluru", "bangalore", "mumbai", "delhi", "noida", "gurugram", "gurgaon",
    "hyderabad", "chennai", "pune", "india", "kolkata", "ahmedabad", "jaipur",
    "lucknow", "kochi", "thiruvananthapuram", "indore", "chandigarh", "coimbatore",
    "ncr", "greater delhi", "nagpur", "bhubaneswar", "mysore", "mysuru",
    "trivandrum", "mangalore", "mangaluru", "visakhapatnam", "vizag",
    "madurai", "surat", "vadodara", "rajkot", "nashik",
]

# False-positive location words that contain Indian substrings
INDIA_FALSE_POSITIVES = ["indianapolis", "indiana", "east india"]


def _normalize_user_query(q: str) -> str:
    raw = q.strip().lower()
    raw = raw.replace("software developer i", "software developer")
    raw = raw.replace("software engineer i", "software engineer")
    raw = raw.replace("sde i", "sde")
    raw = raw.replace("software developer 1", "software developer")
    raw = raw.replace("software engineer 1", "software engineer")
    raw = raw.replace("sde 1", "sde")
    return raw


def _build_india_location_sql(table_alias: str) -> str:
    """Build SQL WHERE clause fragment that filters to Indian locations only."""
    city_clauses = " OR ".join(
        f"lower({table_alias}.location) LIKE '%{c}%'" for c in INDIAN_LOCATION_KEYWORDS
    )
    false_pos = " AND ".join(
        f"lower({table_alias}.location) NOT LIKE '%{fp}%'" for fp in INDIA_FALSE_POSITIVES
    )
    return f"(({city_clauses}) AND ({false_pos}))"


def _is_non_tech_title(title: str) -> bool:
    t = title.lower()
    return any(ex in t for ex in NON_TECH_TITLE_EXCLUSIONS)


def _is_high_seniority_title(title: str) -> bool:
    """Only exclude C-suite and executive roles (VP, Director, etc.).
    Keep: Senior, Lead, Architect, Staff — these are still valid tech jobs."""
    t = title.lower()
    high_senior = [
        "principal", "distinguished", "director", "head of",
        "vp", "vice president", "president", "avp", "evp", "svp",
        "chief",
    ]
    return any(s in t for s in high_senior)


def _passes_experience_filter(title: str, jd_text: str, max_years: int = 5) -> bool:
    """Lightweight experience filter — returns True if the job likely requires <= max_years.
    
    Checks title and JD text for experience requirements like:
      - '5+ years', '3-5 years', 'minimum 4 years', 'at least 6 years'
      - Excludes jobs that clearly need more experience than max_years.
    """
    import re

    min_exp_threshold = max_years + 1
    t_lower = title.lower()
    jd_lower = (jd_text or "").lower()[:2000]  # Only check first 2000 chars of JD

    # Check title for experience numbers
    title_exp = re.search(
        r"\b(\d{1,2})\s*(?:\+|[–—\-]\s*\d+)?\s*(?:to\s*\d+)?\s*(?:years?|yrs?|yr)\b",
        t_lower,
    )
    if title_exp:
        try:
            val = int(title_exp.group(1))
            if val >= min_exp_threshold:
                return False
        except ValueError:
            pass

    # Check JD for experience requirements (multiple patterns)
    exp_patterns = [
        # "5+ years", "3-5 years", "minimum 4 years"
        r"\b(\d{1,2})\s*(?:\+|[–—\-]\s*\d+)?\s*(?:to\s*\d+)?\s*(?:years?|yrs?|yr)\s*(?:of)?\s*(?:experience|exp|relevant|professional|work|industry|hands.?on)?",
        # "experience: 5", "exp: 3+"
        r"\b(?:experience|exp)\s*:\s*(\d{1,2})",
        # "minimum 4 years", "at least 5 years"
        r"\b(?:minimum|at\s+least|min|with)\s*(\d{1,2})\s*(?:\+)?\s*(?:years?|yrs?)",
    ]
    for pat in exp_patterns:
        matches = re.findall(pat, jd_lower)
        for m in matches:
            try:
                val = int(m)
                if val >= min_exp_threshold:
                    return False
            except ValueError:
                pass

    # Check for English word experience numbers (e.g. "five years", "seven years")
    word_map = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
        "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    }
    word_matches = re.findall(
        r"\b(one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:\+)?\s*(?:years?|yrs?|yr)\b",
        jd_lower,
    )
    for w in word_matches:
        if word_map.get(w, 0) >= min_exp_threshold:
            return False

    return True



def list_jobs(
    limit: int = 100,
    offset: int = 0,
    q: str | None = None,
    location: str | None = None,
    source: str | None = None,
) -> list[dict[str, Any]]:
    # Synonym expansion map
    SYNONYMS = {
        "software developer": ["software engineer", "software developer", "sde", "developer", "software dev"],
        "software engineer": ["software engineer", "software developer", "sde", "developer", "software dev"],
        "sde": ["sde", "software engineer", "software developer", "developer"],
        "developer": ["developer", "software developer", "software engineer", "sde", "web developer"],
        "engineer": ["engineer", "software engineer", "developer", "sde"],
        "frontend": ["frontend", "front-end", "front end", "react", "vue", "angular", "ui developer", "ui engineer"],
        "frontend developer": ["frontend", "front-end", "react", "vue", "angular", "ui developer"],
        "frontend engineer": ["frontend", "front-end", "react", "vue", "angular", "ui engineer"],
        "backend": ["backend", "back-end", "back end", "node", "python", "java", "golang", "django", "api"],
        "backend developer": ["backend", "back-end", "node", "python", "java", "golang"],
        "backend engineer": ["backend", "back-end", "node", "python", "java", "golang"],
        "fullstack": ["fullstack", "full-stack", "full stack"],
        "full stack": ["fullstack", "full-stack", "full stack"],
        "full stack developer": ["fullstack", "full-stack", "full stack"],
        "data engineer": ["data engineer", "data engineering", "etl", "data pipeline"],
        "data scientist": ["data scientist", "data science", "machine learning", "ml engineer"],
        "devops": ["devops", "dev ops", "site reliability", "sre", "infrastructure", "platform engineer"],
        "python": ["python", "django", "flask", "fastapi"],
        "python developer": ["python", "django", "flask", "fastapi", "python developer"],
        "react": ["react", "frontend", "front-end", "nextjs", "next.js"],
        "java": ["java ", "spring", "springboot", "java developer"],
        "java developer": ["java ", "spring", "springboot", "java developer"],
        "node": ["node", "nodejs", "node.js", "express"],
        "golang": ["golang", "go developer", "go engineer"],
        "machine learning": ["machine learning", "ml engineer", "deep learning", "ai engineer", "data scientist"],
        "qa": ["qa", "quality assurance", "test engineer", "sdet", "automation engineer"],
        "test engineer": ["test engineer", "qa engineer", "sdet", "automation engineer"],
        "android": ["android", "android developer", "kotlin", "mobile developer"],
        "ios": ["ios", "ios developer", "swift", "mobile developer"],
        "mobile": ["mobile", "android", "ios", "react native", "flutter"],
        "cloud": ["cloud", "aws", "azure", "gcp", "cloud engineer"],
        "intern": ["intern", "internship", "trainee", "fresher", "graduate"],
    }

    norm_q = _normalize_user_query(q) if q and q.strip() else None

    with get_conn() as conn:
        # Step 1: Query main jobs table
        where_clauses: list[str] = []
        params: list[Any] = []

        if norm_q:
            synonyms = SYNONYMS.get(norm_q)
            if synonyms:
                syn_clauses = []
                for syn in synonyms:
                    syn_clauses.append("(lower(j.title) LIKE ? OR lower(j.company) LIKE ? OR lower(j.jd_text) LIKE ?)")
                    params.extend([f"%{syn}%", f"%{syn}%", f"%{syn}%"])
                where_clauses.append("(" + " OR ".join(syn_clauses) + ")")
            else:
                # Keep ALL tokens including "developer", "engineer", "software" — they matter!
                tokens = [t.strip() for t in norm_q.split() if len(t.strip()) >= 2 and t.strip() not in ("role", "roles", "jobs", "job", "for", "the", "a", "in")]
                if not tokens:
                    tokens = [norm_q]
                token_subclauses = []
                for t in tokens:
                    token_subclauses.append("(lower(j.title) LIKE ? OR lower(j.company) LIKE ? OR lower(j.jd_text) LIKE ?)")
                    params.extend([f"%{t}%", f"%{t}%", f"%{t}%"])
                if token_subclauses:
                    where_clauses.append("(" + " OR ".join(token_subclauses) + ")")

        if location and location.strip() and location.lower() not in ("any", "all", "worldwide"):
            loc_lower = location.lower().strip()
            if loc_lower == "india":
                where_clauses.append(_build_india_location_sql("j"))
            else:
                where_clauses.append("lower(j.location) LIKE ?")
                params.append(f"%{loc_lower}%")

        if source and source.strip() and source.lower() != "all":
            where_clauses.append("j.source = ?")
            params.append(source.strip())

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        query = f"""
            SELECT j.id, j.company, j.title, j.location, j.url, j.source, j.match_score, j.created_at, j.stage,
                   e.recruiter_email, e.status
            FROM jobs j
            LEFT JOIN emails e ON e.job_id = j.id
            {where_sql}
            GROUP BY j.id
            ORDER BY j.id DESC
            LIMIT ? OFFSET ?
        """
        params.extend([limit * 3, 0])

        rows = conn.execute(query, params).fetchall()
        results = [
            dict(row) for row in rows
            if not _is_non_tech_title(row["title"])
        ]

        # Step 2: Query ats_crawler_jobs (67K+ indexed jobs)
        # Pre-filter by India location IN SQL, use FTS5 when possible
        raw_q = (norm_q or "software engineer").strip().lower()
        synonyms = SYNONYMS.get(raw_q)

        # --- Build India location filter for SQL ---
        india_loc_sql = _build_india_location_sql("cj")

        # --- Try FTS5 first for speed ---
        fts_results: list[sqlite3.Row] = []
        fts_available = False
        try:
            # Build FTS5 match expression
            if synonyms:
                fts_terms = " OR ".join(f'"{syn}"' for syn in synonyms)
            else:
                tokens = [t.strip() for t in raw_q.split() if len(t.strip()) >= 2 and t.strip() not in ("role", "roles", "jobs", "job", "for", "the", "a", "in")]
                if not tokens:
                    tokens = [raw_q]
                fts_terms = " OR ".join(f'"{t}"' for t in tokens)

            fts_match = f"({fts_terms})"

            fts_query = f"""
                SELECT c.name as company, cj.title, cj.location, cj.url, cj.jd_text, cj.source,
                       98.0 as match_score, cj.last_seen as created_at
                FROM ats_crawler_jobs cj
                JOIN ats_crawler_jobs_fts fts ON cj.id = fts.rowid
                LEFT JOIN ats_companies c ON cj.company_id = c.id
                WHERE fts.ats_crawler_jobs_fts MATCH ?
                  AND {india_loc_sql}
                  AND julianday('now') - julianday(cj.last_seen) <= 14
                ORDER BY cj.last_seen DESC
                LIMIT 10000
            """
            fts_results = conn.execute(fts_query, (fts_match,)).fetchall()
            fts_available = True
        except (sqlite3.OperationalError, sqlite3.DatabaseError):
            fts_available = False

        # --- Fallback: LIKE scan if FTS5 failed or returned too few ---
        if not fts_available or len(fts_results) < 50:
            c_where = [india_loc_sql, "julianday('now') - julianday(cj.last_seen) <= 14"]
            c_params: list[Any] = []

            if synonyms:
                syn_clauses = []
                for syn in synonyms:
                    syn_clauses.append("(lower(cj.title) LIKE ? OR lower(cj.jd_text) LIKE ?)")
                    c_params.extend([f"%{syn}%", f"%{syn}%"])
                c_where.append("(" + " OR ".join(syn_clauses) + ")")
            else:
                tokens = [t.strip() for t in raw_q.split() if len(t.strip()) >= 2 and t.strip() not in ("role", "roles", "jobs", "job", "for", "the", "a", "in")]
                if not tokens:
                    tokens = [raw_q]
                # Use OR for broader matching
                token_subclauses = []
                for t in tokens:
                    token_subclauses.append("(lower(cj.title) LIKE ? OR lower(cj.jd_text) LIKE ?)")
                    c_params.extend([f"%{t}%", f"%{t}%"])
                if token_subclauses:
                    c_where.append("(" + " OR ".join(token_subclauses) + ")")

            c_where_sql = " WHERE " + " AND ".join(c_where)

            c_query = f"""
                SELECT c.name as company, cj.title, cj.location, cj.url, cj.jd_text, cj.source,
                       98.0 as match_score, cj.last_seen as created_at
                FROM ats_crawler_jobs cj
                LEFT JOIN ats_companies c ON cj.company_id = c.id
                {c_where_sql}
                ORDER BY cj.last_seen DESC
                LIMIT 10000
            """
            like_results = conn.execute(c_query, c_params).fetchall()

            # Merge FTS + LIKE results, deduplicate by URL
            if fts_available and fts_results:
                fts_urls = {dict(r).get("url") for r in fts_results}
                combined = list(fts_results) + [r for r in like_results if dict(r).get("url") not in fts_urls]
                c_rows = combined
            else:
                c_rows = like_results
        else:
            c_rows = fts_results

        existing_urls = {r.get("url") for r in results if r.get("url")}

        for idx, r in enumerate(c_rows, 1):
            d = dict(r)
            url = d.get("url")
            if not url or url in existing_urls:
                continue
            title = d.get("title") or ""
            jd = d.get("jd_text") or ""

            # Skip non-tech and very-high-seniority titles
            if _is_non_tech_title(title) or _is_high_seniority_title(title):
                continue

            # Skip jobs requiring more than 5 years of experience
            if not _passes_experience_filter(title, jd, max_years=5):
                continue

            d["id"] = 300000 + idx
            d["company"] = d.get("company") or "Tech Startup"
            d["stage"] = "discovered"
            d["recruiter_email"] = None
            d["status"] = None
            results.append(d)
            existing_urls.add(url)

        # Slice results to user requested pagination
        return results[offset : offset + limit]

def get_job(job_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

def list_unprocessed_inbox_entries(limit: int = 50) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id, gmail_thread_id, sender_email, subject, body, received_at
            FROM inbox_entries
            WHERE processed = 0
            ORDER BY datetime(received_at) ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]


def list_known_recruiter_emails(limit: int = 500) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT lower(recruiter_email) AS recruiter_email
            FROM emails
            WHERE recruiter_email IS NOT NULL
            ORDER BY recruiter_email
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [str(row["recruiter_email"]) for row in rows if row["recruiter_email"]]


def list_known_gmail_threads(limit: int = 500) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT gmail_thread_id
            FROM emails
            WHERE gmail_thread_id IS NOT NULL AND trim(gmail_thread_id) != ''
            ORDER BY datetime(COALESCE(sent_at, CURRENT_TIMESTAMP)) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
        return [str(row["gmail_thread_id"]) for row in rows if row["gmail_thread_id"]]


def inbox_message_exists(gmail_message_id: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM inbox_entries WHERE gmail_message_id = ?",
            (gmail_message_id,),
        ).fetchone()
        return row is not None


def insert_inbox_entry(
    *,
    gmail_message_id: str,
    gmail_thread_id: str | None,
    sender_email: str | None,
    subject: str | None,
    body: str,
    received_at: str | None,
) -> int:
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO inbox_entries (gmail_message_id, gmail_thread_id, sender_email, subject, body, received_at, processed)
            VALUES (?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP), 0)
            """,
            (gmail_message_id, gmail_thread_id, sender_email, subject, body, received_at),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("Failed to insert inbox entry row.")
        return int(cursor.lastrowid)


def resolve_email_id_by_sender(sender_email: str | None) -> int | None:
    if not sender_email:
        return None
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id
            FROM emails
            WHERE lower(recruiter_email) = lower(?)
            ORDER BY datetime(COALESCE(sent_at, CURRENT_TIMESTAMP)) DESC
            LIMIT 1
            """,
            (sender_email,),
        ).fetchone()
        return int(row["id"]) if row else None


def resolve_email_id_by_thread(thread_id: str | None) -> int | None:
    if not thread_id:
        return None
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id
            FROM emails
            WHERE gmail_thread_id = ?
            ORDER BY datetime(COALESCE(sent_at, CURRENT_TIMESTAMP)) DESC
            LIMIT 1
            """,
            (thread_id,),
        ).fetchone()
        return int(row["id"]) if row else None


def insert_reply(
    *,
    email_id: int | None,
    raw_text: str,
    category: str,
    confidence: float,
    received_at: str | None,
) -> int:
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO replies (email_id, raw_text, category, confidence, received_at)
            VALUES (?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
            """,
            (email_id, raw_text, category, confidence, received_at),
        )
        if cursor.lastrowid is None:
            raise RuntimeError("Failed to insert reply row.")
        return int(cursor.lastrowid)


def mark_inbox_processed(entry_id: int, *, category: str, confidence: float, email_id: int | None) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE inbox_entries
            SET processed = 1, category = ?, confidence = ?, email_id = ?, error = NULL
            WHERE id = ?
            """,
            (category, confidence, email_id, entry_id),
        )


def mark_inbox_error(entry_id: int, error: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE inbox_entries
            SET error = ?
            WHERE id = ?
            """,
            (error, entry_id),
        )


def list_replies(limit: int, offset: int) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT r.id, r.email_id, r.raw_text, r.category, r.confidence, r.received_at, e.recruiter_email
            FROM replies r
            LEFT JOIN emails e ON e.id = r.email_id
            ORDER BY datetime(r.received_at) DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        return [dict(row) for row in rows]

def list_followups(limit: int, offset: int) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT e.id, e.recruiter_email, e.sent_at, j.company, 
                   CAST(julianday('now') - julianday(e.sent_at) AS INTEGER) AS days_since_sent
            FROM emails e
            LEFT JOIN jobs j ON e.job_id = j.id
            WHERE e.status = 'sent' 
              AND (julianday('now') - julianday(e.sent_at)) > 3
              AND NOT EXISTS (
                  SELECT 1 FROM replies r 
                  WHERE r.email_id = e.id 
                  AND r.category IN ('INTERVIEW', 'REJECTED')
              )
            ORDER BY datetime(e.sent_at) ASC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        return [dict(row) for row in rows]

# --- Configuration, Resumes, and Templates CRUD ---

def get_setting(key: str, default: str = "") -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return str(row["value"]) if row else default

def set_setting(key: str, value: str) -> None:
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))

def list_settings() -> dict[str, str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {str(row["key"]): str(row["value"]) for row in rows}

def list_resumes() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM resumes ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

def get_active_resume() -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM resumes WHERE is_active = 1 LIMIT 1").fetchone()
        return dict(row) if row else None

def insert_resume(name: str, latex_content: str, is_active: bool) -> int:
    with get_conn() as conn:
        if is_active:
            conn.execute("UPDATE resumes SET is_active = 0")
        cursor = conn.execute(
            "INSERT INTO resumes (name, latex_content, is_active) VALUES (?, ?, ?)",
            (name, latex_content, 1 if is_active else 0)
        )
        if cursor.lastrowid is None:
            raise RuntimeError("Failed to insert resume")
        return int(cursor.lastrowid)

def update_resume(resume_id: int, name: str, latex_content: str, is_active: bool) -> None:
    with get_conn() as conn:
        if is_active:
            conn.execute("UPDATE resumes SET is_active = 0 WHERE id != ?", (resume_id,))
        conn.execute(
            "UPDATE resumes SET name = ?, latex_content = ?, is_active = ? WHERE id = ?",
            (name, latex_content, 1 if is_active else 0, resume_id)
        )

def delete_resume(resume_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM resumes WHERE id = ?", (resume_id,))

def list_templates() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM templates ORDER BY created_at DESC").fetchall()
        return [dict(row) for row in rows]

def get_active_template() -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM templates WHERE is_active = 1 LIMIT 1").fetchone()
        return dict(row) if row else None

def insert_template(name: str, subject_template: str, body_template: str, is_active: bool) -> int:
    with get_conn() as conn:
        if is_active:
            conn.execute("UPDATE templates SET is_active = 0")
        cursor = conn.execute(
            "INSERT INTO templates (name, subject_template, body_template, is_active) VALUES (?, ?, ?, ?)",
            (name, subject_template, body_template, 1 if is_active else 0)
        )
        if cursor.lastrowid is None:
            raise RuntimeError("Failed to insert template")
        return int(cursor.lastrowid)

def update_template(template_id: int, name: str, subject_template: str, body_template: str, is_active: bool) -> None:
    with get_conn() as conn:
        if is_active:
            conn.execute("UPDATE templates SET is_active = 0 WHERE id != ?", (template_id,))
        conn.execute(
            "UPDATE templates SET name = ?, subject_template = ?, body_template = ?, is_active = ? WHERE id = ?",
            (name, subject_template, body_template, 1 if is_active else 0, template_id)
        )

def delete_template(template_id: int) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM templates WHERE id = ?", (template_id,))

def update_job_stage(job_id: int, stage: str | None) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE jobs SET stage = ? WHERE id = ?", (stage, job_id))
