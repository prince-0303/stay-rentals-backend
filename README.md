# Stay Rentals

A full-stack microservices-based accommodation rental platform built with Django, React.js, and FastAPI. Designed to simplify the process of discovering, booking, and managing rental properties — inspired by the real-world difficulty of finding accommodation when relocating.

---

## Features

- **Map-Based Property Discovery** — Browse and filter properties on an interactive map powered by React Leaflet and OpenStreetMap
- **RAG-Based AI Search** — Natural language property search powered by Groq LLaMA 3.3 70B and ChromaDB
- **Real-Time Encrypted Chat** — Secure messaging between tenants and landlords via WebSockets
- **Advance Payment & Property Locking** — Reserve properties with advance payment to prevent double-booking
- **JWT Authentication with MFA** — Secure login with multi-factor authentication and Google OAuth
- **KYC-Based Admin Moderation** — Identity verification flow for listing approval and trust management
- **Cloudinary Integration** — Optimized media storage and delivery for property images
- **Firebase Notifications** — Real-time push notifications for bookings and messages

---

## Tech Stack

**Backend**
- Django, Django REST Framework
- FastAPI (AI microservice)
- PostgreSQL
- Redis & Celery (async tasks and background jobs)
- WebSockets (real-time communication)
- ChromaDB (vector store for RAG)

**Frontend**
- React.js 19 (Vite)
- React Leaflet + Leaflet.js — interactive maps with OpenStreetMap tiles
- Tailwind CSS
- Recharts (data visualization)
- Axios (HTTP client)
- React Router DOM

**Infrastructure**
- Docker & Docker Compose
- Nginx (reverse proxy)
- AWS EC2 (Mumbai region)
- Cloudflare Tunnel
- Vercel (frontend deployment)

**Integrations**
- Groq LLaMA 3.3 70B (AI search)
- Cloudinary (media)
- Firebase (notifications)
- Google OAuth

---

## Architecture

Stay Rentals follows a microservices architecture with two backend services:

1. **Core Service** (Django/DRF) — Handles authentication, property listings, bookings, payments, and real-time chat
2. **AI Service** (FastAPI) — Manages RAG-based natural language search using ChromaDB and Groq

Both services run in Docker containers behind an Nginx reverse proxy, deployed on AWS EC2.

---

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+
- PostgreSQL
- Redis

### Clone the Repository

```bash
git clone https://github.com/prince-0303/stay-rentals-backend.git
cd stay-rentals-backend
```

### Environment Variables

Create a `.env` file in the root directory. Required variables:

```env
# Django
SECRET_KEY=your_secret_key
DEBUG=False
ALLOWED_HOSTS=your_domain_or_ip

# Database
DATABASE_URL=postgresql://user:password@db:5432/stay_rentals

# Redis
REDIS_URL=redis://redis:6379/0

# Groq
GROQ_API_KEY=your_groq_api_key

# Cloudinary
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret

# Firebase
FIREBASE_CREDENTIALS_JSON=path_to_credentials.json

# Google OAuth
GOOGLE_CLIENT_ID=your_google_client_id
GOOGLE_CLIENT_SECRET=your_google_client_secret
```

### Run with Docker

```bash
docker-compose up --build
```

The backend will be available at `http://localhost:8000`.

---

## Project Structure

```
stay-rentals-backend/
├── core/                   # Main Django application
│   ├── accounts/           # Authentication, MFA, OAuth
│   ├── properties/         # Listings, search, map data
│   ├── bookings/           # Reservations and payments
│   ├── chat/               # WebSocket real-time chat
│   └── moderation/         # KYC and admin tools
├── ai_service/             # FastAPI RAG service
│   ├── search/             # LLM + ChromaDB integration
│   └── embeddings/         # Vector indexing
├── nginx/                  # Nginx config
├── docker-compose.yml
└── README.md
```

---

## Deployment

The project is configured for deployment on AWS EC2 (free tier, Mumbai region) using Docker Compose and Nginx. The frontend is hosted on Vercel. A Cloudflare tunnel handles external access with automated environment variable updates on the frontend via the Vercel API.

> **Note:** Deployment is currently in progress. The backend services run successfully on EC2, but a session persistence issue after login is under investigation — likely related to cookie/CORS configuration across the Cloudflare tunnel and Vercel frontend.

---

## GitHub

- Backend : [github.com/prince-0303/stay-rentals-backend](https://github.com/prince-0303/stay-rentals-backend)
- Frontend: [github.com/prince-0303/stay-rentals-backend](https://github.com/prince-0303/stay-rentals-frontend)
- Profile: [github.com/prince-0303](https://github.com/prince-0303)

---

## License

This project is for portfolio and demonstration purposes.
