# TommyMoran.com

A personal website featuring an interactive AI chatbot, portfolio showcase, and the HEART (Hobart Echo Appropriateness Review Tool) clinical decision support system.

## 🚀 Features

- Interactive AI Chatbot powered by OpenAI
- Responsive and modern UI design
- Portfolio showcase
- Contact information
- Blog section
- HEART clinical decision support tool for echocardiogram appropriateness

## 🏥 HEART Tool

HEART (Hobart Echo Appropriateness Review Tool) is a clinical decision support tool designed to help clinicians determine the appropriateness of echocardiogram requests based on validated clinical criteria. The tool:

- Assesses if an echocardiogram is indicated for a specific clinical scenario
- Determines the appropriate timeframe for the study
- Recommends inpatient vs outpatient setting
- Suggests consultations with specialist teams when necessary
- Generates unique case IDs for audit purposes

Access the tool at [tommymoran.com/HEART](https://tommymoran.com/HEART)

## 🛠️ Tech Stack

- **Frontend**: HTML5, CSS3, JavaScript
- **Backend**: 
  - Flask (Python web framework)
  - Gunicorn (Production WSGI HTTP Server)
- **AI Integration**: OpenAI API (Assistants)
- **Database**: JSON file storage for HEART case data
- **Deployment**: 
  - Render.com (Cloud Platform)
  - Gunicorn (Production Server)
- **Version Control**: Git

## 📁 Project Structure

```
.
├── index.html          # Main website page
├── server.py           # Flask backend server
├── script.js           # Frontend JavaScript
├── styles.css          # CSS styles
├── requirements.txt    # Python dependencies
├── .env                # Environment variables
├── gunicorn_config.py  # Production server configuration
├── render.yaml         # Render deployment configuration
├── images/             # Image assets
├── HEART/              # HEART tool files
│   ├── index.html      # HEART landing page
│   ├── context.html    # Clinical context input page
│   ├── about.html      # About the HEART tool
│   ├── help.html       # Help and contact form
│   ├── js/             # JavaScript for HEART
│   ├── css/            # CSS for HEART
│   └── images/         # HEART-specific images
├── tools/              # Utility scripts
└── deploy/             # Deployment configurations
```

## 🚀 Getting Started

### Prerequisites

- Python 3.x
- Node.js (for development)
- OpenAI API key

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/Webpage.git
   cd Webpage
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file with your OpenAI API keys:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

5. Update the HEART Assistant ID in server.py:
   ```python
   # Replace with your actual HEART assistant ID
   assistant_id="REPLACE_WITH_HEART_ASSISTANT_ID"
   ```

6. Run the development server:
   ```bash
   python server.py
   ```

## 🌐 Deployment

The website is deployed on Render.com. The deployment process:
1. The Flask application is served using Gunicorn (configuration in `gunicorn_config.py`)
2. Render.com handles the deployment and hosting (configuration in `render.yaml`)
3. Environment variables like the OpenAI API key are securely managed through Render's dashboard

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 📞 Contact

- Website: [tommymoran.com](https://tommymoran.com)
- Email: TommyMoran@gmail.com

---

Last updated: May 16, 2024
