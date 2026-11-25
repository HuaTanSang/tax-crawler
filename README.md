# Tax crawler

This script uses Scrapy to collect household business information from [GDT](https://www.gdt.gov.vn/wps/portal/home/hct). It uses administrative divisions from before 01/07/2025 (1 July 2025).

## Prerequisites

- Windows: use WSL with Ubuntu and follow the instructions below. On macOS and Ubuntu, go straight to installation.

## Installation

### 1. Install Git, curl and Tesseract OCR

Tesseract is a system program that reads CAPTCHA images. Install it separately from the Python dependencies.
Follow the instructions for your operating system.

**Ubuntu / WSL (Ubuntu):**

```sh
sudo apt update
sudo apt install -y git curl ca-certificates tesseract-ocr
```

**macOS:** if you don't have [Homebrew](https://brew.sh/), install it with the command below, then follow
the **Next steps** shown at the end of the installation to add `brew` to your PATH:

```sh
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

Then install the tools:

```sh
brew install git curl tesseract
```

The Tesseract installation commands follow the [official documentation](https://tesseract-ocr.github.io/tessdoc/Installation.html).
Check that the tools are installed:

```sh
git --version
curl --version
tesseract --version
```

### 2. Install uv and Python 3.12

The remaining steps apply to Ubuntu, WSL/Ubuntu and macOS.
Install [uv](https://docs.astral.sh/uv/getting-started/installation/) with the standalone installer:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
. "$HOME/.local/bin/env"
uv --version
```

Use uv to [install Python 3.12](https://docs.astral.sh/uv/guides/install-python/):

```sh
uv python install 3.12
```

### 3. Clone the repository and install dependencies

```sh
git clone https://github.com/HuaTanSang/tax-crawler.git
cd tax-crawler
uv sync --locked
uv run --locked python --version
```

### 4. Install the pre-commit hook

Run this once in the cloned repository to enable automatic checks before each commit:

```sh
uv run --locked pre-commit install
```

## Run the job

From the `tax-crawler` directory, run:

```sh
uv run --locked src/gdt_spider.py
```
