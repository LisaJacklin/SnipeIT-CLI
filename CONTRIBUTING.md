# Contributing to SnipeIT-CLI

Thank you for your interest in contributing to **SnipeIT-CLI**! We welcome bug reports, feature suggestions, and code contributions.

---

## 🛠 Development Setup

1. **Fork and clone the repository:**
   ```bash
   git clone https://github.com/<your-username>/SnipeIT-CLI.git
   cd SnipeIT-CLI
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install the package in editable mode with dependencies:**
   ```bash
   pip install -e .
   ```

4. **Configure your test credentials:**
   ```bash
   cp example.cred dev.cred
   # Edit dev.cred with your test Snipe-IT API key
   ```

---

## 🧪 Testing Your Changes

Verify that the CLI runs and your changes work properly:

```bash
# Verify CLI help and command discovery
snipeit --help

# Test authentication against your test instance
snipeit test auth --profile dev

# Test asset listing
snipeit asset list --profile dev --limit 2
```

---

## 🔒 Security & Credentials

- **NEVER** commit real API tokens, `.cred` files (except `example.cred`), or `.env` files containing live keys.
- Check `git status` before committing to verify no credential files are staged.
- All credential files (`*.cred`, `.env`) are excluded in `.gitignore`.

---

## 📝 Pull Request Process

1. Create a descriptive feature branch:
   ```bash
   git checkout -b feature/my-new-command
   ```
2. Make your code changes, ensuring clear docstrings and comments are included.
3. Commit with clear, descriptive commit messages:
   ```bash
   git commit -m "Add asset checkout command"
   ```
4. Push to your fork and open a Pull Request against the `main` branch.
