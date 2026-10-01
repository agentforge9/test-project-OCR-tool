# OCR Region Capture

A small Windows app that reads text from the screen and takes silent screenshots, using global hotkeys.

- Read the text inside a screen area, and get **only the new text** each time (good for live captions).
- Take a rectangle screenshot **silently**: no grey screen, no crosshair, no visible border.
- Take a **freeform** (any shape) screenshot, also silently.
- Hotkeys work in every program after you press **Start**. They stop after you press **Stop**.
- All settings are saved in `settings.json` next to the exe. Copy both files to another PC and it works the same.

---

## 1. Quick start (use the exe)

1. Open the `dist` folder and double-click **`OcrRegionCapture.exe`**.
2. Press **Start**.
3. Press **Alt + ,** and drag over the text you want to read. This sets the region.
4. Press **Alt + .** to read the text. The new text shows in the window and is copied to the clipboard.

That's all. Press **Stop** to turn the hotkeys off.

> The first start creates `settings.json` next to the exe. Startup takes 1–2 seconds because the
> exe unpacks itself.

---

## 2. The window

| Part | What it does |
|---|---|
| **Hotkey boxes** | Show the hotkey for each action. To change one, click the box and press the new keys together (for example hold **Alt + Shift**, then press **/**). The box fills in the name by itself (`Alt+Shift+Slash`). **Backspace** empties a box, which turns that action off. **Esc** cancels the change. The boxes are locked while the app is running. |
| **Reset hotkeys to defaults** | Puts back the default hotkeys. |
| **Region: …** | Shows the current text region (position and size in screen pixels). |
| **Start / Stop** | **Start** turns the hotkeys on for the whole PC. **Stop** turns them off. |
| **Status line** | Tells you what is happening, or what went wrong (red). |
| **New text box** | Every piece of new text you capture. |
| **Clear** | Empties the box **and** forgets the last capture, so the next capture returns all the text again. |
| **Open captures folder** | Opens the folder where the screenshots are saved. |

Every change is saved to `settings.json` right away.

---

## 3. Current hotkeys

| Setting name | Default hotkey | What it does |
|---|---|---|
| `set_region` | **Alt + ,** (`Alt+Comma`) | Drag with the mouse to choose the text region. **Esc** or a right click cancels. |
| `capture_new_text` | **Alt + .** (`Alt+Period`) | Reads the region and gives you **only the text that is new** since the last capture. |
| `capture_image` | **Alt + /** (`Alt+Slash`) | Click a **start** point, then an **end** point. The rectangle is saved silently. |
| `capture_freeform_image` | **Alt + Shift + /** (`Alt+Shift+Slash`) | Click a **start** point, move the mouse around the shape, click again. The shape is closed with a straight line back to the start and saved silently. |

`Alt+Period` is the **.** key next to **,**. If you meant the **.** on the number pad, click the box and press
**Alt + numpad .**. It will show as `Alt+Decimal`.

### Where the hotkeys are defined

There are two places. **`settings.json` always wins.**

1. **`settings.json` (next to the exe), lines 3–6.** These are the hotkeys the app really uses:

   ```json
   "hotkeys": {
     "set_region": "Alt+Comma",
     "capture_new_text": "Alt+Period",
     "capture_image": "Alt+Slash",
     "capture_freeform_image": "Alt+Shift+Slash"
   },
   ```

2. **`ocr_capture/config.py`, lines 52–57 (`DEFAULT_HOTKEYS`).** These are the defaults. They are used
   when `settings.json` does not exist yet, when a line in it is missing or wrong, and when you press
   **Reset hotkeys to defaults**.

### How to change a hotkey (pick one way)

- **In the app (easiest):** press **Stop**, click the box, press the new keys. Done. It is saved right away.
- **In `settings.json`:** change the text on that line, save the file, then press **Stop** and **Start**
  in the app. You do **not** need to restart the app, because **Start** always reads `settings.json` again.
- **As a new default (source code):** change the line in `ocr_capture/config.py`, rebuild the exe, then
  delete `settings.json` (or press **Reset hotkeys to defaults**).

Hotkey format: modifiers, then one key, joined with `+`. For example `Ctrl+Alt+F9` or `Win+Shift+Q`.
Modifiers are `Ctrl`, `Alt`, `Shift`, `Win`. Keys are `A`–`Z`, `0`–`9`, `F1`–`F24`, `Numpad0`–`Numpad9`,
`Comma`, `Period`, `Slash`, `Semicolon`, `Quote`, `Minus`, `Equals`, `Backtick`, `LeftBracket`,
`RightBracket`, `Backslash`, `Space`, `Enter`, `Tab`, `Insert`, `Delete`, `Home`, `End`, `PageUp`,
`PageDown`, `Up`, `Down`, `Left`, `Right`, `Decimal`, `Add`, `Subtract`, `Multiply`, `Divide`,
`PrintScreen`, `Pause`. The full list is in `ocr_capture/hotkey_spec.py`.

Rules:
- A hotkey needs **Ctrl, Alt or Win**, so normal typing is never blocked. Only `F1`–`F24` and `Pause` may be used alone.
- Two actions cannot share the same hotkey.
- If another program already uses a hotkey, **Start** tells you which one. Pick a different hotkey.

---

## 4. How each capture works

### Read text (`capture_new_text`)

- The app takes a screenshot of the region and reads it with the **OCR built into Windows**. Nothing extra needs to be installed.
- The text **keeps its layout**: line breaks, empty lines, indentation and wide gaps between words are rebuilt from where each word sits on screen.
- The app **remembers the last result** and gives you only what changed:
  - a line that grew (`Hello` → `Hello world`) gives only `world`;
  - new lines at the bottom are returned whole;
  - lines that scrolled away, or that OCR read slightly differently (`He1lo` vs `Hello`), give nothing.
- The new text is shown in the window and copied to the clipboard. If nothing changed, the status says "No new text."
- Setting a new region or pressing **Clear** makes the app forget, so the next capture returns everything.

### Silent screenshots (`capture_image`, `capture_freeform_image`)

- Nothing is drawn on screen and the mouse cursor does not change. The app just listens to your clicks.
- The clicks you use are **not** passed to the program under the mouse, so you never click a button by accident.
- **Right click**, pressing the **same hotkey again**, or waiting 60 seconds cancels.
- The image is saved in the `captures` folder next to the exe (for example `image_20261001_101530_123456.png`) and copied to the clipboard.
- Freeform images are PNG files with a transparent area outside the shape. On the clipboard, the outside is white.

---

## 5. Live captioning

**What happens:** captions on screen usually scroll up and grow at the bottom. Each capture is compared
with the previous one, and only the new words come out. So if you capture again and again, you get a
clean stream of new caption text with no repeats.

**How to set it up:**

1. Press **Start**, then **Alt + ,** and drag over the caption area only (smaller area = faster and more accurate).
2. Open `settings.json` and set the interval in milliseconds, for example:
   ```json
   "text_capture": {
     "live_caption_interval_ms": 1000,
     "transcript_file": "transcript.txt"
   }
   ```
   - `live_caption_interval_ms`: `0` means "capture once per key press". A number (200 or more) means
     the hotkey turns **automatic capturing** on and off, every that many milliseconds.
   - `transcript_file`: every new piece of text is also added to this file (next to the exe). Leave it `""` to turn it off.
3. Press **Stop** and **Start** so the app reads the file again.
4. Press **Alt + .** once to begin. Press it again to stop.

Tips:
- 500–1000 ms works well. If a capture is still running when the next one is due, the next one is skipped, so it never piles up.
- If captions are re-read too often (OCR noise), lower `similarity_threshold` a little (for example `0.7`).
  If real changes are missed, raise it (for example `0.9`).

**In the code:** the comparison logic is `ocr_capture/text_diff.py` (`NewTextTracker`). The timer is in
`ocr_capture/capture_controller.py` (`capture_new_text` and `_live_timer`).

---

## 6. All settings (`settings.json`)

| Setting | Default | Meaning |
|---|---|---|
| `hotkeys.*` | see above | The hotkey for each action. `""` = action off. |
| `region` | `null` | The text region. Set with the `set_region` hotkey. |
| `ocr.language` | `""` | `""` = Windows display language. Or a tag like `"en-US"`, `"de-DE"`. The Windows language pack must be installed. |
| `ocr.upscale_factor` | `2.0` | Enlarges the image before reading (1.0–4.0). Higher helps with small text. |
| `text_capture.preserve_layout` | `true` | Keep spacing and empty lines. `false` = simple lines with single spaces. |
| `text_capture.similarity_threshold` | `0.8` | How alike two lines must be (0–1) to count as "the same line". |
| `text_capture.copy_to_clipboard` | `true` | Copy new text to the clipboard. |
| `text_capture.transcript_file` | `""` | File that new text is added to. `""` = off. |
| `text_capture.live_caption_interval_ms` | `0` | `0` = one capture per key press. 200 or more = automatic capture (see section 5). |
| `image_capture.output_folder` | `"captures"` | Where screenshots go. Relative paths are next to the exe. |
| `image_capture.file_format` | `"png"` | `png`, `jpg` or `bmp`. Only `png` keeps transparency. |
| `image_capture.copy_to_clipboard` | `true` | Copy screenshots to the clipboard. |
| `image_capture.background_color` | `"#FFFFFF"` | Colour used where transparency cannot be kept. |
| `selection.timeout_seconds` | `60.0` | An unfinished silent selection is cancelled after this. |
| `selection.freeform_min_point_distance_px` | `3` | Freeform path: ignore mouse moves shorter than this. |

If a value is wrong, the app uses its default and shows a red message. If the file is broken (not valid
JSON), it is renamed to `settings.json.broken-<date>` and a fresh one is created. All defaults live in
`ocr_capture/config.py`.

---

## 7. Move to another PC

Copy these into one folder on the new PC:

- `OcrRegionCapture.exe`
- `settings.json` (your hotkeys, region and options)

Nothing else to install. The new PC needs Windows 10 or 11. To read a language other than English, that
Windows language must be installed (**Settings → Time & language → Language**).

To check that text reading works on the new PC, run `OcrRegionCapture.exe --check-ocr`. Then open
`ocr_region_capture.log` next to the exe. It should say `OCR check read 'OCR check 12345'`.

Files the app creates next to the exe:

| File | What it is |
|---|---|
| `settings.json` | Your settings. |
| `captures\` | Saved screenshots. |
| `ocr_region_capture.log` | Log file, useful when something goes wrong. |

> Put the app in a folder you can write to (for example `Documents\OcrRegionCapture`), not in
> `C:\Program Files`, or settings cannot be saved.

---

## 8. For developers

### Run from source

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python run_app.py
```

### Run the tests

```powershell
.\.venv\Scripts\python -m pytest -q
```

### Build the exe

```powershell
.\build_exe.ps1
```

This installs the packages, runs the tests, and builds `dist\OcrRegionCapture.exe`. Close the app before building.

### Project structure

| File | Job |
|---|---|
| `ocr_capture/config.py` | **Every tunable value and the default hotkeys.** Change values here, not in the logic files. |
| `ocr_capture/settings.py` | Loads and saves `settings.json`. Bad values fall back to defaults. |
| `ocr_capture/hotkey_spec.py` | Reads, checks and formats hotkey text (`Alt+Shift+Slash`). |
| `ocr_capture/win32/hotkeys.py` | Turns hotkeys on and off for the whole PC (`RegisterHotKey`). |
| `ocr_capture/win32/mouse_hook.py` | Listens to the mouse on its own thread during silent selection. |
| `ocr_capture/point_picker.py` | Click logic for silent selection (start / end / cancel). |
| `ocr_capture/silent_selector.py` | One silent selection: mouse listener + click logic + timeout. |
| `ocr_capture/region_selector.py` | The drag overlay for `set_region`. |
| `ocr_capture/screen_capture.py` | Silent screenshots. |
| `ocr_capture/ocr_engine.py` | Windows OCR. Swap in another engine by implementing `TextRecognizer`. |
| `ocr_capture/text_layout.py` | Rebuilds spacing and line breaks from word positions. |
| `ocr_capture/text_diff.py` | Finds only the new text (live captioning). |
| `ocr_capture/image_output.py` | Freeform mask, saving images. |
| `ocr_capture/capture_controller.py` | What each hotkey does. |
| `ocr_capture/ui/` | The window and the hotkey box. |
| `ocr_capture/app.py` | Starts the app and connects everything. |

### Add a new hotkey action

1. `config.py`: add a member to `HotkeyAction`, plus a default hotkey in `DEFAULT_HOTKEYS`, a label in
   `ACTION_LABELS` and a tooltip in `ACTION_TOOLTIPS`.
2. `capture_controller.py`: add a handler to `self._handlers`.

The window, `settings.json` and hotkey registration pick it up automatically.

---

## 9. Troubleshooting

| Problem | Fix |
|---|---|
| "already used by another program" on Start | Another app owns that hotkey. Choose a different one. |
| "No region yet" | Press the `set_region` hotkey (default **Alt + ,**) and drag. |
| Text is wrong or missing | Make the region tighter around the text, or raise `ocr.upscale_factor` to `3.0`. |
| "OCR language … is not installed" | Install that language in Windows settings, or set `ocr.language` to `""`. |
| Esc does not close the region overlay | Right click instead (Windows sometimes keeps keyboard focus in the other app). |
| Settings not saved | Move the app to a folder you can write to. |
| Anything else | Look in `ocr_region_capture.log` next to the exe. |
