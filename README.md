# Canny

A social platform for sharing what you're learning - GoodReads meets LinkedIn.

## Project Structure
```
├── canny-frontend/    # React frontend
├── canny-backend/     # Express API
└── README.md
```

## Setup

### Database
```bash
createdb canny
psql canny < schema.sql
```

### Backend
```bash
cd canny-backend
npm install
cp .env.example .env  # Edit with your settings
node server.js
```

### Frontend
```bash
cd canny-frontend
npm install
npm start
```

## Tech Stack

- **Frontend**: React, Tailwind CSS, Lucide Icons
- **Backend**: Node.js, Express
- **Database**: PostgreSQL
- **Auth**: JWT
