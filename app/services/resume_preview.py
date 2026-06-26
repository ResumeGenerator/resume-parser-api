from html import escape
import re

from app.models.resume_schema import ResumeProfile, TemplateResumeSection


def build_resume_preview_html(profile: ResumeProfile) -> str:
    data = profile.data
    accent_color = sanitize_css_color(profile.color)
    font = sanitize_font_family(profile.font)

    contact_parts = [
        data.location,
        data.phone,
        data.email,
    ]
    contacts = " | ".join(escape(part) for part in contact_parts if part)

    avatar_html = ""
    if profile.withPhoto and profile.avatar:
        avatar_html = (
            f'<img class="resume-avatar" src="{escape(profile.avatar, quote=True)}" '
            f'alt="{escape(data.name or "Resume photo", quote=True)}" />'
        )

    section_html = "\n".join(
        section_preview_html(section)
        for section in data.sections
        if section.title or section.items
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{escape(data.name or "Resume Preview")}</title>
  <style>
    body {{
      margin: 0;
      background: #f4f4f5;
      color: #18181b;
      font-family: "{font}", Arial, sans-serif;
    }}
    .resume-preview {{
      box-sizing: border-box;
      max-width: 860px;
      min-height: 100vh;
      margin: 0 auto;
      padding: 48px;
      background: #ffffff;
    }}
    .resume-header {{
      display: flex;
      gap: 24px;
      align-items: flex-start;
      border-bottom: 2px solid {accent_color};
      padding-bottom: 20px;
      margin-bottom: 28px;
    }}
    .resume-avatar {{
      width: 96px;
      height: 96px;
      object-fit: cover;
      border-radius: 50%;
      flex: 0 0 auto;
    }}
    h1 {{
      margin: 0;
      color: {accent_color};
      font-size: 34px;
      line-height: 1.15;
      letter-spacing: 0;
    }}
    .resume-title {{
      margin-top: 6px;
      font-size: 18px;
      font-weight: 600;
    }}
    .resume-contacts {{
      margin-top: 10px;
      font-size: 13px;
      color: #52525b;
    }}
    .resume-section {{
      margin-top: 24px;
    }}
    h2 {{
      margin: 0 0 10px;
      color: {accent_color};
      font-size: 17px;
      letter-spacing: 0;
      text-transform: uppercase;
      border-bottom: 1px solid #d4d4d8;
      padding-bottom: 6px;
    }}
    .entry {{
      margin-top: 14px;
    }}
    .entry-heading {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      font-weight: 700;
    }}
    .muted {{
      color: #71717a;
      font-size: 13px;
    }}
    p {{
      margin: 0;
      line-height: 1.55;
    }}
    ul {{
      margin: 8px 0 0 20px;
      padding: 0;
    }}
    li {{
      margin-top: 4px;
      line-height: 1.45;
    }}
    .pill-list {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 8px;
    }}
    .pill {{
      border: 1px solid #d4d4d8;
      border-radius: 999px;
      padding: 4px 10px;
      font-size: 13px;
    }}
  </style>
</head>
<body>
  <main class="resume-preview">
    <header class="resume-header">
      {avatar_html}
      <div>
        <h1>{escape(data.name)}</h1>
        <div class="resume-title">{escape(data.title)}</div>
        <div class="resume-contacts">{contacts}</div>
      </div>
    </header>
    {section_html}
  </main>
</body>
</html>"""


def section_preview_html(section: TemplateResumeSection) -> str:
    title = escape(section.title)
    content = section_items_html(section)
    if not content:
        return ""
    return f"""<section class="resume-section">
  <h2>{title}</h2>
  {content}
</section>"""


def section_items_html(section: TemplateResumeSection) -> str:
    items = section.items
    if isinstance(items, str):
        return f"<p>{escape(items)}</p>" if items else ""
    if not items:
        return ""

    if section.type == "skill":
        return render_skill_items(items)
    if section.type in {"experience", "internship"}:
        return "\n".join(render_experience_item(item) for item in items)
    if section.type == "education":
        return "\n".join(render_education_item(item) for item in items)
    if section.type == "course":
        return "\n".join(render_course_item(item) for item in items)
    if section.type == "language":
        return render_language_items(items)
    if section.type == "reference":
        return "\n".join(render_reference_item(item) for item in items)
    if section.type == "link":
        return "\n".join(render_link_item(item) for item in items)
    if section.type == "hobby":
        return render_string_list([str(item) for item in items])

    return render_string_list([format_generic_item(item) for item in items])


def render_skill_items(items: list[object]) -> str:
    pills = []
    for item in items:
        name = getattr(item, "name", "")
        level = getattr(item, "level", "")
        label = f"{name} - {level}" if level else name
        if label:
            pills.append(f'<span class="pill">{escape(label)}</span>')
    return f'<div class="pill-list">{"".join(pills)}</div>' if pills else ""


def render_language_items(items: list[object]) -> str:
    values = []
    for item in items:
        language = getattr(item, "language", "")
        level = getattr(item, "level", "")
        label = f"{language} - {level}" if level else language
        if label:
            values.append(label)
    return render_string_list(values)


def render_experience_item(item: object) -> str:
    position = getattr(item, "position", "")
    company = getattr(item, "company", "")
    location = getattr(item, "location", "")
    start = getattr(item, "start", "")
    end = getattr(item, "end", "")
    achievements = getattr(item, "achievements", [])
    role_line = " | ".join(part for part in (position, company) if part)
    date_line = format_date_range(start, end)
    meta = " | ".join(part for part in (location, date_line) if part)
    return f"""<div class="entry">
  <div class="entry-heading">
    <span>{escape(role_line)}</span>
    <span class="muted">{escape(meta)}</span>
  </div>
  {render_string_list(achievements)}
</div>"""


def render_education_item(item: object) -> str:
    degree = getattr(item, "degree", "")
    school = getattr(item, "school", "")
    location = getattr(item, "location", "")
    years = getattr(item, "years", "")
    start = getattr(item, "start", "")
    end = getattr(item, "end", "")
    highlights = getattr(item, "highlights", [])
    heading = " | ".join(part for part in (degree, school) if part)
    date_line = years or format_date_range(start, end)
    meta = " | ".join(part for part in (location, date_line) if part)
    return f"""<div class="entry">
  <div class="entry-heading">
    <span>{escape(heading)}</span>
    <span class="muted">{escape(meta)}</span>
  </div>
  {render_string_list(highlights)}
</div>"""


def render_course_item(item: object) -> str:
    course = getattr(item, "course", "")
    institution = getattr(item, "institution", "")
    date_line = format_date_range(getattr(item, "start", ""), getattr(item, "end", ""))
    heading = " | ".join(part for part in (course, institution) if part)
    return f"""<div class="entry">
  <div class="entry-heading">
    <span>{escape(heading)}</span>
    <span class="muted">{escape(date_line)}</span>
  </div>
</div>"""


def render_reference_item(item: object) -> str:
    name = getattr(item, "name", "")
    company = getattr(item, "company", "")
    email = getattr(item, "email", "")
    phone = getattr(item, "phone", "")
    heading = " | ".join(part for part in (name, company) if part)
    details = " | ".join(part for part in (email, phone) if part)
    return f"""<div class="entry">
  <div class="entry-heading">
    <span>{escape(heading)}</span>
    <span class="muted">{escape(details)}</span>
  </div>
</div>"""


def render_link_item(item: object) -> str:
    label = getattr(item, "label", "") or getattr(item, "link", "")
    link = getattr(item, "link", "")
    href = escape(link, quote=True)
    return f'<p><a href="{href}" rel="noreferrer">{escape(label)}</a></p>' if link else ""


def render_string_list(items: list[str]) -> str:
    values = [escape(str(item)) for item in items if str(item)]
    return f"<ul>{''.join(f'<li>{item}</li>' for item in values)}</ul>" if values else ""


def format_generic_item(item: object) -> str:
    if isinstance(item, str):
        return item
    if hasattr(item, "model_dump"):
        values = item.model_dump(mode="json").values()
        return " | ".join(str(value) for value in values if value not in ("", None, []))
    return str(item)


def format_date_range(start: str, end: str) -> str:
    if start and end:
        return f"{start} - {end}"
    return start or end


def sanitize_css_color(value: str) -> str:
    if re.fullmatch(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?", value or ""):
        return value
    if re.fullmatch(r"[a-zA-Z]+", value or ""):
        return value
    return "#000000"


def sanitize_font_family(value: str) -> str:
    sanitized = re.sub(r"[^a-zA-Z0-9 ,._-]", "", value or "")
    return sanitized.strip() or "Arial"
