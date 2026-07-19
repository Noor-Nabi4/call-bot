"""Business information included in the system prompt."""

from __future__ import annotations


def business_information(business_name: str) -> str:
    return (
        f"Business name: {business_name}.\n"
        "Only share business facts that appear in these instructions. "
        "If a caller asks for details that are not listed here, say you do not "
        "have that information and offer to take a message or suggest another "
        "way they can get help. Never invent hours, prices, policies, "
        "addresses, or availability."
    )
