# 🏠 NestQuest — Real Estate Platform

A full-stack Django real estate platform with an AI-powered chat assistant that lets users find, filter, and compare properties using natural language.

---


## 📋 Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Environment Variables](#environment-variables)
- [AI Chat System](#ai-chat-system)
- [How Filtering Works](#how-filtering-works)

---

## ✨ Features

- 🔍 **Property listings** — browse, filter, and search properties with pagination
- 🤖 **AI Chat Assistant** — find properties using natural language
- 📊 **Aggregate queries** — ask for average price, total count, min/max values
- ⚖️ **Property comparison** — compare 2–4 properties side by side
- 📝 **Blog** — real estate articles and guides
- 👤 **User accounts** — register, login, manage profile and listings
- 🛠️ **Admin panel** — property approval workflow, contact messages, user management

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 6.0 |
| Database | PostgreSQL |
| AI | Groq API (`llama-3.3-70b-versatile`) |
| Admin UI | Jazzmin |
| Images | Pillow |
| Config | python-decouple |

---

## 📁 Project Structure

```
Real-Estate-App/
├── application/          # Django project settings and URLs
├── accounts/             # User registration, login, profile
├── properties/           # Property listings, forms, views
│   ├── ai/               # AI chat service (modular)
│   │   ├── constants.py      # Hard caps: MAX_LIMIT, MAX_CONDITIONS...
│   │   ├── prompts.py        # System prompts for Groq
│   │   ├── groq_client.py    # Groq API client with retry
│   │   ├── validators.py     # Condition and sort validation
│   │   ├── filters.py        # Django Q() filter builder
│   │   ├── parser.py         # AI response parsing per mode
│   │   ├── comparison.py     # Property comparison logic
│   │   ├── utils.py          # Message building utilities
│   │   └── __init__.py       # Public API
├── core/                 # Home, about, contact, blog
└── templates/            # HTML templates
```

---

## ⚙️ Installation

### 1. Clone the repository
```bash
git clone https://github.com/ana003m/real-estate-app.git
cd real-estate-app
```

### 2. Create and activate a virtual environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment variables
Create a `.env` file in the root directory.

### 5. Run migrations
```bash
python manage.py migrate
```

### 6. Create a superuser
```bash
python manage.py createsuperuser
```

### 7. Run the development server
```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000/`

---

## 🔐 Environment Variables

Create a `.env` file in the root directory:

```env
SECRET_KEY=your-django-secret-key
DEBUG=True
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.3-70b-versatile
DB_NAME=your-database-name
DB_USER=your-database-user
DB_PASSWORD=your-database-password
DB_HOST=localhost
DB_PORT=5432
```

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` for development, `False` for production |
| `GROQ_API_KEY` | API key from [console.groq.com](https://console.groq.com) |
| `GROQ_MODEL` | Groq model to use (default: `llama-3.3-70b-versatile`) |
| `DB_NAME` | PostgreSQL database name |
| `DB_USER` | PostgreSQL username |
| `DB_PASSWORD` | PostgreSQL password |
| `DB_HOST` | Database host (default: `localhost`) |
| `DB_PORT` | Database port (default: `5432`) |

> ⚠️ Without `GROQ_API_KEY` the AI chat will not work, but the rest of the app functions normally.

---

## 🤖 AI Chat System

The AI chat is built around a pipeline of modular components in `properties/ai/`:

### How it works

```
User message
     ↓
detect_intent()         — compare specific properties or filter?
     ↓
call_groq()             — sends message + SYSTEM_PROMPT to Groq API
     ↓
parse_ai_response()     — validates and routes to per-mode parser
     ↓
apply_filters()         — builds Django Q() objects, queries the database
     ↓
JsonResponse            — returns properties + message to frontend
```

### Supported modes

| Mode | Triggered when | Example |
|---|---|---|
| `filter` | User wants to find properties | "show me apartments under $500,000" |
| `aggregate` | User wants a statistic | "what is the average price of villas?" |
| `question` | User asks about a specific property | "how many bathrooms does the cheapest house have?" |
| `chat` | General conversation | "what should I look for when buying a home?" |
| `compare` | User names 2+ properties | "compare Villa #1 and Villa #2" |

### Security caps

To prevent abuse and hallucinated large values:

| Cap | Value |
|---|---|
| `MAX_CONDITIONS` | 10 |
| `MAX_SORTS` | 3 |
| `MAX_LIMIT` | 50 |
| `MAX_CHAT_HISTORY` | 20 |

---

## 🔍 How Filtering Works

1. **Groq** receives the user message and the `SYSTEM_PROMPT` which describes all available fields and operators. It returns a structured JSON response:

```json
{
  "mode": "filter",
  "conditions": [
    {"field": "property_type", "op": "eq",        "value": "apartment"},
    {"field": "price",         "op": "lte",       "value": 500000},
    {"field": "city",          "op": "icontains", "value": "Chicago"}
  ],
  "sort": [{"field": "price", "direction": "asc"}],
  "limit": null,
  "message": "Apartments in Chicago under $500,000 (lowest price first)."
}
```

2. **`parse_ai_response()`** validates every condition against whitelisted fields and operators. Invalid or malformed conditions are silently dropped.

3. **`apply_filters()`** builds a single Django `Q()` object and applies it in one `.filter()` call:

```python
# Single efficient database query
queryset.filter(
    Q(property_type="apartment") &
    Q(price__lte=500000) &
    Q(city__icontains="Chicago")
)
```

### Supported filter operators

| Operator | Meaning | Example |
|---|---|---|
| `eq` | equals | `property_type = "apartment"` |
| `neq` | not equals | `property_type ≠ "apartment"` |
| `lt` / `lte` | less than / less or equal | `price ≤ 500000` |
| `gt` / `gte` | greater than / greater or equal | `bedrooms ≥ 3` |
| `icontains` | case-insensitive contains | `city contains "Chicago"` |
| `not_icontains` | does not contain | `city not contains "Chicago"` |
| `in` | value is in list | `property_type in ["apartment", "house"]` |
| `any_of` | has any of the features | `features: pool or garage` |
| `none_of` | has none of the features | `features: no pool, no garage` |

## 👩‍💻 Authors

| Name | Index  |
|---|--------|
| Ana Manasieva | 221200 |
| Nela Nikolova | 221045 |
| Iva Kostadinova | 221124 |
| Aleksandra Krusharoska | 221005 |
| Sara Dobrevska | 221125 |

---
## 📄 License
This project was developed for educational purposes as part of a university course assignment. It is not intended for commercial use.