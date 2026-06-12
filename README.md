# TAK-CIV Preference Configurator

Repository: [https://github.com/cfd2474/TAK_pref_configurator](https://github.com/cfd2474/TAK_pref_configurator)

Web application for building TAK-CIV `.pref` configuration files. The UI is derived from [ATAK-CIV](https://github.com/TAK-Product-Center/atak-civ) preference definitions and uses dropdowns and multi-select controls wherever the source app defines discrete options.

## Features

- Web UI for TAK-CIV preference categories extracted from ATAK-CIV source
- Dropdowns and multi-select fields for list-based preferences (units, colors, display modes, etc.)
- Structured connection builder with protocol/interface dropdowns
- Import existing `.pref` files for editing
- Preview generated XML before download
- Runs as a Docker container on Ubuntu 22.04
- No authentication (intended for trusted internal networks)

## Quick Start (Ubuntu 22.04)

```bash
git clone https://github.com/cfd2474/TAK_pref_configurator.git
cd TAK_pref_configurator
chmod +x install.sh update.sh
./install.sh
```

Open `http://<server-ip>:8080`.

## Configuration

Create or edit `.env`:

```env
APP_PORT=8080
```

## Updating

```bash
./update.sh
```

This pulls the latest git changes and rebuilds the container.

## Manual Docker Commands

```bash
docker compose up -d --build
docker compose logs -f
docker compose down
```

## Regenerating the Preference Schema

When ATAK releases a new version, refresh the schema from the upstream repo:

```bash
python3 tools/extract_schema.py
./update.sh
```

## .pref File Format

Generated files follow ATAK's `PreferenceControl` XML format:

```xml
<?xml version='1.0' standalone='yes'?>
<preferences>
  <preference name="cot_streams">
    <entry key="count" class="class java.lang.Integer">1</entry>
    <entry key="connectString0" class="class java.lang.String">ssl:server.example.com:8089:stream</entry>
  </preference>
  <preference name="com.atakmap.civ_preferences">
    <entry key="displayRed" class="class java.lang.Boolean">true</entry>
  </preference>
</preferences>
```

Reference implementation: [`PreferenceControl.java`](https://github.com/TAK-Product-Center/atak-civ/blob/main/atak/ATAK/app/src/main/java/com/atakmap/app/preferences/PreferenceControl.java)

## Deployment Notes

- Place generated `.pref` files in ATAK's config prefs directory or import through ATAK's preference management UI
- Device-specific keys (`locationCallsign`, `bestDeviceUID`) are intentionally excluded
- Default output group: `com.atakmap.civ_preferences`

## Project Structure

```
backend/          FastAPI app and .pref generator
frontend/         Static web UI
tools/            Schema extraction script
install.sh        First-time server install
update.sh         Pull and redeploy
docker-compose.yml
Dockerfile
```

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn backend.app.main:app --reload --port 8080
```

Then open `http://127.0.0.1:8080`.
