<<<<<<< HEAD
# 🛍 Food Bot — Oziq-ovqat Sotish Telegram Boti

Python 3.11+ · python-telegram-bot v21 · SQLAlchemy 2 · aiosqlite

---

## 📁 Loyiha strukturasi

```
food_bot/
├── main.py                  ← Ishga tushurish nuqtasi
├── config.py                ← .env dan sozlamalar
├── requirements.txt
├── .env.example
│
├── db/
│   ├── models.py            ← SQLAlchemy ORM modellari
│   └── session.py           ← Async engine va session
│
├── services/
│   ├── user_service.py      ← Foydalanuvchi CRUD
│   ├── product_service.py   ← Mahsulot/kategoriya CRUD
│   ├── cart_service.py      ← Savatcha operatsiyalari
│   └── order_service.py     ← Buyurtma yaratish va statistika
│
├── handlers/
│   ├── start.py             ← /start, /admin
│   ├── catalog.py           ← Kategoriya → mahsulot ko'rish
│   ├── cart.py              ← Savatcha ko'rish va inline tugmalar
│   ├── checkout.py          ← Buyurtma berish wizardi
│   ├── orders.py            ← Foydalanuvchi buyurtmalar tarixi
│   └── admin/
│       ├── products.py      ← Mahsulot qo'shish/tahrirlash/o'chirish
│       ├── orders.py        ← Admin buyurtmalar paneli
│       ├── broadcast.py     ← Barcha foydalanuvchilarga xabar
│       └── menu.py          ← Statistika, bog'lanish
│
├── keyboards/
│   ├── user_kb.py           ← Foydalanuvchi tugmalari
│   └── admin_kb.py          ← Admin tugmalari
│
└── utils/
    ├── formatters.py        ← Matn formatlash
    └── validators.py        ← Input validation
```

---

## 🚀 O'rnatish (Windows)

### 1. Python 3.11+ o'rnatish
[python.org](https://www.python.org/downloads/) dan yuklab o'rnating.
O'rnatish paytida **"Add Python to PATH"** katagini belgilang.

### 2. Loyihani yuklab oling
```bash
git clone https://github.com/yourname/food_bot.git
cd food_bot
```
yoki ZIP yuklab, papkaga ochin.

### 3. Virtual muhit yaratish
```bash
python -m venv venv
venv\Scripts\activate       # Windows CMD
# yoki:
.\venv\Scripts\Activate.ps1  # PowerShell
```

### 4. Kerakli kutubxonalarni o'rnatish
```bash
pip install -r requirements.txt
```

### 5. `.env` faylini sozlash
```bash
copy .env.example .env
```
`.env` faylini matn muharrirda oching va to'ldiring:
```env
BOT_TOKEN=7123456789:AAF...your_token_here
ADMIN_IDS=123456789         # Telegram user ID (vergul bilan bir nechtasi)
DB_URL=sqlite+aiosqlite:///./food_bot.db
```

> **Telegram user ID topish:** [@userinfobot](https://t.me/userinfobot) ga `/start` yuboring.

### 6. Botni ishga tushirish
```bash
python main.py
```

---

## 🔧 Asosiy buyruqlar

| Buyruq | Tavsif |
|--------|--------|
| `/start` | Botni ishga tushirish |
| `/admin` | Admin panelni ochish |
| `/cancel` | Joriy jarayonni bekor qilish |

---

## 🗄️ PostgreSQLga ko'chirish

1. `requirements.txt`ga qo'shing:
   ```
   asyncpg==0.29.0
   ```
2. `.env` ni o'zgartiring:
   ```env
   DB_URL=postgresql+asyncpg://user:password@localhost:5432/food_bot
   ```
3. PostgreSQL da DB yarating:
   ```sql
   CREATE DATABASE food_bot;
   ```
4. Botni qayta ishga tushiring — jadvallar avtomatik yaratiladi.

---

## 📊 Ma'lumotlar bazasi jadvallari

| Jadval | Tavsif |
|--------|--------|
| `users` | Foydalanuvchilar (tg_id, telefon) |
| `categories` | Kategoriyalar |
| `products` | Mahsulotlar (narx, rasm, tavsif) |
| `carts` | Savatchalar |
| `cart_items` | Savatcha elementlari |
| `orders` | Buyurtmalar (yetkazish, to'lov, status) |
| `order_items` | Buyurtma elementlari (snapshot) |

---

## 🛣 Keyingi bosqichlar (Roadmap)

### 🔵 v1.1 – UX yaxshilash
- [ ] Mahsulotlarga reyting/sharh qo'shish
- [ ] Mahsulot qidirish (`/search`)
- [ ] Foydalanuvchi profilini ko'rish (`/profile`)
- [ ] Savatcaga tezkor qo'shish inline query orqali

### 🟡 v1.2 – To'lov integratsiyasi
- [ ] Payme to'lov tizimi (`python-payme`)
- [ ] Click to'lov tizimi
- [ ] Telegram Stars to'lov

### 🟠 v1.3 – Admin kengaytma
- [ ] Kategoriya tahrirlash/o'chirish
- [ ] Excel eksport (buyurtmalar hisoboti)
- [ ] Maxsus takliflar va chegirmalar
- [ ] Buyurtmaga izoh qo'shish

### 🔴 v2.0 – Arxitektura
- [ ] Redis sessiyasi (ConversationHandler o'rniga)
- [ ] Webhook rejim (polling o'rniga)
- [ ] Docker + docker-compose
- [ ] Alembic migratsiyalar
- [ ] Celery vazifalar navbati (katta broadcast uchun)

---

## ⚠️ Muhim eslatmalar

- Bot birinchi ishga tushganda `food_bot.db` fayl avtomatik yaratiladi
- Admin ID to'g'ri kiritilmasa `/admin` buyrug'i ishlamaydi
- Conversation timeout 10 daqiqa — foydalanuvchi jarayonni tashlab ketsa avtomatik reset
- Barcha xatolar `logging` orqali konsolga chiqariladi va birinchi adminga yuboriladi
=======
# food_bot
RIZO | Kolbasa boti
>>>>>>> 77c3255110aa6662c15ebd11090488073fffccb9
