#!/usr/bin/env python3
"""
Phantom OSINT — Entry Point
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        from ui.app import PhantomOSINT
        app = QApplication(sys.argv)
        app.setApplicationName("Phantom OSINT")
        window = PhantomOSINT()
        window.show()
        sys.exit(app.exec())
    except ImportError as e:
        print(f"Missing dependency: {e}\nRun: pip install PyQt6")
        sys.exit(1)

if __name__ == "__main__":
    main()
