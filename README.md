# 🏠 Stay Rentals — Accommodation Rental Platform

> A full-stack accommodation rental platform built to solve a real problem — helping students and working professionals find verified stays in unfamiliar cities, with AI-powered search, real-time chat, and secure booking.

🌐 **Live Demo:** [stay-rentals.vercel.app](https://stay-rentals.vercel.app/login)  

---

## 📌 The Problem

Moving to a new city — especially as a student or a young professional — is stressful. Finding affordable, trustworthy accommodation involves scrolling through unreliable listings, struggling to communicate with owners, and often making decisions without ever visiting the place.

This platform was built from personal experience after facing exactly this situation while relocating to Kochi. The goal was to build something that actually solves it — with AI-driven discovery, direct owner communication, map-based exploration, and secure advance booking.

---

## ✨ Key Features

### 🤖 AI-Powered Search & Recommendations
- Natural language property search — users can type *"2BHK near IT park under ₹10,000"* and get relevant results
- RAG-based recommendation engine using **ChromaDB**, **sentence transformers**, and **Groq (LLaMA 3.3 70B)**
- AI-powered listing comparisons to help users make informed decisions
- Asynchronous ChromaDB sync via **Celery** to keep vector embeddings up to date

### 💬 Real-Time Chat
- Bidirectional chat between tenants and property listers
- Built with **Django Channels**, **WebSockets**, and **Redis** via **Daphne ASGI server**
- All messages **encrypted at rest** using Fernet symmetric encryption

### 🗺️ Map-Based Property Discovery
- Interactive property maps powered by **Leaflet.js** and **OpenStreetMap**
- Automatic geocoding of property addresses to coordinates
- Live filters and marker-based navigation for intuitive browsing

### 🔐 Comprehensive Authentication
- **JWT** with HttpOnly cookies for stateless, XSS-safe sessions
- **Google OAuth** for one-click sign-in
- **OTP email verification** on registration
- **TOTP-based MFA** (Google Authenticator compatible)
- **Role-Based Access Control (RBAC)** — Users, Listers, and Admins have distinct permissions

### 📅 Booking & Scheduling
- Users can send **visit schedule requests** to listers for in-person property tours
- **Advance payment** gateway integration to reserve a property
- Once an advance is paid, the listing is marked unavailable — preventing double bookings

### 🛡️ Admin Panel
- Full control over user management and KYC document review
- Property moderation and listing approvals
- Visit schedule oversight and platform-wide analytics

### 📎 Media & Notifications
- Property images stored and served via **Cloudinary**
- Push notifications via **Firebase Cloud Messaging**
- Email dispatching (OTP, confirmations) handled asynchronously via **Celery + Redis**

---

## 🏗️ Architecture

This platform follows a **microservices architecture** with two independent backend services:

```
┌─────────────────────────────┐       ┌──────────────────────────────┐
│     Django Backend Service  │       │    FastAPI AI/Chatbot Service │
│                             │       │                              │
│  - Authentication (JWT,     │       │  - RAG Search Engine         │
│    OAuth, MFA, OTP)         │       │  - AI Recommendations        │
│  - Property Management      │       │  - FAQ Chatbot               │
│  - Real-time Chat           │◄─────►│  - ChromaDB Vector Store     │
│    (WebSockets/Channels)    │       │  - Groq LLM Integration      │
│  - Bookings & Payments      │       │  - Sentence Transformers     │
│  - Admin Panel              │       │                              │
│  - Notifications (Firebase) │       └──────────────────────────────┘
│  - Celery Background Tasks  │
└─────────────────────────────┘
             ▲
             │
     ┌───────┴────────┐
     │  Nginx Reverse │
     │     Proxy      │
     │                │
     │ - WS Upgrade   │
     │ - Static Files │
     │ - Upstream     │
     │   Routing      │
     └───────┬────────┘
             │
     ┌───────┴────────┐
     │ React Frontend │
     │  (Vercel CDN)  │
     └────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technologies |
|---|---|
| **Frontend** | React.js, Leaflet.js |
| **Backend (Core)** | Django, Django REST Framework |
| **Backend (AI)** | FastAPI |
| **Real-time** | Django Channels, WebSockets, Daphne ASGI |
| **AI / ML** | ChromaDB, Sentence Transformers, Groq (LLaMA 3.3 70B) |
| **Database** | PostgreSQL |
| **Cache / Queue** | Redis, Celery |
| **Auth** | JWT (HttpOnly cookies), Google OAuth, TOTP MFA, OTP Email |
| **Media Storage** | Cloudinary |
| **Maps** | OpenStreetMap, Leaflet.js |
| **Notifications** | Firebase Cloud Messaging |
| **DevOps** | Docker, Docker Compose, Nginx |
| **Deployment** | Vercel (Frontend) |

---

## 📁 Project Structure

```
.
├── backend_service/               # Django Core Service
│   ├── auth_app/                  # JWT, OAuth, MFA, OTP
│   ├── chat_app/                  # WebSocket chat + encryption
│   ├── chatbot_app/               # Chatbot relay to FastAPI
│   ├── property_app/              # Listings, geocoding, filters
│   ├── payments_app/              # Advance payment & property locking
│   ├── notifications_app/         # Firebase push notifications
│   ├── profile_app/               # User profiles
│   ├── adminpanel/                # KYC, moderation, analytics
│   ├── nginx/nginx.conf           # Reverse proxy config
│   └── docker-compose.yml
│
└── chatbot_service/               # FastAPI AI Service
    ├── rag/                       # RAG pipeline
    │   ├── chain.py               # LLM chain setup
    │   ├── embeddings.py          # Sentence transformer embeddings
    │   ├── property_chain.py      # Property-specific RAG
    │   └── property_embeddings.py # Property vector ingestion
    ├── routers/
    │   ├── faq_bot.py             # FAQ chatbot endpoint
    │   └── recommendations.py     # AI recommendation endpoint
    ├── docs/                      # RAG knowledge base (FAQ, policies)
    └── chroma_db/                 # Persisted vector store
```

---

## 🚀 Getting Started

### Prerequisites

- Docker & Docker Compose
- Node.js (for frontend)
- A Groq API key ([console.groq.com](https://console.groq.com))
- Cloudinary account
- Firebase project (for push notifications)
- Google OAuth credentials

### 1. Clone the Repository

```bash
git clone https://github.com/prince-0303/stay-rentals.git
cd stay-rentals
```

### 2. Configure Environment Variables

Create a `.env` file inside `backend_service/`:

```env
SECRET_KEY=your_django_secret_key
DEBUG=False
DATABASE_URL=postgresql://user:password@db:5432/stayrentals

# Auth
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret

# Cloudinary
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# Redis
REDIS_URL=redis://redis:6379/0

# Email
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password

# Payment Gateway
PAYMENT_API_KEY=your_payment_key
```

Create a `.env` inside `chatbot_service/`:

```env
GROQ_API_KEY=your_groq_api_key
```

### 3. Run with Docker Compose

```bash
cd backend_service
docker-compose up --build
```

This starts:
- Django backend (port 8000)
- FastAPI chatbot service (port 8001)
- PostgreSQL database
- Redis instance
- Celery worker
- Nginx reverse proxy (port 80)

### 4. Run Frontend

```bash
cd frontend
npm install
npm run dev
```

---

## 🧠 How the AI Search Works

```
User types: "affordable 1BHK near Infopark Kochi"
        │
        ▼
FastAPI /recommendations endpoint
        │
        ▼
Sentence Transformer encodes query → embedding vector
        │
        ▼
ChromaDB similarity search over indexed property listings
        │
        ▼
Top-k matching listings retrieved
        │
        ▼
Groq LLaMA 3.3 70B generates natural language comparison & recommendation
        │
        ▼
Results returned to React frontend with ranked listings
```

Property data is synced into ChromaDB asynchronously via a **Celery periodic task** so the vector store always reflects the latest listings without blocking the main API.

---

## 🔒 Security Highlights

- JWT stored in **HttpOnly cookies** — not localStorage, protected against XSS
- Chat messages **encrypted at rest** with Fernet symmetric encryption
- **TOTP-based MFA** support for accounts requiring higher security
- **RBAC** enforced at the API layer for all role-sensitive endpoints
- **KYC document verification** required for property listers before listings go live

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

---

## 👤 Author

**Prince Biju**  
Python Django Developer  
📧 princebiju.dev@gmail.com  
💼 [LinkedIn](https://www.linkedin.com/in/princebiju/)
