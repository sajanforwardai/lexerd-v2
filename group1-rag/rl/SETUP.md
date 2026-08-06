# Environment Setup Guide

This guide walks through setting up the RL dynamic hedging system in your environment.

## Prerequisites

- Python 3.8+
- pip or conda
- ~500 MB disk space for dependencies
- (Optional) GPU for faster training (CUDA 11.8+)

## Installation Options

### Option 1: Virtual Environment (Recommended)

```bash
# Navigate to project
cd /workspace/group1-rag/rl

# Create virtual environment
python3 -m venv venv

# Activate
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Verify
python3 -c "import torch, gymnasium, numpy; print('✓ Setup complete')"
```

### Option 2: Conda Environment

```bash
# Create conda environment
conda create -n rl-hedging python=3.10 -y

# Activate
conda activate rl-hedging

# Install dependencies
conda install pytorch pytorch-cuda=11.8 -c pytorch -c nvidia
conda install gymnasium numpy pytest -y

# Verify
python -c "import torch, gymnasium, numpy; print('✓ Setup complete')"
```

### Option 3: Docker (Production)

```bash
# Build Docker image
docker build -f Dockerfile -t group1-rl:latest .

# Run container
docker run -it --gpus all group1-rl:latest

# Inside container: run training
python example_training.py
```

## Dependencies

### Required

| Package | Version | Purpose |
|---------|---------|---------|
| numpy | ≥1.20 | Numerical computation |
| gymnasium | ≥0.27 | RL environment interface |
| torch | ≥2.0 | Neural network training |
| python | 3.8+ | Runtime |

### Optional

| Package | Version | Purpose |
|---------|---------|---------|
| pytest | ≥7.0 | Testing |
| tensorboard | ≥2.10 | Training visualization |
| wandb | ≥0.13 | Experiment tracking |

### Requirements File

Create `requirements.txt`:

```
numpy>=1.20
gymnasium>=0.27
torch>=2.0
pytest>=7.0
```

Install with:
```bash
pip install -r requirements.txt
```

## Verification

### Test Imports

```bash
python3 -c "
import numpy as np
import gymnasium as gym
import torch
print('✓ numpy version:', np.__version__)
print('✓ gymnasium version:', gym.__version__)
print('✓ torch version:', torch.__version__)
print('✓ CUDA available:', torch.cuda.is_available())
"
```

### Test Installation

```bash
# Navigate to RL module
cd /workspace/group1-rag/rl

# Check syntax
python3 -m py_compile *.py

# Run quick test
python3 -c "from rl_environment import HedgingEnvironment; env = HedgingEnvironment(); print('✓ Environment initialized')"
```

### Run Full Test Suite

```bash
cd /workspace/group1-rag/rl

# Run all tests
pytest test_rl.py -v

# Run specific test
pytest test_rl.py::TestHedgingEnvironment -v

# Run with coverage
pytest test_rl.py --cov=. --cov-report=html
```

## GPU Setup (Optional but Recommended)

### Check GPU

```bash
python3 -c "
import torch
print('CUDA available:', torch.cuda.is_available())
if torch.cuda.is_available():
    print('CUDA device:', torch.cuda.get_device_name(0))
    print('Device count:', torch.cuda.device_count())
"
```

### Install CUDA-Enabled PyTorch

```bash
# For NVIDIA GPU (CUDA 11.8)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# For CPU only
pip install torch torchvision torchaudio

# For AMD GPU
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.7
```

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'torch'"

**Solution**: Install PyTorch
```bash
pip install torch
```

### Issue: "ModuleNotFoundError: No module named 'gymnasium'"

**Solution**: Install Gymnasium
```bash
pip install gymnasium
```

### Issue: "CUDA out of memory"

**Solution**: Reduce batch size or network size
```python
config = PPOConfig(batch_size=32)  # Default: 64
config = PPOConfig(hidden_size=64)  # Default: 128
```

### Issue: "Slow training on CPU"

**Solution**: Use GPU (if available)
```python
device = "cuda" if torch.cuda.is_available() else "cpu"
agent = PPOAgent(device=device)
```

Or use smaller episodes:
```python
config = TrainingConfig(trading_day_minutes=200)  # Default: 390
```

### Issue: Tests fail with "No module named pytest"

**Solution**: Install pytest
```bash
pip install pytest
```

## Platform-Specific Instructions

### macOS (Apple Silicon)

```bash
# Install dependencies for Apple Silicon
pip install --upgrade pip

# Install PyTorch for Apple Silicon
pip install torch torchvision torchaudio

# Verify Metal acceleration
python3 -c "
import torch
print('Metal available:', torch.backends.mps.is_available())
"
```

### Linux

```bash
# Install system dependencies (Ubuntu/Debian)
apt-get install python3-dev python3-pip python3-venv

# Create venv
python3 -m venv venv
source venv/bin/activate

# Install
pip install -r requirements.txt
```

### Windows

```bash
# Create venv
python -m venv venv

# Activate (PowerShell)
.\venv\Scripts\Activate.ps1

# Activate (cmd)
venv\Scripts\activate.bat

# Install
pip install -r requirements.txt
```

## Development Setup

### For Contributors

```bash
# Clone the project
cd /workspace/group1-rag/rl

# Create development venv
python3 -m venv venv-dev
source venv-dev/bin/activate

# Install with development tools
pip install -r requirements-dev.txt

# Pre-commit hooks (optional)
pre-commit install

# Code formatting (optional)
black *.py
pylint *.py
mypy *.py
```

### requirements-dev.txt

```
numpy>=1.20
gymnasium>=0.27
torch>=2.0
pytest>=7.0
black>=22.0
pylint>=2.15
mypy>=0.990
pre-commit>=2.20
```

## Docker Setup

### Dockerfile

```dockerfile
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /workspace/group1-rag/rl

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# Run training by default
CMD ["python", "example_training.py"]
```

Build and run:
```bash
docker build -t group1-rl:latest .
docker run -it --gpus all group1-rl:latest
```

## Performance Tips

### For Faster Training

1. **Use GPU**: 5-10x faster on NVIDIA GPU
```python
agent = PPOAgent(device="cuda")
```

2. **Reduce episode length**: Faster feedback
```python
config = TrainingConfig(trading_day_minutes=200)
```

3. **Reduce network size**: Faster updates
```python
config = PPOConfig(hidden_size=64)
```

4. **Larger batch size**: More stable learning (requires more RAM)
```python
config = PPOConfig(batch_size=128)
```

### Memory Optimization

1. **Reduce portfolio value**: Smaller numbers
```python
config = TrainingConfig(initial_portfolio=1_000_000)
```

2. **Smaller network**: Fewer parameters
```python
config = PPOConfig(hidden_size=64)
```

3. **Smaller batch size**: Less buffered data
```python
config = PPOConfig(batch_size=32)
```

## Validation Checklist

After installation, verify:

- [ ] Python 3.8+ installed
- [ ] numpy, gymnasium, torch installed
- [ ] All .py files compile without errors
- [ ] Can import all modules:
  ```bash
  python3 -c "
  from rl_environment import HedgingEnvironment
  from q_learning_agent import QLearningAgent
  from ppo_agent import PPOAgent
  from training_loop import TrainingLoop
  print('✓ All imports successful')
  "
  ```
- [ ] Can create environment:
  ```bash
  python3 -c "
  from rl_environment import HedgingEnvironment
  env = HedgingEnvironment(seed=42)
  obs, info = env.reset()
  print('✓ Environment created')
  "
  ```
- [ ] Can create agents:
  ```bash
  python3 -c "
  from ppo_agent import PPOAgent
  from q_learning_agent import QLearningAgent
  ppo = PPOAgent()
  q = QLearningAgent()
  print('✓ Agents created')
  "
  ```
- [ ] Tests pass (at least basic ones):
  ```bash
  pytest test_rl.py::TestHedgingEnvironment::test_env_initialization -v
  ```

## Next Steps

1. **Verify Installation**: Run validation checklist above
2. **Run Quick Test**: See QUICKSTART.md "Option A"
3. **Full Training**: See QUICKSTART.md "Option B"
4. **Explore Code**: Review README.md architecture section
5. **Run Examples**: `python example_training.py`

## Getting Help

1. **Installation issues**: Check "Troubleshooting" section
2. **Test failures**: Run `pytest -vv` for detailed output
3. **Training problems**: See README.md "Troubleshooting" section
4. **Code questions**: Review docstrings and example_training.py

---

**Version**: 0.1.0  
**Last Updated**: 2026-08-06

**Successfully installed?** → Run `python example_training.py`
