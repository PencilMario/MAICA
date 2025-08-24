# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MAICA (幻象引擎/Illuminator) is a Python-based AI system with multiple components including HTTP/WebSocket servers, AI model integrations, and various utility modules. The project supports both English and Chinese languages.

## Development Commands

### Starting the Application
- **Linux**: `cd kickstart && ./start_linux.sh`
- **Windows**: `cd kickstart && powershell -ExecutionPolicy Bypass -File start_windows.ps1`

The startup scripts launch multiple processes:
- `00essentials.py` - Environment setup and configuration
- `maica_ws.py` - WebSocket server
- `maica_http.py` - HTTP server (Quart-based)
- `00nvsmiwatch.py` - NVIDIA GPU monitoring
- `00keepalived.py` - Process monitoring

### Dependencies
- Install dependencies: `pip install -r requirements.txt`
- Project uses Python 3.10+ with virtual environment in `maica/` directory

## Architecture

### Core Structure
- `maica/` - Main application directory
  - `maica_http.py` - HTTP server using Quart framework
  - `maica_ws.py` - WebSocket server implementation
  - `00essentials.py` - Environment initialization
  - `maica_utils/` - Core utility modules
  - `mtools/` - Tool modules (email, inspiration, scraping, agents)
  - `mfocus/` - Focus management modules
  - `mtrigger/` - Trigger system modules

### Key Components

#### maica_utils Package
Core utilities including:
- Database connection pooling (`DbPoolCoroutine`)
- Account management and encryption
- Settings management
- Connection utilities
- Exception handling classes

#### mtools Package
Tool modules providing:
- `mpostal.py` - Email functionality
- `mspire.py` - Inspiration generation
- `wiki_scraping.py` - Wikipedia integration
- `weather_scraping.py` - Weather API
- `enet_scraping.py` - Internet search
- `agent_modules.py` - Agent tool implementations

#### Database
- Uses SQLite databases (`maica.db`, `flarum.db`)
- Connection pooling via `DbPoolCoroutine`
- Account management via `AccountCursor`

#### Security
- RSA encryption for tokens and authentication
- Public/private key pairs in `key/` directory
- Message signing and verification

### Communication Protocols
- **WebSocket**: Primary interface at `wss://maicadev.monika.love/websocket`
- **HTTP POST**: Secondary API endpoints
- **Message Format**: JSON with standardized status codes (1xx, 2xx, 4xx, 5xx)

### Configuration
- Environment variables loaded via `load_env()` function
- Proxy support with `PROXY_ADDR` configuration
- Version control via `VERSION_CONTROL` environment variable
- Database selection via `USE_SQLITE` environment variable:
  - `enabled`: Uses SQLite databases (AUTHENTICATOR_DB and MAICA_DB as file paths)
  - `disabled`: Uses MySQL databases with DB_ADDR, DB_USER, DB_PASSWORD configuration

## Important Notes
- The `maica/Lib/` and `maica/Scripts/` directories contain a Python virtual environment
- Project supports both Linux and Windows deployment
- Uses RSA encryption for secure communication
- Multi-process architecture with proper cleanup handling
- Extensive error handling with custom exception classes