# Intelligent Dashboard Demo App

A simple template for building Databricks Apps that combine Lakeview dashboards with Genie AI chatbots in a single-page interface.

**Built with:** FastAPI + Vanilla HTML/CSS/JS (no build tools needed!)

---

## 🎯 What You Get

- **70% Dashboard / 30% Chatbot** split-screen layout
- **Databricks Lakeview** dashboard embedded on the left
- **Genie AI chatbot** for natural language queries on the right
- **OAuth authentication** handled by Databricks Apps
- **Zero frontend dependencies** - pure HTML/CSS/JS

**Perfect for:** Quick demos, internal analytics tools, and proof-of-concepts.

---

## 📁 Project Structure

```
your-app/
├── app.py                 # FastAPI backend (serves static files + proxies APIs)
├── config.py              # Configuration (YOUR dashboard/Genie IDs go here)
├── requirements.txt       # Python dependencies
├── app.yaml              # Databricks Apps deployment config
└── static/               # Frontend (HTML/CSS/JS)
    ├── index.html        # Main page
    ├── css/styles.css    # Styling (easily customizable)
    └── js/
        ├── chatbot.js    # Genie API integration
        └── dashboard.js  # Dashboard embedding
```

---

## 🚀 Quick Start

### 1. Get Your Configuration Details

You need three things from your Databricks workspace:

**Dashboard ID:**
- Open your Lakeview dashboard
- Copy ID from URL: `/dashboardsv3/{YOUR_DASHBOARD_ID}`

**Genie Space ID:**
- Open your Genie space
- Copy ID from URL: `/genie/rooms/{YOUR_SPACE_ID}`

**Access Token:**
- User Settings → Access Tokens → Generate New Token
- Copy the token (starts with `dapi...`)

### 2. Configure Your App

Create a `.env` file in the project root with your credentials:

```bash
# Copy the template
cp env.example .env

# Edit .env with your actual values
```

**Required environment variables:**
```bash
DATABRICKS_INSTANCE_URL=https://your-workspace.cloud.databricks.com
DATABRICKS_WORKSPACE_ID=your_workspace_id
DATABRICKS_DASHBOARD_ID=your_dashboard_id
DATABRICKS_DASHBOARD_TOKEN=dapi_your_token_here

DATABRICKS_GENIE_INSTANCE_URL=https://your-workspace.cloud.databricks.com
DATABRICKS_GENIE_SPACE_ID=your_genie_space_id
DATABRICKS_GENIE_TOKEN=dapi_your_token_here
```

> **⚠️ IMPORTANT:** Never commit your `.env` file to git! It contains secrets.

### 3. Test Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the app
uvicorn app:app --host 127.0.0.1 --port 8000 --reload

# Open browser
open http://127.0.0.1:8000
```

### 4. Deploy to Databricks

```bash
databricks apps deploy your-app-name --source-code-path .
```

Done! 🎉

---

## 🎨 Customization Guide

### Change App Title

**File:** `static/index.html` (line 18)
```html
<h1 class="app-title">Your App Name Here</h1>
```

### Change Colors

**File:** `static/css/styles.css` (lines 4-6)
```css
:root {
    --danone-blue: #0066cc;        /* Your brand color */
    --danone-dark-blue: #004c99;   /* Darker shade */
}
```

### Adjust Layout Proportions

**File:** `static/index.html` (line 25)
```html
<!-- Current: 70% dashboard, 30% chat -->
<div style="display: grid; grid-template-columns: 70% 30%; ...">

<!-- Options: -->
<!-- 50/50 split -->
<div style="display: grid; grid-template-columns: 50% 50%; ...">

<!-- 80/20 split -->
<div style="display: grid; grid-template-columns: 80% 20%; ...">
```

### Update Sample Questions

**File:** `static/index.html` (lines 45-53)

Replace with questions relevant to your Genie space:
```html
<button onclick="sendSampleQuestion('Your question here')">
    Button label
</button>
```

Also update in `static/js/chatbot.js` (lines 352-360) for the reset button.

---

## 🔧 Configuration Details

### `config.py` - Main Configuration

```python
# Dashboard Configuration
dashboard_config = {
    "instance_url": "https://your-workspace.cloud.databricks.com",
    "workspace_id": "your_workspace_id",
    "dashboard_id": "YOUR_DASHBOARD_ID",  # ← Required
    "token": "YOUR_TOKEN"                 # ← Required
}

# Genie Configuration  
genie_config = {
    "instance_url": "https://your-workspace.cloud.databricks.com",
    "space_id": "YOUR_GENIE_SPACE_ID",    # ← Required
    "token": "YOUR_TOKEN",                # ← Required (can be same as above)
    "api_base": "/api/2.0/genie"
}
```

### `app.yaml` - Deployment Settings

```yaml
# Command to run your app
command: ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]

# OAuth scopes (required for Genie and Dashboard access)
scopes:
  - "all-apis"

# Public paths (no authentication required)
auth:
  public_paths:
    - "/static/**"
    - "/css/**"
    - "/js/**"
    - "*.css"
    - "*.js"
    - "*.json"
```

---

## 🎓 How It Works

### Backend (`app.py`)

The FastAPI backend is simple:
1. Serves static files from `/static`
2. Proxies Genie API calls (so frontend doesn't expose tokens)
3. Provides dashboard configuration endpoint
4. OAuth handled automatically by Databricks Apps

**Key endpoints:**
- `GET /` - Main page
- `POST /api/genie/conversations/start` - Start chat
- `GET /api/dashboard/config` - Dashboard embed info
- `GET /health` - Health check

### Frontend (`static/`)

Pure HTML/CSS/JS - no build process:

**`index.html`**: Single page with 70/30 split layout

**`chatbot.js`**: 
- Polls Genie API for responses
- Displays messages and query results
- Handles conversation state

**`dashboard.js`**:
- Fetches embed configuration
- Creates iframe for dashboard

**`styles.css`**:
- CSS variables for easy theming
- Responsive design
- Blue gradient header (customizable)

---

## 📦 Dependencies

**Python** (see `requirements.txt`):
```
fastapi==0.104.1
uvicorn==0.24.0
httpx==0.28.1
pydantic==2.11.7
```

**Frontend**: Zero dependencies! Pure JavaScript.

---

## 🚀 Deployment

### Option 1: Databricks Apps (Recommended)

```bash
databricks apps deploy my-app --source-code-path .
```

**Pros:** OAuth built-in, auto-scaling, easy deployment

### Option 2: Docker

```bash
docker build -t my-app .
docker run -p 8000:8000 my-app
```

### Option 3: Direct

```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8000
```

---

## 🔐 Permissions

Users need these permissions:
- **Dashboard**: `CAN_VIEW` on your Lakeview dashboard
- **Genie**: `CAN_USE` on your Genie space
- **App**: `CAN_RUN` on the deployed app

Grant permissions via Databricks workspace UI or CLI.

---

## 🐛 Troubleshooting

### Dashboard Not Loading
- ✅ Verify dashboard ID in `config.py`
- ✅ Check token has dashboard access
- ✅ Confirm workspace ID is correct

### Chatbot Not Responding
- ✅ Verify Genie space ID in `config.py`
- ✅ Check token has Genie access
- ✅ Ensure `app.yaml` includes `all-apis` scope

### Static Files Not Loading
- ✅ Check files exist in `static/` directory
- ✅ Verify `app.yaml` public_paths configuration

### Authentication Errors
- ✅ Add `all-apis` to `app.yaml` scopes
- ✅ Verify user permissions on resources
- ✅ Restart app after config changes

---

## 🎯 Common Modifications

### Remove Database Code (Simplify)

If you don't need database features:
- Comment out database imports in `app.py` (lines 11-16)
- Remove database endpoints (lines 499-929)
- Delete database config from `config.py`

### Dashboard-Only App

Remove chatbot:
```html
<!-- static/index.html - change to single column -->
<div style="grid-template-columns: 100%;">
    <!-- Keep only dashboard section -->
</div>
```

Remove: `<script src="/js/chatbot.js"></script>`

### Chatbot-Only App

Remove dashboard:
```html
<!-- static/index.html - change to single column -->
<div style="grid-template-columns: 100%;">
    <!-- Keep only chatbot section -->
</div>
```

Remove: `<script src="/js/dashboard.js"></script>`

---

## 💡 Tips

**Use Environment Variables:**
```bash
export DATABRICKS_DASHBOARD_ID="your_id"
export DATABRICKS_GENIE_SPACE_ID="your_id"
export DATABRICKS_TOKEN="your_token"
```

**Sample Questions:**
Customize based on your Genie space's capabilities. Check what queries your space can answer.

**Branding:**
Replace colors in `styles.css` with your company's brand colors.

**Multiple Environments:**
Create separate configs for dev/staging/prod using environment variables.

---

## 📚 Resources

- [Databricks Apps Documentation](https://docs.databricks.com/en/apps/index.html)
- [Genie API Reference](https://docs.databricks.com/en/genie/api-ref.html)
- [Lakeview Dashboards](https://docs.databricks.com/en/dashboards/index.html)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

## 🤝 Contributing

This is a template! Feel free to:
- Fork and customize for your needs
- Remove features you don't need
- Add new features for your use case
- Share improvements with your team

---

## 📄 License

This template is provided as-is for use with Databricks.

---

**Questions?** Check the inline code comments or Databricks documentation!

**Ready to build?** Start by updating `config.py` with your IDs! 🚀
