# Contributing to JanesCriber

Thank you for your interest in contributing to **JanesCriber**! We welcome bug fixes, performance improvements, and architectural enhancements that advance our mission of building a private, fast, offline audio and video transcription studio.

---

## 1. Developer Certificate of Origin (DCO)

To protect the software, its maintainers, and its users, all contributors must certify that their contributions comply with the Developer Certificate of Origin (Version 1.1):

```text
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

By submitting a Pull Request, you certify that your contribution is licensed under the repository's [MIT License](LICENSE) and does not violate any third-party copyrights, patents, or intellectual property rights.

---

## 2. Engineering Standards & Verification Gates

JanesCriber adheres to strict quality and stability requirements. Before submitting a pull request, ensure all verification gates pass cleanly:

### A. Python Transcription Engine
Run using `uv` with locked dependencies:
```bash
uv sync --locked
uv run --locked pytest tests/ -v
```
- All unit tests must pass.
- New features or bug fixes must include corresponding tests in `tests/`.

### B. Tauri Desktop Rust Bridge
```bash
cd desktop-ui
cargo fmt --manifest-path src-tauri/Cargo.toml --check
cargo test --manifest-path src-tauri/Cargo.toml
```

### C. Frontend Interface (React + TypeScript)
```bash
cd desktop-ui
npm test
npm run build
```

---

## 3. Pull Request Guidelines

1. **Keep PRs Focused:** Small, coherent pull requests are reviewed and merged significantly faster.
2. **Preserve Offline Integrity:** Never introduce remote network calls, tracking, telemetry, or external API requirements into core transcription pipelines.
3. **Packaging Discipline:** Never commit loose build scripts to the repository root; all packaging logic belongs in `packaging/`.
