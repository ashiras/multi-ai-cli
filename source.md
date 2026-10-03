了解です。  
では **ステータスバー通知 + TERMINAL ログ出力 + 重複通知防止** を入れた完成版を出します。

---

# 変更内容
`MainWindow` に以下を追加します。

- `self._last_result_saved_line: str | None = None`
- `_notify_result_saved()` helper
- `_on_ready_read_stdout()` から helper を呼ぶ

これで:

- `[*] Result saved to 'test.txt'` を検出
- ステータスバーに `Output saved to test.txt`
- TERMINAL に `[INFO] Output saved to test.txt`
- 同じ行での重複通知はしない

---

# 修正版 `src/multi_ai_gui/window.py` の差し替えポイント

## 1. `__init__()` に状態を追加
このあたり:

```python
self.process: QProcess | None = None
self._stdout_buffer = ""
self._pause_waiting = False
self._last_output_had_newline = True
```

を、こうします。

```python
self.process: QProcess | None = None
self._stdout_buffer = ""
self._pause_waiting = False
self._last_output_had_newline = True
self._last_result_saved_line: str | None = None
```

---

## 2. `_start_repl_session()` で初期化
このあたり:

```python
self._stdout_buffer = ""
self._pause_waiting = False
self._last_output_had_newline = True
```

を、こうします。

```python
self._stdout_buffer = ""
self._pause_waiting = False
self._last_output_had_newline = True
self._last_result_saved_line = None
```

---

## 3. helper メソッドを追加
`_on_ready_read_stdout()` の前後あたりに、これを追加してください。

```python
def _notify_result_saved(self, text: str) -> None:
    """Notify the user when CLI output has been saved to a file."""
    for line in text.splitlines():
        marker_index = line.find(RESULT_SAVED_MARKER)
        if marker_index == -1:
            continue

        if line == self._last_result_saved_line:
            return

        saved_part = line[marker_index + len(RESULT_SAVED_MARKER) :]
        end_index = saved_part.find("'")
        if end_index == -1:
            continue

        saved_path = saved_part[:end_index]
        message = f"Output saved to {saved_path}"

        self._last_result_saved_line = line
        self._set_repl_status("Running", "#4ec9b0")
        self.status_bar.showMessage(message, 5000)
        self.log_view.appendPlainText(f"[INFO] {message}")
        return

    if self._last_result_saved_line != RESULT_SAVED_MARKER:
        self._last_result_saved_line = RESULT_SAVED_MARKER
        self._set_repl_status("Running", "#4ec9b0")
        self.status_bar.showMessage("Output file saved.", 5000)
        self.log_view.appendPlainText("[INFO] Output file saved.")
```

---

## 4. `_on_ready_read_stdout()` を差し替え
このメソッドを以下に置き換えてください。

```python
def _on_ready_read_stdout(self) -> None:
    if not self.process:
        return

    data = self.process.readAllStandardOutput()
    text = bytes(data.data()).decode("utf-8", errors="replace")
    text = self._normalize_log_text(text)

    if (
        text.startswith("[*]")
        and not self._last_output_had_newline
        and not self._stdout_buffer.endswith("\n")
    ):
        self._stdout_buffer += "\n"

    self._stdout_buffer += text
    self._last_output_had_newline = text.endswith("\n")

    if PAUSE_PROMPT in self._stdout_buffer:
        self._stdout_buffer = self._stdout_buffer.replace(PAUSE_PROMPT, "")
        if not self._pause_waiting:
            self._set_pause_waiting(True)

    if RESULT_SAVED_MARKER in self._stdout_buffer and not self._pause_waiting:
        self._notify_result_saved(self._stdout_buffer)

    while "\n" in self._stdout_buffer:
        line, self._stdout_buffer = self._stdout_buffer.split("\n", 1)
        if line.strip():
            self.log_view.appendPlainText(line)
        else:
            self.log_view.appendPlainText("")

    scrollbar = self.log_view.verticalScrollBar()
    if scrollbar:
        scrollbar.setValue(scrollbar.maximum())
```

---

# ちょっとだけ注意
この版は「同じ保存通知行」に対して重複防止します。  
たとえば連続で:

- `[*] Result saved to 'test.txt'`
- `[*] Result saved to 'test.txt'`

が来た場合、**2回目は出ません**。

もし「同じファイル名でも別タイミングなら毎回通知したい」なら、  
`line` ベースではなく「1回バッファから処理した通知は消す」方式にします。  
ただ、通常の CLI 利用なら今の重複防止で十分なことが多いです。

---

# おすすめ改善
もし「同じ `test.txt` に対してコマンドを2回実行したら、2回とも通知したい」なら、  
次はこういう設計のほうが自然です。

- `_stdout_buffer` を行単位で処理
- `RESULT_SAVED_MARKER` を含む行を見つけたら、その行をその場で通知して通常ログにも流す
- 重複は「同じ読み取りイベント内」だけ防ぐ

このほうが UX 的にはさらに自然です。

---

必要なら次に、  
**「同じファイル名でも別実行なら毎回通知される、より自然な完成版」**  
にアップグレードした版も出せます。