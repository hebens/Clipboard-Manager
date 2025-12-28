import sys
import os

# Erzwingt die DPI-Skalierung für Windows, bevor die GUI geladen wird
os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"
os.environ["QT_AUTOSCREENSCALEFACTOR"] = "1"

from datetime import time, datetime
from pynput import keyboard
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, 
                             QVBoxLayout, QHBoxLayout, QWidget, QComboBox, QLabel, QFileDialog)
from PyQt6.QtCore import Qt, QThread, QPoint
from recorder import ScreenRecorder

class ScreenCaptureApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.recorder = ScreenRecorder()
        app = QApplication.instance()
        screen = app.primaryScreen()
        if screen:
            self.recorder.device_pixel_ratio = screen.devicePixelRatio()

        self.old_pos = QPoint()
        self.blink_state = False
        self.init_ui()
        # Globalen Hotkey-Listener initialisieren
        self.listener = keyboard.GlobalHotKeys({
            '<f10>': self.toggle_recording
        })
        self.listener.start()

    def init_ui(self):
        #layout = QVBoxLayout()
        
        # Main Widget mit Styling
        self.main_container = QWidget()
        self.main_container.setObjectName("Toolbar")
        self.setCentralWidget(self.main_container) 

        self.toolbar_layout = QHBoxLayout(self.main_container)
        self.toolbar_layout.setContentsMargins(10, 5, 10, 5)
        self.toolbar_layout.setSpacing(10)

        # Fenster-Eigenschaften
        self.setWindowTitle("PyCap Mini")
        self.setFixedSize(450, 60)
        # Hält das Fenster immer im Vordergrund
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.main_container.setStyleSheet("""
            QWidget#Toolbar {
                background-color: #2c3e50;
                border-radius: 10px;
                border: 1px solid #34495e;
            }
            QPushButton {
                background: transparent;
                color: white;
                font-weight: bold;
                border: none;
                padding: 5px 15px;
            }
            QPushButton:hover { background-color: #34495e; }
            QPushButton:disabled { color: #7f8c8d; }
        """)

        # Handle-Icon am Anfang des Layouts ein
        drag_handle = QLabel("⋮⋮")
        drag_handle.setObjectName("DragHandle")
        drag_handle.setStyleSheet("color: #555; font-size: 18px;")
        self.toolbar_layout.addWidget(drag_handle)
        
        self.status_indicator = QLabel("●")
        self.status_indicator.setStyleSheet("color: #2ecc71; font-size: 14px; margin-left: 5px;") # Startet Grün

        self.status_label = QLabel("Start")
        self.status_label.setStyleSheet("color: #888; font-size: 10px; font-family: 'Segoe UI';")

        # Ein kleiner vertikaler Container für den Text-Status
        status_container = QWidget()
        status_layout = QVBoxLayout(status_container)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(0)
        status_layout.addWidget(self.status_indicator, alignment=Qt.AlignmentFlag.AlignCenter)
        status_layout.addWidget(self.status_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.toolbar_layout.addWidget(status_container)

        # Format Auswahl mittels ComboBox
        self.format_box = QComboBox()
        self.format_box.addItems(["MP4 Video", "GIF Anim", "PNG Snap"])
        self.format_box.setFixedWidth(90)
        self.toolbar_layout.addWidget(self.format_box)
        
        #  Buttons & Connections
        self.area_btn = QPushButton("Area")
        self.area_btn.clicked.connect(self.open_area_selector)

        self.record_btn = QPushButton("● Start")
        self.record_btn.setObjectName("RecordBtn")
        self.record_btn.clicked.connect(self.start_capture)

        self.stop_btn = QPushButton("■ Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_capture)
    
        self.close_btn = QPushButton("✕")
        self.close_btn.setStyleSheet("background-color: transparent; color: #888;")
        self.close_btn.clicked.connect(self.close)

        # ... (Events wie zuvor verknüpfen)
        self.toolbar_layout.addWidget(self.area_btn)
        self.toolbar_layout.addWidget(self.record_btn)
        self.toolbar_layout.addWidget(self.stop_btn)
        self.toolbar_layout.addWidget(self.close_btn)

        # Timer für blinkenden Punkt
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self._toggle_blink)

    def _toggle_blink(self):
        if self.recorder.recording:
            self.blink_state = not self.blink_state
            color = "#e74c3c" if self.blink_state else "#1e1e1e"
            self.status_dot.setStyleSheet(f"color: {color}; font-size: 14px;")

    def open_area_selector(self):
        """Öffnet das transparente Overlay zur Bereichswahl."""
        from selector import AreaSelector        
        self.selector = AreaSelector()
        # WICHTIG: Damit 'destroyed' zuverlässig gefeuert wird
        self.selector.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.selector.showFullScreen()
        # Sobald das Fenster geschlossen wird, holen wir die Region
        self.selector.destroyed.connect(self.update_region_info)

    def update_region_info(self):
        if hasattr(self, 'selector') and self.selector.selected_region:
            reg = self.selector.selected_region
            self.recorder.region = reg
            self.record_btn.setText("● Ready")
            self.status_label.setText(f"{reg['width']}x{reg['height']}")
            self.status_indicator.setStyleSheet("color: #3498db;") # Blau für "Bereich gewählt"

    def start_capture(self):
        self.record_btn.setEnabled(False)
        self.status_label.setText("Aufnahme startet in 3...")

        # Ein einfacher QTimer, um die GUI nicht einfrieren zu lassen
        QTimer.singleShot(1000, lambda: self.status_label.setText("Aufnahme startet in 2..."))
        QTimer.singleShot(2000, lambda: self.status_label.setText("Aufnahme startet in 1..."))
        QTimer.singleShot(3000, self._start_capture) 
    
    def _start_capture(self):
        fmt_text = self.format_box.currentText()
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if "PNG" in fmt_text:
            # Schneller Screenshot ohne Thread
            file_path, _ = QFileDialog.getSaveFileName(self, "Speichern Unter", f"Snappshot_{timestamp}", "Image (*.png)")
            if file_path:
                self.recorder.take_screenshot(file_path)
                self.status_label.setText("Screenshot gespeichert!")

            self.record_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
        else:
            # Video/GIF Aufnahme starten
            self.status_label.setText("Recording")
            self.status_indicator.setStyleSheet("color: #e74c3c;") # Rot für Aufnahme
            self.record_btn.setEnabled(False)
            self.stop_btn.setEnabled(True)
            self.area_btn.setEnabled(False)
            
            self.rec_thread = RecordingThread(self.recorder)
            self.rec_thread.start()

    def stop_capture(self):
        # Thread stoppen
        self.recorder.recording = False
        self.status_label.setText("Verarbeitung...")
        
        if hasattr(self, 'rec_thread'):
            self.rec_thread.wait() # Warten bis Thread sauber beendet ist

        # Dateidialog basierend auf Format
        fmt_selection = self.format_box.currentText()
        ext = ".mp4" if "MP4" in fmt_selection else ".gif"
        filter_str = "Video (*.mp4)" if ext == ".mp4" else "GIF (*.gif)"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Speichern unter", 
            os.path.join(os.path.expanduser("~"), "Desktop", f"Capture_{timestamp}"), filter_str)
        full_path = f"{file_path}_{timestamp}{ext}" 

        if file_path:
            fmt_key = "mp4" if ext == ".mp4" else "gif"
            # Übergabe an den Recorder (der nutzt jetzt OpenCV/ImageIO)
            self.recorder.stop_and_save(format=fmt_key, filename=full_path) # file_path
            self.status_label.setText("Datei gespeichert!")
        else:
            self.status_label.setText("Abgebrochen. RAM geleert.")
            self.recorder.frames = []

        # UI zurücksetzen
        self.record_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.area_btn.setEnabled(True)

    def toggle_recording(self):
        """ Wird aufgerufen, wenn F10 gedrückt wird (egal welche App im Fokus ist).
            
            Wichtiger Hinweis für macOS (Berechtigungen)
            Unter macOS ist pynput (genau wie mss) auf die Bedienungshilfen-Berechtigung angewiesen. Wenn der Hotkey nicht reagiert:
            Systemeinstellungen -> Datenschutz & Sicherheit.
            Bedienungshilfen (Accessibility).
            Dein Terminal oder deine IDE (z.B. PyCharm/VS Code) hinzufügen und aktivieren.
        """
        if not self.recorder.recording:
            # Da der Listener in einem eigenen Thread läuft, müssen wir 
            # GUI-Änderungen vorsichtig handhaben (Thread-Safety)
            print("Hotkey: Start")
            # Wir rufen die existierende Methode auf
            # Wichtig: In PyQt sollte man eigentlich Signale nutzen, 
            # für diesen Prototyp rufen wir es direkt auf:
            self.start_capture()
        else:
            print("Hotkey: Stop")
            self.stop_capture()
    
    # Mouse-Events zum Verschieben des fensterlosen Widgets
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if not self.old_pos.isNull():
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

class RecordingThread(QThread):
    """Worker-Thread, um die GUI während der Aufnahme flüssig zu halten."""
    def __init__(self, recorder):
        super().__init__()
        self.recorder = recorder

    def run(self):
        self.recorder.start_recording()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    # Stylesheet für einen moderneren Look (optional)
    app.setStyleSheet("QPushButton { height: 30px; }")
    window = ScreenCaptureApp()
    window.show()
    sys.exit(app.exec())