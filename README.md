# OCR Region Capture

A small Windows app that reads text from the screen and takes silent screenshots, using global hotkeys.

- Watch a live-caption area and **paste only the new words** into any text box with one hotkey.
  If nothing is new, nothing is pasted.
- Take a rectangle screenshot **silently**: no grey screen, no crosshair, no visible border.
- Take a **freeform** (any shape) screenshot, also silently.
- Hotkeys work in every program after you press **Start**. They stop after you press **Stop**.
- All settings are saved in `settings.json` next to the exe. Copy both files to another PC and it works the same.

---

## 1. Quick start (use the exe)

1. Open the `dist` folder and double-click **`OcrRegionCapture.exe`**.
2. Press **Start**.
3. Press **Alt + ,** and drag over the text you want (for example the Windows Live Captions box). This sets the region.
4. Click into the text box where you want the words (chat, Notepad, a web form...).
5. Press **Alt + .**. All the text in the region is pasted there.
6. Press **Alt + .** again later: only the text that appeared **since your last paste** is pasted. Nothing new = nothing pasted.

> If the window you read from moves, set the region again (**Alt + ,**). The region is a fixed place on the screen.

That's all. Press **Stop** to turn the hotkeys off.

> The first start creates `settings.json` next to the exe. Startup takes 1–2 seconds because the
> exe unpacks itself.

---

## 2. The window

| Part | What it does |
|---|---|
| **Hotkey boxes** | Show the hotkey for each action. To change one, click the box and press the new keys together (for example hold **Alt + Shift**, then press **/**). The box fills in the name by itself (`Alt+Shift+Slash`). **Backspace** empties a box, which turns that action off. **Esc** cancels the change. The boxes are locked while the app is running. |
| **Reset to defaults** | Puts back the default hotkeys. |
| **Region: …** | Shows the current caption region (position and size in screen pixels). |
| **Start / Stop** (green / red) | **Start** turns the hotkeys on for the whole PC and starts watching the region. **Stop** turns everything off. |
| **Status line** | Tells you what is happening (green), or what went wrong (red). |
| **History** | Every piece of text that was pasted, with the time, oldest at the top. **Double-click** an entry (or select it and press **Copy selected**) to copy it again. |
| **Clear history** | Empties the history list. |
| **Open captures folder** | Opens the folder where the screenshots are saved. |

Every change is saved to `settings.json` right away.

---

## 3. Current hotkeys

| Setting name | Default hotkey | What it does |
|---|---|---|
| `set_region` | **Alt + ,** (`Alt+Comma`) | Drag with the mouse to choose the text region. **Esc** or a right click cancels. |
| `capture_new_text` | **Alt + .** (`Alt+Period`) | Pastes the region's text into the focused text box. First press after Start / set region: **all** text. Next presses: only text that is **new since the last paste**. Nothing new = nothing pasted. |
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

2. **`ocr_capture/config.py`, lines 56–61 (`DEFAULT_HOTKEYS`).** These are the defaults. They are used
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

### Paste new text (`capture_new_text`)

Works with any text on screen: live captions, a chat, a web page, a document.

- After **Start**, the app quietly reads the region about twice a second with the **OCR built into Windows**
  (nothing extra to install) and collects the words in a hidden buffer.
- The **first** reading after Start or after setting the region puts **all** the text in the buffer.
  Later readings add only words that were not there before.
- When you press **Alt + .**, the app reads the region once more, then:
  - **pastes** the collected words into the text box that has the focus (it waits until you let go of Alt, then presses Ctrl+V for you);
  - leaves them on the clipboard and adds them to the **History** list;
  - empties the buffer, so the next press gives only words that come after this one.
- **No new words = nothing happens.** Nothing is pasted and the clipboard is not touched.
  The status says "No new text since the last paste", or "No text found in the region" if the region shows no text at all.
- The words are pasted as one line, separated by single spaces (captions re-wrap, so their line breaks mean nothing).
- Words are never lost when captions scroll away between presses, because the region is read in the background.
- Consecutive pastes get a space in between, so the words do not run together.
- If this app's own window has the focus, nothing is pasted (click into your target box first).

### Silent screenshots (`capture_image`, `capture_freeform_image`)

- Nothing is drawn on screen and the mouse cursor does not change. The app just listens to your clicks.
- The clicks you use are **not** passed to the program under the mouse, so you never click a button by accident.
- **Right click**, pressing the **same hotkey again**, or waiting 60 seconds cancels.
- The image is saved in the `captures` folder next to the exe (for example `image_20261001_101530_123456.png`) and copied to the clipboard.
- Freeform images are PNG files with a transparent area outside the shape. On the clipboard, the outside is white.

---

## 5. Live captioning

**How it works (simple version):**

1. **Background reading.** While running, the region is read every 0.5 s (`poll_interval_ms`).
2. **Compare words, not lines.** Captions are one long stream of words seen through a small window:
   old words scroll away at the top, new words appear at the end, and lines re-wrap all the time.
   So each new reading is turned into a list of words and lined up against the previous reading.
3. **Find the overlap.** The last place where at least 2 words in a row match (the "anchor") is where
   the old text ends. Every word after it is new and goes into the buffer. Case and punctuation are
   ignored (`and.` = `And`), and one or two misread words inside the overlap are tolerated.
4. **Corrections.** Caption engines often fix their last word (`Mundy` → `Monday`). If a word at the end
   of the previous reading disappears, it is taken back out of the buffer (if it was not pasted yet),
   so you get `Monday`, not `Mundy Monday`.
5. **Deliver on demand.** The hotkey hands out the buffer and empties it. Empty buffer = nothing pasted.

**Tips:**

- Drag the region over the caption text only. A smaller area is faster and more accurate.
- Windows Live Captions: put its window over a plain background, because the box is a little see-through.
- To also keep a full log of everything you pasted, set `"transcript_file": "transcript.txt"`.
- To save CPU, raise `poll_interval_ms` (for example `1000`). With `0` there is no background reading:
  each press reads the screen once, so words that scrolled away between two presses are missed.

**In the code:** word comparison is in `ocr_capture/text_diff.py` (`diff_caption_words`, `CaptionTracker`).
Background reading and delivery are in `ocr_capture/capture_controller.py` (`_poll_timer`, `_request_read`,
`_deliver`). Pasting is in `ocr_capture/auto_paster.py`.

---

## 6. All settings (`settings.json`)

| Setting | Default | Meaning |
|---|---|---|
| `hotkeys.*` | see above | The hotkey for each action. `""` = action off. |
| `region` | `null` | The text region. Set with the `set_region` hotkey. |
| `ocr.language` | `""` | `""` = Windows display language. Or a tag like `"en-US"`, `"de-DE"`. The Windows language pack must be installed. |
| `ocr.upscale_factor` | `2.0` | Enlarges the image before reading (1.0–4.0). Higher helps with small text. |
| `text_capture.poll_interval_ms` | `500` | Read the region in the background every N ms (200 or more). `0` = only read when the hotkey is pressed. |
| `text_capture.auto_paste` | `true` | Paste new words into the focused text box. `false` = only copy them. |
| `text_capture.copy_to_clipboard` | `true` | Copy new words to the clipboard when `auto_paste` is `false`. |
| `text_capture.paste_separator` | `" "` | Put before each paste except the first one after Start / set region. |
| `text_capture.transcript_file` | `""` | File that every pasted text is added to. `""` = off. |
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
| `ocr_capture/text_layout.py` | OCR word/line types; rebuilds spacing and line breaks from word positions (used by `--check-ocr`). |
| `ocr_capture/text_diff.py` | Finds only the new caption words (`CaptionTracker`). |
| `ocr_capture/auto_paster.py` | Waits for you to release the hotkey, then presses Ctrl+V in the focused box. |
| `ocr_capture/ui/theme.py` | All colours and the window style. |
| `assets/app.ico` | App icon (window, taskbar, exe). Rebuild it from `assets/app_icon_source.jpg` with `python tools/make_icon.py`. |
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
| "No text found in the region" | The region shows no text. The window probably moved: set the region again with **Alt + ,**. |
| "No new text since the last paste" | Everything in the region was already pasted. New text will be pasted when it appears. |
| Words are not pasted | Click into the target text box first. Programs running as administrator do not accept pasting from a normal app; run this app as administrator too. |
| Text is wrong or missing | Make the region tighter around the text, or raise `ocr.upscale_factor` to `3.0`. |
| "OCR language … is not installed" | Install that language in Windows settings, or set `ocr.language` to `""`. |
| Esc does not close the region overlay | Right click instead (Windows sometimes keeps keyboard focus in the other app). |
| Settings not saved | Move the app to a folder you can write to. |
| Anything else | Look in `ocr_region_capture.log` next to the exe. |
