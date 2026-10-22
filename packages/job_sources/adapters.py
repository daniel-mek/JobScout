import re
from datetime import UTC, datetime
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlencode, urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .safe_http import SafeHTTP, SourceError, public_url


class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        if tag in ("p", "br", "li", "div", "h2", "h3"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain(value) -> str | None:
    if not value:
        return None
    parser = TextOnly()
    parser.feed(unescape(str(value)[:150000]))
    return (
        "\n".join(" ".join(x.split()) for x in "".join(parser.parts).splitlines() if x.strip())[:60000]
        or None
    )


def normalized(value: str) -> str:
    return " ".join(value.casefold().split())


def date(value) -> str | None:
    if not value:
        return None
    try:
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(value / 1000, UTC).isoformat()
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.replace(tzinfo=parsed.tzinfo or UTC).astimezone(UTC).isoformat()
    except (ValueError, OverflowError, OSError):
        return None


class Posting(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, allow_inf_nan=False)
    external_id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=300)
    company: str = Field(min_length=1, max_length=200)
    location: str | None = Field(default=None, max_length=300)
    country: str | None = Field(default=None, max_length=100)
    arrangement: str | None = Field(default=None, pattern="^(REMOTE|HYBRID|ONSITE)$")
    employment_type: str | None = Field(default=None, max_length=60)
    salary_min: float | None = Field(default=None, ge=0)
    salary_max: float | None = Field(default=None, ge=0)
    salary_period: str | None = Field(default=None, max_length=50)
    currency: str | None = Field(default=None, max_length=10)
    description: str | None = Field(default=None, max_length=60000)
    responsibilities: str | None = Field(default=None, max_length=20000)
    requirements: str | None = Field(default=None, max_length=20000)
    experience_min: float | None = Field(default=None, ge=0, le=100)
    experience_max: float | None = Field(default=None, ge=0, le=100)
    education: str | None = Field(default=None, max_length=5000)
    clearance: str | None = Field(default=None, max_length=5000)
    work_authorization: str | None = Field(default=None, max_length=5000)
    posted_at: str | None = None
    application_url: str = Field(max_length=2000)

    @field_validator("application_url")
    @classmethod
    def safe_link(cls, value):
        try:
            return public_url(value)
        except SourceError:
            raise ValueError("Use a public application URL.") from None

    @field_validator("posted_at")
    @classmethod
    def valid_date(cls, value):
        if value and not date(value):
            raise ValueError("Invalid posting date")
        return date(value)


def detect(value: str) -> dict:
    """Detect known ATS URLs without fetching an arbitrary career page."""
    url = urlsplit(public_url(value))
    parts = [x for x in url.path.split("/") if x]
    host = url.hostname
    provider = {
        "boards.greenhouse.io": "greenhouse",
        "job-boards.greenhouse.io": "greenhouse",
        "jobs.lever.co": "lever",
        "jobs.eu.lever.co": "lever",
        "jobs.ashbyhq.com": "ashby",
        "jobs.smartrecruiters.com": "smartrecruiters",
        "careers.smartrecruiters.com": "smartrecruiters",
    }.get(host or "")
    if provider and parts and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", parts[0]):
        return {
            "provider": provider,
            "board": ("eu:" if host == "jobs.eu.lever.co" else "") + parts[0],
            "supported": True,
            "method": "documented_api",
        }
    return {
        "provider": "workday" if (host or "").endswith(".myworkdayjobs.com") else "generic",
        "board": "",
        "supported": False,
        "method": "manual",
        "reason": "No reviewed API or feed is registered for this site. Enter the job manually.",
    }


def arrangement(value):
    return {
        "remote": "REMOTE",
        "hybrid": "HYBRID",
        "onsite": "ONSITE",
        "on-site": "ONSITE",
        "on site": "ONSITE",
    }.get(str(value).lower())


HOSTS = {
    "greenhouse": {"boards-api.greenhouse.io"},
    "lever": {"api.lever.co", "api.eu.lever.co"},
    "ashby": {"api.ashbyhq.com"},
    "smartrecruiters": {"api.smartrecruiters.com"},
    "usajobs": {"data.usajobs.gov"},
    "adzuna": {"api.adzuna.com"},
}


def fetch(
    provider: str, board: str, company: str, credentials: dict, rate: dict, http=None, cursor: int = 0
) -> tuple[list[Posting], bool, int]:
    """Return validated public postings plus whether this is a complete employer feed.

    An incomplete/malformed feed fails atomically: it must not archive old jobs.
    Search APIs and capped pagination never qualify as complete employer feeds.
    """
    if provider not in HOSTS:
        raise SourceError("adapter_unavailable")
    http = http or SafeHTTP(HOSTS[provider], rate.get("min_interval_seconds", 1))
    pages = max(1, min(4, int(rate.get("max_pages", 4))))
    if not re.fullmatch(r"(?:eu:)?[A-Za-z0-9_-]{1,100}", board):
        raise SourceError("invalid_board")
    if provider == "smartrecruiters":
        payload = http.get(
            f"https://api.smartrecruiters.com/v1/companies/{board}/postings?offset={cursor}&limit=5"
        )
        items = payload["content"]
        if not isinstance(items, list) or len(items) > 5:
            raise SourceError("invalid_response")
        postings = []
        for item in items:
            identifier = str(item["id"])
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", identifier):
                raise SourceError("invalid_response")
            detail = http.get(f"https://api.smartrecruiters.com/v1/companies/{board}/postings/{identifier}")
            if detail.get("active") is False:
                continue
            posting = convert(provider, {**item, **detail}, company)
            if not re.search(r"\bintern(ship)?\b", posting.title, re.I):
                postings.append(posting)
        total = int(payload["totalFound"])
        end = cursor + len(items)
        if not items and total > cursor:
            raise SourceError("invalid_response")
        return postings, end >= total, 0 if end >= total else end
    rows: list[Posting] = []
    complete = False
    for page in range(pages):
        if provider == "greenhouse":
            payload = http.get(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true")
            items = payload["jobs"]
            complete = len(items) == payload.get("meta", {}).get("total", len(items))
        elif provider == "ashby":
            payload = http.get(f"https://api.ashbyhq.com/posting-api/job-board/{board}")
            items = payload["jobs"]
            complete = True
        elif provider == "lever":
            host = "api.eu.lever.co" if board.startswith("eu:") else "api.lever.co"
            items = http.get(
                f"https://{host}/v0/postings/{board.removeprefix('eu:')}?mode=json&skip={cursor + page * 100}&limit=100"
            )
            complete = len(items) < 100
        elif provider == "usajobs":
            payload = http.get(
                "https://data.usajobs.gov/api/search?"
                + urlencode({"Keyword": board, "Page": page + 1, "ResultsPerPage": 100}),
                {
                    "Host": "data.usajobs.gov",
                    "User-Agent": credentials["USAJOBS_EMAIL"],
                    "Authorization-Key": credentials["USAJOBS_API_KEY"],
                },
            )
            items = [x["MatchedObjectDescriptor"] for x in payload["SearchResult"]["SearchResultItems"]]
        else:
            payload = http.get(
                "https://api.adzuna.com/v1/api/jobs/us/search/"
                + str(page + 1)
                + "?"
                + urlencode(
                    {
                        "app_id": credentials["ADZUNA_APP_ID"],
                        "app_key": credentials["ADZUNA_APP_KEY"],
                        "what": board,
                        "results_per_page": 100,
                        "full_time": 1,
                        "content-type": "application/json",
                    }
                )
            )
            items = payload["results"]
        if not isinstance(items, list) or len(items) > 5000:
            raise SourceError("invalid_response")
        for item in items:
            if provider == "ashby" and item.get("isListed") is not True:
                continue
            row = convert(provider, item, company)
            # Discovery remains full-time IT/CS; historical resume internships are unaffected.
            if re.search(r"\bintern(ship)?\b", row.title, re.I) or str(row.employment_type).lower() in (
                "intern",
                "internship",
            ):
                continue
            rows.append(row)
        if complete or provider in ("greenhouse", "ashby") or len(items) < 100:
            break
    if len(rows) > 5000:
        raise SourceError("response_too_large")
    return (
        rows,
        complete if provider not in ("usajobs", "adzuna") else False,
        (cursor + pages * 100 if provider == "lever" and not complete else 0),
    )


def convert(provider: str, item: dict, company: str) -> Posting:
    if provider == "greenhouse":
        return Posting(
            external_id=str(item["id"]),
            title=item["title"],
            company=company,
            location=item.get("location", {}).get("name"),
            description=plain(item.get("content")),
            application_url=item["absolute_url"],
            posted_at=date(item.get("first_published")),
        )
    if provider == "lever":
        category = item.get("categories", {})
        salary = item.get("salaryRange") or {}
        return Posting(
            external_id=item["id"],
            title=item["text"],
            company=company,
            location=category.get("location"),
            employment_type=category.get("commitment"),
            arrangement=arrangement(item.get("workplaceType")),
            description=plain(
                "\n".join(
                    filter(
                        None,
                        [
                            item.get("descriptionPlain") or item.get("description"),
                            *[x.get("text", "") + "\n" + x.get("content", "") for x in item.get("lists", [])],
                            item.get("additionalPlain") or item.get("additional"),
                        ],
                    )
                )
            ),
            application_url=item.get("applyUrl") or item["hostedUrl"],
            posted_at=date(item.get("createdAt")),
            salary_min=salary.get("min"),
            salary_max=salary.get("max"),
            currency=salary.get("currency"),
            salary_period=salary.get("interval"),
        )
    if provider == "ashby":
        return Posting(
            external_id=str(item.get("id") or urlsplit(item["jobUrl"]).path.rstrip("/").split("/")[-1]),
            title=item["title"],
            company=company,
            location=item.get("location"),
            country=(item.get("address") or {}).get("postalAddress", {}).get("addressCountry"),
            arrangement=arrangement(item.get("workplaceType")),
            employment_type=item.get("employmentType"),
            description=plain(item.get("descriptionPlain") or item.get("descriptionHtml")),
            application_url=item.get("applyUrl") or item["jobUrl"],
            posted_at=date(item.get("publishedAt")),
        )
    if provider == "smartrecruiters":
        # Public list endpoint only. Never request authenticated/internal postings.
        location = item.get("location") or {}
        sections = item.get("jobAd", {}).get("sections", {})
        return Posting(
            external_id=str(item["id"]),
            title=item["name"],
            company=company,
            location=location.get("city"),
            country=location.get("country"),
            posted_at=date(item.get("releasedDate")),
            application_url=item.get("applyUrl") or item["postingUrl"],
            description=plain(sections.get("jobDescription", {}).get("text")),
            requirements=plain(sections.get("qualifications", {}).get("text")),
            employment_type=item.get("typeOfEmployment", {}).get("label"),
            arrangement="REMOTE" if location.get("remote") is True else None,
        )
    if provider == "usajobs":
        pay = (item.get("PositionRemuneration") or [{}])[0]
        details = item.get("UserArea", {}).get("Details", {})
        return Posting(
            external_id=str(item["PositionID"]),
            title=item["PositionTitle"],
            company=item["OrganizationName"],
            location=item.get("PositionLocationDisplay"),
            application_url=(item.get("ApplyURI") or [item["PositionURI"]])[0],
            posted_at=date(item.get("PublicationStartDate")),
            description=plain(details.get("JobSummary")),
            requirements=plain(item.get("QualificationSummary")),
            education=plain(details.get("Education")),
            salary_min=pay.get("MinimumRange"),
            salary_max=pay.get("MaximumRange"),
            salary_period=pay.get("RateIntervalCode"),
        )
    return Posting(
        external_id=str(item["id"]),
        title=plain(item["title"]) or item["title"],
        company=item["company"]["display_name"],
        location=item.get("location", {}).get("display_name"),
        application_url=item["redirect_url"],
        description=plain(item.get("description")),
        posted_at=date(item.get("created")),
        salary_min=None if item.get("salary_is_predicted") else item.get("salary_min"),
        salary_max=None if item.get("salary_is_predicted") else item.get("salary_max"),
        employment_type=item.get("contract_time"),
    )
