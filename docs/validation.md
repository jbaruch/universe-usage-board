# Validation

Tested on a physical GitHub Universe 2026 Badger 2350 with MicroPython 1.29.0-preview, firmware build 2026-10-13.

- Rendered and inspected actual 320×240 framebuffers for the matrix, enlarged metrics, waiting, and stale states.
- Checked combined Claude weekly/session rings and separate Antigravity Gemini/Claude resource selection.
- Checked empty/full remaining-allowance endpoints and green/yellow/red boundaries.
- Injected logical button events on the device to check navigation, detail selection, return to matrix, and launcher exit.
- Read back the 80% backlight setting.
- Rebooted into the installed startup app and verified live USB READY/ACK updates from the Mac helper.
- Static app validation passed using the official Universe 2026 skill.

The automated suite checks normalization, missing/error/stale readings, provider filtering/order, multiple accounts, balance semantics, invalid numeric values, credential-field exclusion, portable helper configuration, and deployment/backup/restore guards.

Physical cable-removal sleep/wake and the launcher's icon appearance were not independently visually confirmed in the automated checks. The README includes a photograph of the installed badge and a separate real badge framebuffer rendered using synthetic demonstration data.
