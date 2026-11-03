# 🚨 Aapda Awaaz (आपदा आवाज़) · Signal Fusion Board

[![Sarvam AI](https://img.shields.io/badge/Powered%20by-Sarvam%20AI-FF6B4A?style=for-the-badge)](https://www.sarvam.ai/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/Frontend-React%2018%20%2B%20TypeScript-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev/)
[![Leaflet](https://img.shields.io/badge/Maps-Leaflet%20Clustering-199900?style=for-the-badge&logo=leaflet&logoColor=white)](https://leafletjs.com/)

> **Sarvam Campus Builds — Problem Statement 42 (PS42)**  
> *Aggregates multi-channel crisis reports including voice notes and calls, deduplicates incoming reports, resolves vague geographic mentions to map coordinates, ranks severity, and delivers an operational dashboard linking every prioritized incident directly to raw evidence trails.*

---

## 📌 Table of Contents
- [Executive Overview](#-executive-overview)
- [System Architecture](#-system-architecture)
- [Sarvam AI Integration](#-sarvam-ai-integration)
- [Core Capabilities](#-core-capabilities)
- [Operational Dashboard & Views](#-operational-dashboard--views)
- [Quick Start](#-quick-start)
- [Verification & Testing](#-verification--testing)
- [Project Layout](#-project-layout)
- [Configuration](#-configuration)
- [Ethical Safety & Privacy](#-ethical-safety--privacy)

---

## 🌟 Executive Overview

During large-scale disasters (floods, fires, landslides), emergency helplines are rapidly overwhelmed by hundreds of chaotic calls in different Indian languages and dialects. Responders lose critical time trying to decipher panic-stricken voice notes, pinpoint ambiguous village names, and weed out duplicate reports for the same incident.

**Aapda Awaaz** solves this by creating an intelligent, voice-first **Signal Fusion Board**:
1. **Listens in Native Indian Languages**: Powered by **Sarvam Saaras v3 STT**, auto-detecting language and transcribing dialectal speech in real time.
2. **Conducts Live Conversational Triage**: Through **Awaaz Live**, an interactive WebSocket assistant asks targeted follow-up questions only for missing facts (location, headcount, hazard).
3. **Resolves Locations to Coordinates**: Grounded in a local gazetteer to turn vague local landmarks into exact map pins with ungrounded/verified status flags.
4. **Deduplicates Across Channels**: Links multiple callers describing the same disaster into a single unified incident to prevent resource duplication.
5. **Ranks Threat Severity**: Transparent, deterministic priority scoring (Critical, High, Medium, Low) that accounts for life threat, vulnerable people, and hazard escalation.
6. **Replies with Voice**: Synthesizes verified emergency acknowledgements and broadcast alerts in the caller's language using **Sarvam Bulbul v3 TTS**.

---

## 🏗️ System Architecture

```
                                  [ Incoming Channels ]
                      Live Voice Call / Voice Note / Audio Upload
                                          │
                                          ▼
                      ┌───────────────────────────────────────┐
                      │    Speech-to-Text: Sarvam Saaras v3   │
                      │   (Auto-detects language in-stream)   │
                      └───────────────────┬───────────────────┘
                                          │ Raw Transcript
                                          ▼
                      ┌───────────────────────────────────────┐
                      │     Deterministic Rule Extraction     │
                      │  • Hazard Type    • People Count      │
                      │  • Local Location • Urgency Level     │
                      └───────────────────┬───────────────────┘
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    ▼                                           ▼
      ┌───────────────────────────┐               ┌───────────────────────────┐
      │ Gazetteer Location Engine │               │  Threat Priority Scorer   │
      │  Coordinates & Confidence │               │    0.0 - 10.0 Severity    │
      └─────────────┬─────────────┘               └─────────────┬─────────────┘
                    │                                           │
                    └─────────────────────┬─────────────────────┘
                                          ▼
                      ┌───────────────────────────────────────┐
                      │    Deduplication & Clustering Engine  │
                      │  Matches spatial, temporal & keyword  │
                      │  evidence to merge or link reports    │
                      └───────────────────┬───────────────────┘
                                          │
                    ┌─────────────────────┴─────────────────────┐
                    ▼                                           ▼
      ┌───────────────────────────┐               ┌───────────────────────────┐
      │  Text-to-Speech: Bulbul   │               │   Operational Dashboard   │
      │ Caller Acknowledgement &  │               │ • Situation Room (Leaflet)│
      │ Multi-language Broadcast  │               │ • Evidence Audit Trails   │
      └───────────────────────────┘               │ • Live Calls Panel        │
                                                  └───────────────────────────┘
```

---

## 🎙️ Sarvam AI Integration

The entire audio pipeline is built on Sarvam AI's state-of-the-art speech models:

### 1. Speech-to-Text: Sarvam Saaras v3 (`saaras:v3`)
- **Native Multilingual Auto-Detection**: No dropdown required. Saaras identifies the language spoken (`hi-IN`, `mr-IN`, `ta-IN`, `te-IN`, `kn-IN`, `ml-IN`, `gu-IN`, `bn-IN`, `pa-IN`, `en-IN`, etc.) and returns accurate transcripts even for heavy regional accents.
- **In-Memory Streaming**: Accepts WAV, MP3, M4A, AAC, OGG, and FLAC containers, and streams in-memory buffers directly from live browser AudioWorklets.
- **Robust Error Recovery**: Automatic exponential backoff with transient retry handling (429, 5xx).

### 2. Text-to-Speech: Sarvam Bulbul v3 (`bulbul:v3`)
- **High-Fidelity Regional Voices**: Spoken in the exact detected language using designated native speakers:
  | Language | Sarvam Code | Bulbul Speaker | Persona / Role |
  | :--- | :--- | :--- | :--- |
  | **Hindi** | `hi-IN` | `aditya` | Clear, reassuring emergency tone |
  | **Marathi** | `mr-IN` | `neha` | Calm, natural regional Marathi |
  | **English** | `en-IN` | `ritu` | Crisp, authoritative broadcast |
  | **Tamil** | `ta-IN` | `pooja` | Native South Indian inflection |
  | **Telugu** | `te-IN` | `rohan` | Native Telugu delivery |
  | **Kannada** | `kn-IN` | `simran` | Clear emergency instruction |
  | **Malayalam** | `ml-IN` | `kavya` | Clear regional pronunciation |
  | **Gujarati** | `gu-IN` | `amit` | Natural Western Indian dialect |
  | **Bengali** | `bn-IN` | `dev` | Natural Eastern Indian dialect |
  | **Punjabi** | `pa-IN` | `ishita` | Fluent Northern Indian delivery |
- **Direct 16 kHz PCM Streaming**: Audio is generated with `speech_sample_rate: 16000` to stream directly into the browser's audio graph without client-side resampling.

---

## ⚡ Core Capabilities

### 1. Awaaz Live (`/awaaz`)
- **Real-Time Conversational Agent**: Connects the caller to a bi-directional WebSocket (`ws://localhost:8000/api/live/call`).
- **Dynamic Missing-Fact Inquiries**: As the caller speaks, the extractor checks what has already been established:
  - If location is missing $\rightarrow$ asks for village/landmark.
  - If hazard is unclear $\rightarrow$ asks whether it is flood, fire, or collapse.
  - If headcount is unknown $\rightarrow$ asks how many people are trapped.
- **Hands-Free Turn Detection**: Continuous RMS frame energy analysis automatically detects when speech stops and closes the turn without requiring button presses.
- **Echo Prevention**: Audio input is gated while the assistant is speaking (`playback_done` synchronization) so the system never transcribes its own voice.

### 2. New Call & Visual Signal Journey (`/call`)
- A transparent 7-step visual audit trail showing exactly how raw audio turns into an actionable emergency response:
  1. **Hear**: Audio arrives and waveform is rendered.
  2. **Transcribe**: Sarvam Saaras converts audio to text.
  3. **Understand**: Entities (hazards, casualties, locations) are extracted.
  4. **Locate**: Pin drop on the map with coordinate verification status.
  5. **Match**: Deduplication engine checks against existing incidents.
  6. **Prioritise**: Algorithmic severity score (Critical, High, Medium, Low).
  7. **Reply**: Sarvam Bulbul plays a spoken acknowledgement in the caller's language.

### 3. Situation Room (`/live`)
- **Interactive Geospatial Dashboard**:
  - Clustered incident markers color-coded by priority (Red = Critical, Orange = High, Yellow = Medium, Green = Low).
  - Smooth pan-and-focus when an incident is selected from the triage list.
  - Visual distinction between verified human ground-truth coordinates and reference approximations.
- **Live Calls Panel**: Displays active conversations in real-time, showing caller/assistant turns, extracted facts, and live priority updates before the caller even hangs up.

### 4. Incident Investigation & Voice Broadcast Alerts (`/incidents/{id}`)
- Complete audit ledger linking every emergency incident back to its raw evidence: original audio recordings, transcripts, time-stamped turns, and operator corrections.
- **Voice Alerts Broadcast**: Enables dispatchers to broadcast safety announcements (evacuation warnings, shelter notices, responder updates) in multiple languages simultaneously, synthesized on-demand with **Sarvam Bulbul**.

---

## 🚀 Quick Start

### Prerequisites
- **Python 3.10+** (Python 3.11, 3.12, 3.14 tested)
- **Node.js 18+** & npm
- **Sarvam AI API Key** (from [Sarvam Dashboard](https://dashboard.sarvam.ai/))

### 1. One-Command Setup & Launch
```bash
# Clone the repository
git clone https://github.com/SarangRao20/sarvamHackathon.git
cd SarvamHackathon

# Ensure your Sarvam API Key is in .env
echo "SARVAM_API_KEY=your_sarvam_api_key_here" > .env
cp .env backend/.env

# Run backend (:8000) and frontend (:5173) together
chmod +x run.sh
./run.sh
```

Once running:
- **Web Dashboard**: [http://localhost:5173](http://localhost:5173)
- **FastAPI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

### 2. Manual Launch (Alternative)

#### Backend
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

#### Frontend
```bash
cd frontend
npm install

# Run frontend
npm run dev -- --port 5173
```

---

## 🧪 Verification & Testing

### 1. Run Backend Test Suite
The backend contains 50 automated tests covering API workflows, deduplication logic, spatial geocoding, priority scoring, audio preprocessing, and alert broadcasts:
```bash
cd backend
venv/bin/pytest
```
*Expected result:* `50 passed in ~3.5s`

### 2. Run Frontend Production Typecheck & Build
```bash
cd frontend
npm run build
```
*Expected result:* Full TypeScript verification (`tsc -b`) and Vite production bundle generation with zero errors.

### 3. Verify Live Sarvam API Integration
```bash
cd backend
venv/bin/python -c "
from app.providers.sarvam import SarvamSTT, SarvamTTS
stt = SarvamSTT()
tts = SarvamTTS()
print('✓ Sarvam Saaras STT initialized:', stt.name)
print('✓ Sarvam Bulbul TTS initialized:', tts.name)
res = tts.synthesize('नमस्ते, आपदा आवाज़ में आपका स्वागत है।', 'hi')
print(f'✓ Bulbul synthesized {len(res.audio)} bytes of audio')
"
```

---

## 📂 Project Layout

```
SarvamHackathon/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point & CORS configuration
│   │   ├── config.py            # Environment & Sarvam settings
│   │   ├── models.py            # SQLAlchemy schema (Reports, Incidents, Links, Audit)
│   │   ├── db.py                # Database session scope & connection pool
│   │   ├── api/
│   │   │   ├── auth.py          # Session authentication endpoint
│   │   │   ├── incidents.py     # Incident triage, reviews, and Voice Alerts
│   │   │   ├── live.py          # WebSocket /api/live/call & /api/live/calls
│   │   │   ├── reports.py       # Report creation, upload, audio handling
│   │   │   ├── serializers.py   # JSON API serialization views
│   │   │   └── system.py        # System health, metrics & runtime settings
│   │   ├── providers/
│   │   │   ├── base.py          # Abstract interfaces for STT and TTS
│   │   │   ├── registry.py      # Provider resolution & fallback engine
│   │   │   ├── sarvam.py        # Sarvam Saaras & Bulbul REST adapters
│   │   │   └── mock_stt.py      # Offline mock STT lookup for CI/offline runs
│   │   └── services/
│   │       ├── live_call.py     # Real-time WebSocket conversational triage engine
│   │       ├── extraction.py    # Deterministic crisis entity extraction
│   │       ├── priority.py      # Severity & threat formula calculation
│   │       ├── deduplication.py # Multi-channel incident linking
│   │       ├── geocoder.py      # Location parsing & coordinate lookup
│   │       ├── acknowledgement.py # Caller template response generator
│   │       └── worker.py        # Background task queue for async processing
│   ├── tests/                   # 50 comprehensive pytest suites
│   ├── data/                    # Synthetic disaster fixtures and audio
│   └── requirements.txt         # Pinned Python dependencies
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Application shell, navigation & theme state
│   │   ├── pages/
│   │   │   ├── Landing.tsx      # Public landing overview
│   │   │   ├── LiveCall.tsx     # Awaaz Live interactive call interface
│   │   │   ├── Journey.tsx      # 7-step visual signal journey
│   │   │   ├── CommandCenter.tsx# Live situation room & incident map
│   │   │   ├── Reports.tsx      # Report log & manual audio upload
│   │   │   ├── IncidentInvestigation.tsx # Evidence inspection & Voice Alerts
│   │   │   ├── Evaluation.tsx   # Model precision/recall metrics lab
│   │   │   └── Settings.tsx     # Threshold controls & provider diagnostics
│   │   ├── components/
│   │   │   ├── IncidentMap.tsx  # Leaflet cluster map with focus & verification
│   │   │   ├── LiveCallsPanel.tsx# Live calls monitor for situation room
│   │   │   ├── VoiceAlerts.tsx  # Dispatcher multi-lingual alert broadcast
│   │   │   ├── AudioRecorder.tsx# In-browser audio capture (16kHz WAV)
│   │   │   └── SiteView3D.tsx   # 3D satellite visualization
│   │   └── lib/
│   │       ├── api.ts           # Typed REST API client
│   │       ├── liveCall.ts      # WebSocket client & AudioWorklet capture
│   │       └── types.ts         # TypeScript schema definitions
│   ├── package.json
│   └── vite.config.ts
│
├── run.sh                       # Unified runner for frontend + backend
├── README.md                    # System documentation
└── LICENSE                      # Open-source license
```

---

## ⚙️ Configuration

Key environment settings configured in `.env`:

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `SARVAM_API_KEY` | *(Required)* | Secret key for Sarvam Saaras STT & Bulbul TTS |
| `SARVAM_BASE_URL` | `https://api.sarvam.ai` | Root URL for Sarvam API services |
| `STT_PROVIDER` | `sarvam` | Active speech-to-text adapter (`sarvam` or `mock`) |
| `TTS_PROVIDER` | `sarvam` | Active text-to-speech adapter (`sarvam` or `none`) |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Whitelisted frontend origins |
| `MAX_UPLOAD_MB` | `25` | Maximum upload limit for audio recordings |
| `AUDIO_PREPROCESSING_ENABLED` | `false` | Enable spectral noise gate & loudness normalization |
| `GEOCODING_ENABLED` | `false` | Enable live OpenStreetMap Nominatim resolution |

---

## 🛡️ Ethical Safety & Privacy

1. **No False Rescue Promises**: Standard caller acknowledgements strictly use reviewed templates that confirm receipt without guaranteeing rescue timelines or false arrival guarantees.
2. **Transparent Uncertainty**: All unverified locations, estimated headcounts, and low-confidence audio are visibly flagged with amber indicators requiring human dispatcher review before dispatch.
3. **Data Protection**: Audio recordings and transcripts remain within the emergency responder's secure boundary, transmitting only necessary speech payloads over encrypted TLS/HTTPS endpoints.

---

<div align="center">
  <b>Built for Sarvam Campus Builds — PS42</b><br/>
  <i>Empowering emergency responders through voice-first multilingual intelligence.</i>
</div>
