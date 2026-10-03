```diff
--- a/src/multi_ai_gui/main.py
+++ b/src/multi_ai_gui/main.py
@@ -246,9 +246,6 @@ class MainWindow(QMainWindow):
         self.process: QProcess | None = None
         self._stdout_buffer = ""
         self._pause_waiting = False
-        self._command_running = False
-        self._response_done_timer = QTimer(self)
-        self._response_done_timer.setSingleShot(True)
-        self._response_done_timer.timeout.connect(self._on_command_output_idle)
         self._last_output_had_newline = True
 
         self._build_ui()
@@ -730,8 +727,6 @@ class MainWindow(QMainWindow):
 
         self._stdout_buffer = ""
         self._pause_waiting = False
-        self._command_running = False
-        self._response_done_timer.stop()
         self._last_output_had_newline = True
         self.btn_continue.setEnabled(False)
         self.btn_abort.setEnabled(False)
@@ -775,18 +770,19 @@ class MainWindow(QMainWindow):
         self._last_output_had_newline = text.endswith("\n")
 
         if PAUSE_PROMPT in self._stdout_buffer and not self._pause_waiting:
-            self._response_done_timer.stop()
             self._set_pause_waiting(True)
 
         while "\n" in self._stdout_buffer:
             line, self._stdout_buffer = self._stdout_buffer.split("\n", 1)
             self.log_view.appendPlainText(line)
 
-        if self._command_running and not self._pause_waiting:
-            self._response_done_timer.start(1000)
+            if line.startswith("[*] Result saved to '") and not self._pause_waiting:
+                if self.process is not None and self.process.state() == QProcess.Running:
+                    self._set_repl_status("Running", "#4ec9b0")
 
         scrollbar = self.log_view.verticalScrollBar()
         if scrollbar:
             scrollbar.setValue(scrollbar.maximum())
 
@@ -799,8 +795,6 @@ class MainWindow(QMainWindow):
             self.log_view.appendPlainText(self._stdout_buffer.rstrip("\r"))
             self._stdout_buffer = ""
 
-        self._command_running = False
-        self._response_done_timer.stop()
         self._pause_waiting = False
         self.btn_continue.setEnabled(False)
         self.btn_abort.setEnabled(False)
@@ -824,8 +818,6 @@ class MainWindow(QMainWindow):
     def _on_process_error(self, error: QProcess.ProcessError) -> None:
         self._set_repl_status("Error", "#f48771")
         self._pause_waiting = False
-        self._command_running = False
-        self._response_done_timer.stop()
         self.btn_continue.setEnabled(False)
         self.btn_abort.setEnabled(False)
         self.btn_send.setEnabled(False)
@@ -888,20 +880,12 @@ class MainWindow(QMainWindow):
             QMessageBox.warning(
                 self, "REPL Not Running", "The REPL process is not running."
             )
             return
-        self._command_running = True
-        self._response_done_timer.stop()
         self._set_repl_status("Processing...", "#dcdcaa")
 
         self.log_view.appendPlainText(command)
         self.log_view.appendPlainText("")
         self.process.write((command + "\n").encode("utf-8"))
-
-    def _on_command_output_idle(self) -> None:
-        if not self._command_running or self._pause_waiting:
-            return
-        if self.process is None or self.process.state() != QProcess.Running:
-            return
-        self._command_running = False
-        self.log_view.appendPlainText("[INFO] Response completed.")
-        self._set_repl_status("Running", "#4ec9b0")
 
     def _on_send(self) -> None:
         flow_data = self.flow_edit.toPlainText().strip()
@@ -931,8 +915,6 @@ class MainWindow(QMainWindow):
             return
 
         self.process.write(b"\n")
-        self._command_running = True
-        self._response_done_timer.stop()
         self._set_pause_waiting(False)
 
     def _on_abort_pause(self) -> None:
@@ -946,8 +928,6 @@ class MainWindow(QMainWindow):
             return
 
         self.process.write(b"q\n")
-        self._command_running = True
-        self._response_done_timer.stop()
         self._set_pause_waiting(False)
```

補足だけすると、この差分で:

- 擬似完了タイマーを撤去
- `[*] Result saved to '...'` 行を見たら
  - pause 中でなければ
  - REPL が生きていれば
  - ステータスを `Running` に戻す

になります。

必要なら次に、これを反映した**関数ごとの完成版コード**で出せます。