#!/usr/bin/env python3
"""BryMaps — fresh OpenStreetMap maps for Bryton Aero 60 / Rider 450 GPS units.

A PySide6 + QML desktop app (Windows / Linux). Pick an area on the map or a country from the
list, build a Bryton-format .dat, and install it to the device — plus one-click backup of the
maps currently on the device. Reuses the Sommet (ambit-app) desktop theme and map approach.
"""
import sys
from pathlib import Path

from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine, qmlRegisterSingletonType
from PySide6.QtCore import QUrl

from backend import Backend

QML = Path(__file__).resolve().parent / "qml"


def main():
    app = QGuiApplication(sys.argv)
    app.setApplicationName("BryMaps")
    app.setOrganizationName("BryMaps")
    icon = QML.parent.parent / "data" / "icon.png"
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))

    engine = QQmlApplicationEngine()
    engine.addImportPath(str(QML))

    backend = Backend()
    engine.rootContext().setContextProperty("Backend", backend)

    engine.load(QUrl.fromLocalFile(str(QML / "Main.qml")))
    if not engine.rootObjects():
        sys.exit("Failed to load QML")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
