# aibtcdev-backend

## Disclaimer

aibtc.dev is not liable for any lost, locked, or mistakenly sent funds. This is alpha software—use at your own risk. Any STX sent to you is owned by you, the trader, and may be redeemed, including profits or losses, at the end of the aibtc.dev Champions Sprint (~5 days). By participating, you accept that aibtc.dev is not responsible for any product use, costs, taxes incurred from trading STX or any other digital asset, or any other liability.

## Getting Started

There are two ways to run the backend locally: using Conda (recommended for development) or Docker.

### Prerequisites

- Python 3.10
- [Bun](https://bun.sh/) (for running TypeScript scripts)
- Git
- Conda (if using the Conda approach)
- Docker (if using the Docker approach)

### Environment Setup

1. Clone the repository and initialize submodules:

```bash
git clone [repository-url]
cd aibtcdev-backend
git submodule init
git submodule update --remote
```

2. Configure environment variables:

- Copy the `.env.example` file to `.env`
- Update the variables as needed

### Option 1: Using Conda (Recommended for Development)

1. Install Miniconda:

```bash
# On macOS
brew install miniconda

# Initialize conda (required after installation)
conda init "$(basename "${SHELL}")"
# Restart your terminal or source your shell configuration
source ~/.zshrc  # for zsh
source ~/.bashrc # for bash
```

2. Create and activate a new conda environment:

```bash
conda create --name aibackend python=3.10
conda activate aibackend
```

3. Install Python dependencies:

```bash
pip install -r requirements.txt
```

4. Set up the TypeScript tools:

```bash
cd agent-tools-ts/
bun install
cd ..
```

5. Run the development server:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Option 2: Using Docker

1. Build the Docker image:

```bash
docker build -t aibtcdev-backend .
```

2. Run the container:

```bash
docker run -p 8000:8000 --env-file .env aibtcdev-backend
```

### Verifying the Installation

The API should be accessible at `http://localhost:8000`. You can verify it's working by:

1. Checking the health endpoint:

```bash
curl http://localhost:8000/
```

2. Viewing the API documentation:

```bash
# Open in your browser
http://localhost:8000/docs
```

## Usage

The backend provides several API endpoints:

- `/` - Health check
- `/bot` - Telegram bot functionality
- `/crew` - Crew management
- `/chat` - Chat functionality

For detailed API documentation, visit the `/docs` endpoint when running the server.

## Development Notes

- The main development branch is `feat/digitalocean`
- Frontend corresponding branch is `feat/cloudflare`
- The system uses OpenAI's API with rate limits depending on your tier
- Bun is used for TypeScript scripts, particularly for wallet operations

## Contributing

1. Branch protection is enabled on `main`
2. Auto-deployment is configured for updates
3. Pull requests require one approval
4. Please ensure all tests pass before submitting a PR

## Troubleshooting

If you encounter rate limit issues with OpenAI:

- Check your current tier limits at https://platform.openai.com/settings/organization/limits
- TPM (Tokens Per Minute) limits vary by tier:
  - Tier 1: 200,000 TPM
  - Tier 2: 2,000,000 TPM


## Supabase

```sql
CREATE TRIGGER on_auth_user_created AFTER INSERT ON auth.users FOR EACH ROW EXECUTE FUNCTION handle_new_user()
```


### NAME
```sql
handle_new_user
```

```sql
BEGIN
  INSERT INTO public.profiles (id, username, email)
  VALUES (NEW.id, NEW.raw_user_meta_data->>'user_name', NEW.email);
  RETURN NEW;
END;
```

Security needs to be definer