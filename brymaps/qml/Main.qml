import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import BryMaps

ApplicationWindow {
    id: win
    visible: true
    width: 1080
    height: 760
    minimumWidth: 820
    minimumHeight: 560
    title: qsTr("BryMaps")
    color: Theme.background

    property var allRegions: []
    property var selRegion: null
    property string outDir: ""
    property string lastDat: ""

    function regionCode(name) {
        var s = (name || "XX").replace(/[^A-Za-z]/g, "").toUpperCase()
        return "C" + (s.length >= 2 ? s.substring(0, 2) : "XX")
    }
    function urlToPath(u) {
        var s = ("" + u).replace(/^file:\/\//, "")
        // Windows: "file:///C:/x" -> "/C:/x" -> "C:/x"
        if (/^\/[A-Za-z]:/.test(s)) s = s.substring(1)
        return decodeURIComponent(s)
    }
    function destOrPrompt() {
        if (win.outDir) return win.outDir
        if (Backend.devicePath) return Backend.devicePath + "/MAP/Update"
        outDirDialog.open(); return ""
    }

    Connections {
        target: Backend
        function onRegionsLoaded(list) { win.allRegions = list; filterRegions(searchField.text) }
        function onLogLine(s) { logArea.text += s + "\n"; logArea.cursorPosition = logArea.length }
        function onProgress(v) { progress.indeterminate = (v < 0); if (v >= 0) progress.value = v }
        function onBuildFinished(ok, msg) {
            status.text = msg
            status.color = ok ? Theme.primary : Theme.error
            if (ok && msg.indexOf(".dat") >= 0) win.lastDat = msg
        }
    }

    function filterRegions(q) {
        q = (q || "").toLowerCase()
        var out = []
        for (var i = 0; i < allRegions.length && out.length < 700; i++) {
            var r = allRegions[i]
            if (!q || r.name.toLowerCase().indexOf(q) >= 0 || (r.parent || "").toLowerCase().indexOf(q) >= 0)
                out.push(r)
        }
        regionList.model = out
    }

    header: ToolBar {
        background: Rectangle { color: Theme.surface }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: Theme.spacingLarge
            anchors.rightMargin: Theme.spacingLarge
            spacing: Theme.spacingMedium
            Text { text: "BryMaps"; color: Theme.text; font.pixelSize: Theme.fontSizeTitle; font.bold: true }
            Text {
                text: qsTr("Fresh OpenStreetMap maps for Bryton Aero 60 / Rider 450")
                color: Theme.mutedText; font.pixelSize: Theme.fontSizeCaption
            }
            Item { Layout.fillWidth: true }
            Rectangle { width: 10; height: 10; radius: 5
                color: Backend.devicePath ? Theme.primary : Theme.error }
            Text {
                text: Backend.devicePath ? qsTr("Bryton connected") : qsTr("No device")
                color: Theme.text; font.pixelSize: Theme.fontSizeLabel
            }
            ToolButton { text: "⟳"; onClicked: Backend.refresh_device() }
        }
    }

    RowLayout {
        anchors.fill: parent
        anchors.margins: Theme.spacingLarge
        spacing: Theme.spacingLarge

        // ── region browser ──
        ColumnLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Theme.spacingMedium

            Text {
                text: qsTr("Choose a country or region")
                color: Theme.text; font.pixelSize: Theme.fontSizeLargeTitle; font.bold: true
            }
            Text {
                text: qsTr("These are free OpenStreetMap extracts from Geofabrik, updated daily. Pick the smallest area that covers where you ride — smaller builds faster and loads faster on the device.")
                color: Theme.mutedText; font.pixelSize: Theme.fontSizeLabel
                Layout.fillWidth: true; wrapMode: Text.WordWrap
            }
            TextField {
                id: searchField
                Layout.fillWidth: true
                placeholderText: qsTr("Search e.g. \"nord-pas\", \"belgium\", \"portugal\"…")
                onTextChanged: filterRegions(text)
            }
            Rectangle {
                Layout.fillWidth: true; Layout.fillHeight: true
                color: Theme.card; radius: Theme.radiusCard; border.color: Theme.border
                ListView {
                    id: regionList
                    anchors.fill: parent; anchors.margins: Theme.spacingSmall
                    clip: true; boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar {}
                    delegate: ItemDelegate {
                        width: regionList.width
                        highlighted: win.selRegion && win.selRegion.id === modelData.id
                        onClicked: win.selRegion = modelData
                        background: Rectangle {
                            color: highlighted ? Theme.cardNested : "transparent"
                            radius: Theme.radiusSmall
                        }
                        contentItem: RowLayout {
                            Column {
                                Layout.fillWidth: true
                                Text { text: modelData.name; color: Theme.text; font.pixelSize: Theme.fontSizeBody }
                                Text { text: modelData.parent || ""; color: Theme.mutedText
                                       font.pixelSize: Theme.fontSizeCaption; visible: !!modelData.parent }
                            }
                            Text {
                                text: modelData.bbox ? Math.round(Math.abs(modelData.bbox[2]-modelData.bbox[0]) *
                                      Math.abs(modelData.bbox[3]-modelData.bbox[1])) + "°²" : ""
                                color: Theme.mutedText; font.pixelSize: Theme.fontSizeCaption
                            }
                        }
                    }
                }
            }
        }

        // ── right: actions ──
        ColumnLayout {
            Layout.preferredWidth: 320
            Layout.fillHeight: true
            spacing: Theme.spacingMedium

            // selection card
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: selCol.implicitHeight + Theme.spacingLarge
                color: Theme.card; radius: Theme.radiusCard; border.color: Theme.border
                ColumnLayout {
                    id: selCol
                    anchors.fill: parent; anchors.margins: Theme.spacingMedium
                    spacing: Theme.spacingSmall
                    Text { text: qsTr("Selected"); color: Theme.secondary
                           font.pixelSize: Theme.fontSizeLabel; font.bold: true }
                    Text {
                        Layout.fillWidth: true; wrapMode: Text.WordWrap
                        text: win.selRegion ? win.selRegion.name : qsTr("— nothing selected —")
                        color: win.selRegion ? Theme.text : Theme.mutedText
                        font.pixelSize: Theme.fontSizeSubtitle; font.bold: win.selRegion !== null
                    }
                    Text {
                        Layout.fillWidth: true; visible: win.selRegion !== null
                        text: win.selRegion ? win.selRegion.parent : ""
                        color: Theme.mutedText; font.pixelSize: Theme.fontSizeCaption
                    }
                    Button {
                        Layout.fillWidth: true; Layout.topMargin: Theme.spacingSmall
                        text: qsTr("Build this map")
                        enabled: win.selRegion !== null && !Backend.busy
                        onClicked: {
                            var dest = win.destOrPrompt(); if (!dest) return
                            Backend.build_region(win.selRegion.id, dest, win.regionCode(win.selRegion.name))
                        }
                    }
                }
            }

            // device / backup card
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: devCol.implicitHeight + Theme.spacingLarge
                color: Theme.card; radius: Theme.radiusCard; border.color: Theme.border
                ColumnLayout {
                    id: devCol
                    anchors.fill: parent; anchors.margins: Theme.spacingMedium
                    spacing: Theme.spacingSmall
                    Text { text: qsTr("Device"); color: Theme.secondary
                           font.pixelSize: Theme.fontSizeLabel; font.bold: true }
                    Text {
                        Layout.fillWidth: true; elide: Text.ElideMiddle
                        text: Backend.devicePath || qsTr("Plug in the Bryton over USB")
                        color: Backend.devicePath ? Theme.text : Theme.mutedText
                        font.pixelSize: Theme.fontSizeCaption
                    }
                    Button {
                        Layout.fillWidth: true
                        text: qsTr("Back up device maps to disk")
                        enabled: Backend.devicePath !== "" && !Backend.busy
                        onClicked: backupDialog.open()
                    }
                    Button {
                        Layout.fillWidth: true
                        text: qsTr("Install last build to device")
                        enabled: win.lastDat !== "" && Backend.devicePath !== "" && !Backend.busy
                        onClicked: Backend.install_to_device(win.lastDat, "true")
                    }
                }
            }

            // output folder
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: outCol.implicitHeight + Theme.spacingLarge
                color: Theme.card; radius: Theme.radiusCard; border.color: Theme.border
                ColumnLayout {
                    id: outCol
                    anchors.fill: parent; anchors.margins: Theme.spacingMedium
                    spacing: Theme.spacingSmall
                    Text { text: qsTr("Output folder"); color: Theme.secondary
                           font.pixelSize: Theme.fontSizeLabel; font.bold: true }
                    Text {
                        Layout.fillWidth: true; elide: Text.ElideMiddle
                        text: win.outDir || (Backend.devicePath ? Backend.devicePath + "/MAP/Update  (device)"
                                                                 : qsTr("choose a folder"))
                        color: Theme.mutedText; font.pixelSize: Theme.fontSizeCaption
                    }
                    Button { Layout.fillWidth: true; text: qsTr("Change…"); onClicked: outDirDialog.open() }
                }
            }

            Item { Layout.fillHeight: true }

            ProgressBar { id: progress; Layout.fillWidth: true; from: 0; to: 1 }
            Text {
                id: status; Layout.fillWidth: true; wrapMode: Text.WordWrap
                color: Theme.mutedText; font.pixelSize: Theme.fontSizeCaption
                text: qsTr("Pick a region and press Build.")
            }
        }
    }

    footer: Rectangle {
        color: Theme.surface
        implicitHeight: 130
        ScrollView {
            anchors.fill: parent; anchors.margins: Theme.spacingSmall
            TextArea {
                id: logArea
                readOnly: true; wrapMode: TextArea.Wrap
                color: Theme.mutedText; font.pixelSize: Theme.fontSizeCaption; font.family: "monospace"
                background: null
                text: qsTr("Ready.\n")
            }
        }
    }

    FolderDialog {
        id: outDirDialog
        title: qsTr("Choose output folder")
        onAccepted: win.outDir = win.urlToPath(selectedFolder)
    }
    FolderDialog {
        id: backupDialog
        title: qsTr("Choose backup destination")
        onAccepted: Backend.backup_device(win.urlToPath(selectedFolder))
    }
}
