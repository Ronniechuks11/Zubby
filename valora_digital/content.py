"""Page content for the Valora Digital landing page.

Keeping the copy in one place means the repeated blocks (services, process
steps, work cards, ...) are rendered from data by the templates, and a
copywriter can edit text here without touching markup.

Items flagged PLACEHOLDER are illustrative and must be replaced with verified
client work and results before the site goes live.
"""
from __future__ import annotations

from markupsafe import Markup

SITE = {
    "name": "Valora Digital",
    "title": "Valora Digital — Make Your Brand Remembered",
    "description": (
        "Valora Digital is a digital marketing and media agency helping brands get "
        "remembered through strategy, content and performance-driven Meta advertising."
    ),
    "og_title": "Valora Digital — Make Your Brand Remembered",
    "og_description": "Sharp strategy, scroll-stopping content and Meta ads built to convert.",
    "theme_color": "#6B0000",
    "parent": "Defcom Global Holdings",
}

# The "V" brand mark, shared by the nav, loader, hero echoes and footer.
LOGO_PATH = "M0 112H103L173 241L285 33H322L173 309L83 144H54L173 361L368 0H405L173 429Z"

NAV_LINKS = [
    {"label": "Services", "anchor": "services"},
    {"label": "Meta Ads", "anchor": "meta-ads"},
    {"label": "Process", "anchor": "process"},
    {"label": "Work", "anchor": "work"},
    {"label": "Contact", "anchor": "contact"},
]

FOOTER_LINKS = [
    {"label": "Services", "anchor": "services"},
    {"label": "Meta Ads", "anchor": "meta-ads"},
    {"label": "Our process", "anchor": "process"},
    {"label": "Selected work", "anchor": "work"},
    {"label": "Start a campaign", "anchor": "contact"},
    {"label": "Back to top ↑", "anchor": "home"},
]

MARQUEE = [
    "Meta Ads",
    "Social Media",
    "Content & Video",
    "Brand Strategy",
    "Media",
    "Performance",
]

SERVICES = [
    {
        "number": "01",
        "category": "PERFORMANCE",
        "title": "Meta Ads",
        "body": "Campaigns engineered to turn attention into action, with sharper targeting and creative that earns the click.",
    },
    {
        "number": "02",
        "category": "COMMUNITY",
        "title": "Social Media Management",
        "body": "A consistent, considered presence that gives your audience a reason to stop, connect and come back.",
    },
    {
        "number": "03",
        "category": "PRODUCTION",
        "title": "Content & Video Production",
        "body": "Distinctive visual stories and short-form content designed for the way people actually consume media.",
    },
    {
        "number": "04",
        "category": "POSITIONING",
        "title": "Brand Strategy & Identity",
        "body": "Clear positioning and a recognisable identity that make the right people understand why you matter.",
    },
    {
        "number": "05",
        "category": "GROWTH",
        "title": "Performance Marketing",
        "body": "Data-led decisions across the journey, continuously improving what works and cutting what doesn't.",
    },
    {
        "number": "06",
        "category": "CAMPAIGNS",
        "title": "Media & Creative Campaigns",
        "body": "Big ideas with a clear purpose, built to travel across channels and create measurable momentum.",
    },
]

ADS_CHECKLIST = [
    "Audience research & precision targeting",
    "Creative testing and campaign optimisation",
    "Retargeting that brings warm leads back",
    "Pixel / Conversions API tracking support",
    "Clear weekly reporting and next steps",
]

# Illustrative phone mock-up. The stylesheet gives posts 1-3 their own artwork
# (by position); the template repeats the first post so the loop scrolls cleanly.
FEED_POSTS = [
    {
        "headline": "Make room for what moves you.",
        "body": "Discover the collection made for your next chapter.",
    },
    {
        "headline": "Built around your everyday.",
        "body": "Thoughtful details. A different kind of essential.",
    },
    {
        "headline": "Find your new favourite.",
        "body": "Explore the edit and discover what's next.",
    },
]

# PLACEHOLDER: illustrative figures shown on the phone mock-up.
METRIC_CHIPS = [
    {"css": "one", "label": "Campaign reach", "value": "128.4K", "delta": "↗ 18.6%"},
    {"css": "two", "label": "Cost per lead", "value": "₦1,240", "delta": "↓ 12%"},
]

FUNNEL = [
    {"step": "01 / Discover", "label": "Reach"},
    {"step": "02 / Engage", "label": "Clicks"},
    {"step": "03 / Connect", "label": "Leads"},
    {"step": "04 / Convert", "label": "Sales"},
]

PROCESS = [
    {
        "number": "01",
        "title": "Discover",
        "body": "We get close to your business, audience and ambition. First, we find the opportunity worth owning.",
        "word": "Listen.",
    },
    {
        "number": "02",
        "title": "Craft",
        "body": "We turn insight into a focused strategy, clear creative direction and messaging people can recognise.",
        "word": "Define.",
    },
    {
        "number": "03",
        "title": "Launch",
        "body": "We bring the work to life, put it in front of the right audience and measure the signals that matter.",
        "word": "Move.",
    },
    {
        "number": "04",
        "title": "Scale",
        "body": "We learn from real performance, refine the details and build on momentum without losing the brand.",
        "word": "Grow.",
    },
]

# PLACEHOLDER: replace with real, approved client projects.
WORK = [
    {
        "art": "art-one",
        "kind": "01 / Brand campaign",
        "title": "Form / Function",
        "services": "Positioning · Creative direction · Social",
    },
    {
        "art": "art-two",
        "kind": "02 / Digital launch",
        "title": "A New Perspective",
        "services": "Content · Campaign strategy",
    },
    {
        "art": "art-three",
        "kind": "03 / Growth campaign",
        "title": "Make It Matter",
        "services": "Meta Ads · Performance creative · Optimisation",
    },
]

# PLACEHOLDER: illustrative performance metrics; replace with verified client results.
STATS = [
    {"value": "3.8", "suffix": "×", "label": "Average ROAS / Placeholder"},
    {"value": "42", "suffix": "%", "label": "Lower cost per lead / Placeholder"},
    {"value": "1.2", "suffix": "M+", "label": "People reached / Placeholder"},
]

# Single source of truth: rendered in the <select> *and* used to validate it.
BUDGET_OPTIONS = [
    "Under ₦100,000",
    "₦100,000 – ₦300,000",
    "₦300,000 – ₦750,000",
    "₦750,000 – ₦1,500,000",
    "₦1,500,000+",
    "Let's discuss",
]

# Footer social icons.  ``icon`` is trusted, static SVG markup (hence Markup).
SOCIALS = [
    {
        "key": "instagram",
        "label": "Instagram",
        "icon": Markup(
            '<rect x="3" y="3" width="18" height="18" rx="5"/>'
            '<circle cx="12" cy="12" r="4"/><path d="M17.5 6.5h.01"/>'
        ),
    },
    {
        "key": "facebook",
        "label": "Facebook",
        "icon": Markup('<path d="M14 8h4V4h-4a5 5 0 0 0-5 5v3H6v4h3v5h4v-5h4l1-4h-5V9a1 1 0 0 1 1-1z"/>'),
    },
    {
        "key": "tiktok",
        "label": "TikTok",
        "icon": Markup('<path d="M14 4v10.5a4.5 4.5 0 1 1-4-4.47"/><path d="M14 4c.5 3 2.5 5 5 5"/>'),
    },
    {
        "key": "linkedin",
        "label": "LinkedIn",
        "icon": Markup('<path d="M5 9v10M5 5v.01M10 19v-6a4 4 0 0 1 8 0v6M10 9v10"/>'),
    },
    {
        "key": "x",
        "label": "X",
        "icon": Markup('<path d="m5 4 14 16M19 4 5 20"/>'),
    },
    {
        "key": "whatsapp",  # URL is built from the WHATSAPP_NUMBER setting
        "label": "WhatsApp",
        "icon": Markup(
            '<path d="M20 11.5a8 8 0 0 1-12 7L4 20l1.5-4A8 8 0 1 1 20 11.5z"/>'
            '<path d="M9 9c.5 2 2 3.5 4 4l1-1 2 1c-.5 2-2 2-3 2-3-1-5-3-6-6 0-1 0-2 2-3l1 2z"/>'
        ),
    },
]
