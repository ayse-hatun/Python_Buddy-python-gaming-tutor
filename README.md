# Python Buddy 🐍🎮

A gamified web application for learning Python through interactive quests, code duels, live challenges, and an AI tutor.

## Features

- 🗺️ **Interactive Quest Map**: Progress through levels covering fundamentals, numbers, strings, logic, loops, lists, functions, and boss fights.
- ❤️ **Hearts & Streak System**: Answer conceptual quizzes with instant feedback and 3-heart life mechanic.
- ⚔️ **Code Duels**: Write real Python code in the browser with server-side validation against expected outputs.
- 💬 **AI Coding Buddy**: Chat with an AI tutor in multiple modes (Learn, Practice, Quiz, Debug).
- 🏅 **Badges & XP**: Earn XP, unlock titles from Newbie to Legend, and collect badges.

## Quick Start

### 1. Clone the repository
```bash
git clone https://github.com/ayse-hatun/python-gaming-tutor.git
cd python-gaming-tutor
```

### 2. Create and activate a virtual environment
```bash
python -m venv .venv

# Windows:
.venv\Scripts\activate

# macOS / Linux:
source .venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure environment variables
Copy `.env.example` to `.env` and configure your API key (Gemini or OpenRouter):
```bash
cp .env.example .env
```
Edit `.env`:
```env
GEMINI_API_KEY="your-api-key"
```

### 5. Run the application
```bash
python main.py
```
Open your browser at [http://127.0.0.1:8000](http://127.0.0.1:8000).
