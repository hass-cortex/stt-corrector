# Sensors

The integration provides 7 sensor entities grouped under a single device, tracking correction activity. All sensors are diagnostic entities.

## Correction Output

| Sensor | Enabled | Description |
|--------|---------|-------------|
| **Last raw text** | Yes | Original text from the wrapped STT entity (before correction) |
| **Last corrected text** | Yes | Text after correction pipeline (cleared when no correction or no-speech) |
| **Last result** | Yes | Status of most recent attempt: `success`, `no_speech`, `error`, or `wrapped_unavailable` |

## Usage Counters

| Sensor | Enabled | Description |
|--------|---------|-------------|
| **Total requests** | Yes | Total proxy invocations (success + failure) |
| **Successful requests** | No | Requests that returned a transcription |
| **Corrections applied** | Yes | Number of requests where correction changed the text |

## Last Request Details

| Sensor | Enabled | Description |
|--------|---------|-------------|
| **Last language** | No | BCP-47 locale used in the most recent request |
