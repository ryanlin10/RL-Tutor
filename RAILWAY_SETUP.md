# Railway Deployment Setup

## Environment Variables

Add these in Railway Dashboard > Your Service > Variables tab.

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `GROQ_API_KEY` | Your Groq API key for LLM calls | `gsk_xxxxxxxxxxxx` |

### Auto-Provided by Railway

These are automatically injected when you add the corresponding service:

| Variable | Service to Add | Description |
|----------|----------------|-------------|
| `DATABASE_URL` | PostgreSQL | Database connection string |
| `REDIS_URL` | Redis | Rate limiting storage (optional) |
| `PORT` | (automatic) | Port for the web server |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | `dev-secret-key...` | Flask session secret (set a random string for production) |
| `FLASK_DEBUG` | `False` | Enable debug mode |
| `GROQ_MODEL` | `deepseek-r1-distill-llama-70b` | Which Groq model to use |
| `RAG_CHUNK_SIZE` | `1000` | Character size for text chunks |
| `RAG_CHUNK_OVERLAP` | `200` | Overlap between chunks |
| `VECTOR_DB_PATH` | `./data/vector_store` | Vector database location |
| `LECTURE_NOTES_PATH` | `./data/lecture_notes` | Lecture notes directory |

## Step-by-Step Railway Setup

### 1. Create Project
- Go to [railway.app](https://railway.app)
- Click "New Project" > "Deploy from GitHub repo"
- Select your repository

### 2. Add PostgreSQL Database
- In your project, click "New" > "Database" > "Add PostgreSQL"
- Railway automatically injects `DATABASE_URL`

### 3. Add Redis (Optional, for rate limiting)
- Click "New" > "Database" > "Add Redis"  
- Railway automatically injects `REDIS_URL`

### 4. Set Environment Variables
In your main service (not the database), go to Variables tab and add:

```
GROQ_API_KEY=gsk_your_actual_key_here
SECRET_KEY=generate_a_random_64_char_string
```

To generate a secret key, run locally:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 5. Deploy
Railway will automatically:
1. Detect the `nixpacks.toml` configuration
2. Install Node.js and Python dependencies
3. Build the React frontend
4. Copy built files to Flask static folder
5. Start the Gunicorn server

### 6. Get Your URL
- Click on your service
- Go to Settings > Networking > Generate Domain
- Your app will be available at `https://your-app.up.railway.app`

## Groq API Key

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up or log in
3. Navigate to API Keys
4. Create a new key
5. Copy and add to Railway variables as `GROQ_API_KEY`

## Available Groq Models

Set `GROQ_MODEL` to one of:
- `deepseek-r1-distill-llama-70b` (default, best for reasoning)
- `llama-3.3-70b-versatile` (good general purpose)
- `mixtral-8x7b-32768` (fast, large context)
- `llama-3.1-8b-instant` (fastest, smaller model)

## Troubleshooting

### Build Fails
- Check that all files are committed to git
- Verify `nixpacks.toml` is in the root directory

### Database Connection Error
- Ensure PostgreSQL service is added
- Check that `DATABASE_URL` is in the Variables tab

### API Not Working
- Verify `GROQ_API_KEY` is set correctly
- Check the deployment logs for errors

### Rate Limiting Not Persisting
- Add Redis service for persistent rate limiting
- Without Redis, rate limits reset on each deployment
