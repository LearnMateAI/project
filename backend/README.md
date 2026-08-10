# Backend development

Create and populate the virtual environment once:

```bash
cd backend
python3 -m venv venv
./venv/bin/python -m pip install -r requirements.txt
```

Activate the environment and start the server on macOS or Linux:

```bash
source venv/bin/activate
python -m uvicorn server:app --reload --port 8000
```

Confirm which interpreter is active with:

```bash
python -c "import sys; print(sys.executable)"
```

It should end with `/backend/venv/bin/python`.

Press `Ctrl+C` to stop the server. Run `deactivate` when you want to leave an
activated virtual environment.
