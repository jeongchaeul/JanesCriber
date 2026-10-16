# Security Policy

**Project:** JanesCriber  
**Maintainer:** project//aspyr (Jane Cerys)  

---

## 1. Supported Versions

Security updates and vulnerability remediation are actively provided for the following releases:

| Version Line | Supported | Status |
| :--- | :--- | :--- |
| **v2.x** (Current) | :white_check_mark: Yes | Actively maintained, tested, and updated |
| **v1.x** (Legacy) | :x: No | Deprecated; users are advised to upgrade to v2.x |

---

## 2. Reporting a Vulnerability

We welcome responsible security research and vulnerability disclosures. If you discover a security vulnerability or weakness in JanesCriber, please report it privately rather than filing a public issue.

### Preferred Reporting Method
- **GitHub Private Vulnerability Reporting:** Open a private advisory under the security tab of the repository.
- **Direct Maintainer Contact:** Alternatively, reach out directly to the maintainer via the contact channel provided in the repository profile with the subject `[SECURITY VULNERABILITY] JanesCriber`.

### What to Include in Your Report
To help us triage and reproduce the issue rapidly, please provide:
1. A clear description of the vulnerability, affected components, and perceived impact.
2. Step-by-step instructions or a Minimal Reproducible Example / Proof of Concept (PoC).
3. The affected environment (Operating System, JanesCriber version, hardware acceleration backend).
4. Proposed mitigation or patch, if known.

### Response Timelines & SLA
- **Initial Acknowledgment:** Within **48 hours** of receiving the report.
- **Triage & Assessment:** Within **5 business days**, confirming reproduction and assigning an internal priority.
- **Remediation & Patch Release:** Critical and High severity issues will receive priority patching, followed by a coordinated public release.

---

## 3. Scope & Threat Model

JanesCriber is a desktop audio and video transcription studio running on local hardware.

### In-Scope Vulnerabilities
- Arbitrary code execution or sandbox escapes triggered by parsing malformed media files.
- Command or argument injection via unsanitized filenames or input paths passed to external subprocesses (such as FFmpeg/ffprobe).
- Local IPC vulnerabilities, command injection, or path traversal across the Tauri native bridge or JSON-lines service.
- Path traversal in transcript export or model caching operations allowing write access outside the designated project or library directories.

### Out-of-Scope Vulnerabilities
- Attacks requiring physical access or administrative control (`root` / `Administrator`) over the user's workstation.
- Local resource exhaustion where a user manually requests models exceeding physical hardware capacity (RAM/VRAM).
