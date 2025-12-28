import os
import mss
import cv2
import numpy as np
from datetime import datetime, time
#import time
import platform
import pyautogui
from processor import VideoProcessor

class ScreenRecorder:
    def __init__(self):
        """Initialisiert den Recorder mit Standardwerten."""
        self.frames = []
        self.recording = False
        self.region = None  # Initialisierung verhindert AttributeError
        self.processor = VideoProcessor()
        self.device_pixel_ratio = 1.0  # Standardwert 1 (kein Retina)

    def start_recording(self):
        """Startet den Capture-Loop. Muss in einem eigenen Thread laufen."""
        self.recording = True
        self.frames = []
        
        # 'with' stellt sicher, dass Ressourcen (GDI/Quartz) im Thread 
        # korrekt initialisiert und wieder freigegeben werden.
        with mss.mss() as sct:
            # Falls keine Region über das GUI gewählt wurde -> Primärmonitor
            if self.region:
                capture_area = self.region 
                print(f"Nehme Bereich auf: {capture_area}")               
            else:
                capture_area = sct.monitors[1]  # Primärmonitor 
                print("Nehme gesamten Monitor auf.")
            # FPS-Kontrolle
            # target_fps = 30
            # frame_duration = 1.0 / target_fps
            
            while self.recording:
                # Screenshot grabben
                sct_img = sct.grab(capture_area)
                
                # start_time = time.time()
                                
                # Konvertierung von BGRA (mss) zu RGB (MoviePy/PIL Standard)
                # Wir machen das direkt hier, um den RAM-Verbrauch pro Frame
                # durch das Entfernen des Alpha-Kanals leicht zu senken.
                frame = np.array(sct_img)
                # Direkt zu RGB
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
                
                # Mausposition relativ zum Aufnahmebereich berechnen
                m_x, m_y = pyautogui.position()

                # Koordinaten-Mapping: Die Mausposition ist global, 
                # wir brauchen sie relativ zur Capture-Area
                rel_x = int((m_x * self.device_pixel_ratio - capture_area['left']))
                rel_y = int((m_y * self.device_pixel_ratio - capture_area['top']))


                os_name = platform.system()
                if os_name == "Darwin":
                    # Für Retina-Displays:
                    rel_x = int((m_x - capture_area['left'] / self.device_pixel_ratio) * self.device_pixel_ratio)

                # Nur zeichnen, wenn die Maus im Aufnahmebereich ist
                if 0 <= rel_x < capture_area['width'] and 0 <= rel_y < capture_area['height']:
                    # Zeichne einen einfachen gelben Kreis als Cursor-Ersatz
                    # (Senior-Tipp: Man könnte hier auch ein Cursor-PNG drüberblenden)
                    cv2.circle(frame, (rel_x, rel_y), 8, (255, 255, 0), -1) # Gelber Punkt
                    cv2.circle(frame, (rel_x, rel_y), 8, (0, 0, 0), 2)      # Schwarzer Rand

                if frame is not None:
                    self.frames.append(frame)
                
                if len(self.frames) % 10 == 0:
                    print(f"Frames aufgenommen: {len(self.frames)}") # Debug-Output

                # Dynamische Pause, um konstante 30 FPS anzustreben
                #elapsed = time.time() - start_time
                #sleep_time = max(0, frame_duration - elapsed)
                time.sleep(1/30)

    def stop_and_save(self, format="mp4", filename="Capture"):
        """Beendet die Aufnahme und delegiert an den VideoProcessor."""
        self.recording = False
        frames_to_process = self.frames

        if not frames_to_process:
            print("Warnung: Keine Frames zum Speichern vorhanden.")
            return

        # Da wir bereits im Loop zu RGB konvertiert haben, 
        # können wir die Frames direkt übergeben.
        print(f"Starte Speicherung als {format} mit {len(frames_to_process)} Frames...")
        # WICHTIG: Wenn 'filename' vom QFileDialog kommt, ist es ein voller Pfad inkl. Endung.
        # Wir prüfen, ob der Pfad bereits existiert, ansonsten bauen wir ihn.

        try: 
            if format == "mp4":
                self.processor.save_as_mp4(frames_to_process, filename) 
            elif format == "gif":
                self.processor.save_as_gif(frames_to_process, filename)
            elif format == "png":
                # Falls wir doch ein Einzelbild aus dem Stream wollen
                cv2.imwrite(f"{filename}.png", cv2.cvtColor(self.frames[-1], cv2.COLOR_RGB2BGR))
        except Exception as e:
            print(f"DEBUG: Fehler in stop_and_save: {e}")   
        finally:
            # 4. Erst wenn der Processor FERTIG ist, leeren wir den RAM
            self.frames = []
            print("Speicher bereinigt.")

    def take_screenshot(self, filename):
        """Erstellt einen sofortigen Screenshot ohne Video-Loop."""
        with mss.mss() as sct:
            capture_area = self.region if self.region else sct.monitors[1]
            sct_img = sct.grab(capture_area)
            img = np.array(sct_img)
            # OpenCV braucht BGR zum Speichern
            cv2.imwrite(filename, cv2.cvtColor(img, cv2.COLOR_BGRA2BGR))