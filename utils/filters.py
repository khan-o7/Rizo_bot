"""
Maxsus filtrlar.

PRIVATE_ONLY  — faqat shaxsiy chatda ishlaydi (guruhda jim)
COURIER_GROUP — faqat kuryer guruhida ishlaydi
"""
from __future__ import annotations
from telegram import Update
from telegram.ext import filters


# Faqat shaxsiy chat (private) — guruh/supergroup/channel da ishlamaydi
PRIVATE_ONLY = filters.ChatType.PRIVATE

# Faqat guruh/supergroup
GROUP_ONLY = filters.ChatType.GROUPS
