# Nu Age — Frontend

> The cross-platform desktop and mobile client for Nu Age, built with Flet (Python).

**Stack:** Python · Flet · REST API (Nu Age Backend)

---

## Table of Contents

- [Overview](#overview)
- [Why Flet](#why-flet)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Environment Variables](#environment-variables)
  - [Running Locally](#running-locally)
- [Building for Distribution](#building-for-distribution)
  - [Windows](#windows)
  - [Android](#android)
- [App Structure](#app-structure)
- [State Management](#state-management)
- [Connecting to the Backend](#connecting-to-the-backend)
- [Contributing](#contributing)

---

## Overview

The Nu Age frontend is a Python-based cross-platform application built with **Flet**, delivering a consistent, responsive experience on both desktop (Windows) and mobile (Android). It communicates entirely with the Nu Age backend via REST API and is designed to remain functional in low-connectivity environments through local caching and offline-first patterns.

Key surfaces:

- **Course Dashboard** — module progression, visual milestones, completion tracking
- **AI Self-Study Hub** — practice quizzes, concept breakdowns, AI-generated lessons
- **Community & Chat** — direct messaging, course-specific channels, friend system
- **Leaderboard** — live course rankings by score and progression speed
- **Certificate Viewer** — view, download, and share completed course certificates
- **Profile** — streak tracking, academic interests, enrolled courses

---

## Why Flet

Flet allows Nu Age to ship one Python codebase across Windows desktop and Android with a near-native feel, without maintaining separate React Native or Flutter codebases. For a solo-architected platform targeting students in bandwidth-constrained environments, this is the right tradeoff.

---

## Getting Started

### Prerequisites

- Python 3.11+
- pip
- A running instance of the [Nu Age Backend](https://github.com/demnzy/nu-age-backend) (local or remote)

### Environment Variables

Create a `.env` file in the project root:

```env
API_BASE_URL=http://localhost:8000
# For production:
# API_BASE_URL=https://your-ec2-domain.com
```

### Running Locally

```bash
# 1. Clone the repo
git clone https://github.com/demnzy/nu-age-frontend.git
cd nu-age-frontend

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up your .env file
cp .env.example .env
# Set API_BASE_URL to your backend address

# 5. Run the app
flet run main.py
```

The app will launch as a native desktop window. To run in the browser during development:

```bash
flet run main.py --web --port 8080
```

---

## Building for Distribution

### Windows

```bash
# Install the Flet CLI if not already installed
pip install flet[build]

# Build a standalone Windows executable
flet build windows
```

The output will be in `build/windows/`. This produces a self-contained `.exe` that does not require Python to be installed on the target machine.

### Android

```bash
# Build an Android APK
flet build apk
```

Requirements for Android build:
- Android SDK installed and `ANDROID_HOME` set in your environment
- Java 11+ available on your PATH

The output `.apk` will be in `build/apk/`. For Play Store distribution, build an `.aab` instead:

```bash
flet build aab
```

> Note: For production Android releases, configure signing keys in `flet_build.yaml` before building.

---

## App Structure

```
nu-age-frontend/
│
├── main.py                  # App entry point, routing
│
├── pages/                   # Full-page views
│   ├── login.py
│   ├── register.py
│   ├── dashboard.py
│   ├── course_view.py
│   ├── study_hub.py
│   ├── chat.py
│   ├── leaderboard.py
│   ├── certificates.py
│   └── profile.py
│
├── components/              # Reusable UI components
│   ├── navbar.py
│   ├── course_card.py
│   ├── progress_bar.py
│   ├── quiz_card.py
│   ├── message_bubble.py
│   └── stat_chip.py
│
├── services/                # API communication layer
│   ├── api_client.py        # Base HTTP client (requests / httpx)
│   ├── auth_service.py
│   ├── course_service.py
│   ├── chat_service.py
│   └── certificate_service.py
│
├── state/                   # App-level state management
│   └── app_state.py
│
├── utils/                   # Helpers
│   ├── storage.py           # Local token and cache storage
│   ├── constants.py
│   └── validators.py
│
├── assets/                  # Static assets (icons, fonts, images)
│
├── .env.example
├── .gitignore
├── requirements.txt
├── flet_build.yaml          # Flet build configuration
└── README.md
```

---

## State Management

Nu Age's frontend uses a centralised `AppState` class passed through Flet's page session. This holds:

- Authenticated user object and JWT token
- Currently active course and module
- Cached leaderboard and chat data
- UI theme and preferences

Components read from and write to `AppState` rather than managing local state independently, keeping the data flow predictable across page navigations.

Token persistence between sessions is handled via Flet's `page.client_storage`, which maps to the platform's native secure storage (Windows Credential Manager on desktop, Android Keystore on mobile).

---

## Connecting to the Backend

All API calls go through `services/api_client.py`, which:

- Attaches the JWT `Authorization` header to every authenticated request
- Handles token refresh transparently when a 401 is received
- Raises structured exceptions that pages can catch and display as user-friendly error states

To point the frontend at a different backend (local vs. production), update `API_BASE_URL` in your `.env` file. No code changes needed.

---

## Contributing

Nu Age is in active student beta. If you're contributing:

1. Fork the repo and create a feature branch — `git checkout -b feature/your-feature`
2. Keep components in `components/` and pages in `pages/` — don't mix layout and logic
3. All API calls must go through the `services/` layer, never directly from a page
4. Test on both desktop and mobile layouts before opening a pull request
5. Open a pull request with a clear description of what changed and why

For bugs or feature requests, open an issue on GitHub.

---

Built by [Oluwatobiloba (Daniel) Davies](https://github.com/demnzy) · [LinkedIn](https://linkedin.com/in/oluwatobiloba-davies)
