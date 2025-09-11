# ALWAYS READ
## Virtual Environment
This project uses uv for dependency management. Always use uv commands instead of python directly:
```bash
# Run Python commands through uv
uv run python script.py

# Install dependencies
uv sync

# Run tests
uv run python -m pytest

# No need to manually activate virtual environment - uv handles it automatically
```
## Directory Structure
