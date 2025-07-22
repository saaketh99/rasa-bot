# Rasa Chatbot with Next.js Frontend

This is a conversational AI chatbot built with Rasa and a modern Next.js frontend for order management and tracking.

## Project Structure

```
rasa-bot-main/
├── actions/           # Rasa custom actions
├── app/              # FastAPI backend
├── data/             # Rasa training data
├── frontend/         # Next.js frontend
├── config.yml        # Rasa configuration
├── domain.yml        # Rasa domain
├── endpoints.yml     # Rasa endpoints
└── credentials.yml   # Rasa credentials
```

## Features

- **Order Tracking**: Track orders by ID or invoice number
- **Customer Queries**: Get orders for specific customers
- **Route Analysis**: Find orders between locations
- **Status Filtering**: Filter orders by delivery status
- **Date Range Queries**: Get orders within date ranges
- **Modern UI**: Beautiful chat interface with conversation history

## Prerequisites

- **Docker** and **Docker Compose** (recommended)
- OR **Python 3.8-3.10** and **Node.js 18+**

## Quick Start (Working Setup)

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd rasa-bot-main
   ```

2. **Install dependencies**
   ```bash
   pip install flask flask-cors requests
   cd frontend
   npm install --legacy-peer-deps
   cd ..
   ```

3. **Start all services**
   ```bash
   # Windows
   start.bat
   
   # PowerShell
   .\start.ps1
   
   # Or manually:
   # Terminal 1: python mock_rasa_server.py
   # Terminal 2: uvicorn app.main:app --reload --port 8000
   # Terminal 3: cd frontend && npm run dev
   ```

4. **Access the application**
   - Frontend: http://localhost:3000
   - Mock Rasa API: http://localhost:5005
   - FastAPI: http://localhost:8000

5. **Test the setup**
   ```bash
   python test_setup.py
   ```

## Manual Setup (Alternative)

### 1. Python Environment Setup

**Option A: Use Python 3.10 (Recommended)**
```bash
# Install Python 3.10 from python.org
# Create virtual environment
python3.10 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

**Option B: Use Conda**
```bash
conda create -n rasa-bot python=3.10
conda activate rasa-bot
```

### 2. Install Python Dependencies
```bash
pip install -r requirements.txt
```

### 3. Install Frontend Dependencies
```bash
cd frontend
npm install --legacy-peer-deps
cd ..
```

### 4. Train Rasa Model
```bash
rasa train
```

## Running the Application

### Method 1: Docker (Easiest)
```bash
docker-compose up --build
```

### Method 2: Manual (Multiple Terminals)

**Terminal 1: Rasa Server**
```bash
rasa run --enable-api --cors "*" --debug
```

**Terminal 2: Rasa Actions Server**
```bash
rasa run actions --debug
```

**Terminal 3: FastAPI Backend**
```bash
uvicorn app.main:app --reload --port 8000
```

**Terminal 4: Frontend**
```bash
cd frontend
npm run dev
```

## Services and Ports

- **Frontend**: http://localhost:3000
- **Rasa Server**: http://localhost:5005
- **Rasa Actions**: http://localhost:5055
- **FastAPI Backend**: http://localhost:8000

## API Endpoints

### FastAPI Backend
- `POST /conversations` - Create new conversation
- `POST /conversations/{id}/messages` - Add message to conversation
- `GET /conversations` - List all conversations
- `GET /conversations/{id}` - Get conversation by ID

### Rasa Webhook
- `POST /webhooks/rest/webhook` - Send message to Rasa bot

## Usage Examples

### Chat with the Bot
1. Open http://localhost:3000
2. Start a new conversation
3. Ask questions like:
   - "Show me orders from Wakefit between 2024-12-01 and 2024-12-31"
   - "Track order WKFT000123"
   - "Get all orders from Hyderabad to Vizag"
   - "Show delivered orders"

### Supported Intents
- Order tracking by ID
- Order tracking by invoice
- Customer-specific orders
- Route-based queries
- Status filtering
- Date range queries
- TAT analysis

## Troubleshooting

### Python Version Issues
If you get Python version errors:
1. Use Python 3.8-3.10 (Rasa doesn't support 3.12 yet)
2. Use Docker setup (recommended)

### Frontend Issues
If npm install fails:
```bash
npm install --legacy-peer-deps
```

### Rasa Training Issues
If model training fails:
```bash
rasa train --force
```

### Database Connection
The project uses MongoDB Atlas. Ensure you have internet connection.

## Development

### Adding New Actions
1. Edit `actions/actions.py`
2. Add new action class
3. Update `domain.yml`
4. Retrain model: `rasa train`

### Adding New Intents
1. Add examples in `data/nlu.yml`
2. Add intent in `domain.yml`
3. Add stories in `data/stories.yml`
4. Retrain model: `rasa train`

### Frontend Customization
1. Edit components in `frontend/components/`
2. Modify API calls in `frontend/app/page.tsx`
3. Update styles in `frontend/app/globals.css`

## Environment Variables

- `MONGODB_URL`: MongoDB connection string
- `NEXT_PUBLIC_API_URL`: Frontend API URL

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

This project is licensed under the MIT License. 